"""Helpers de banco: engine Supabase Postgres + upsert idempotente + log."""
from __future__ import annotations

import hashlib
import os
import time
from contextlib import contextmanager
from typing import Iterable

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import insert as pg_insert


_engine: Engine | None = None


def get_engine() -> Engine:
    """Engine global (singleton)."""
    global _engine
    if _engine is None:
        url = os.environ.get("SUPABASE_DB_URL")
        if not url:
            raise RuntimeError(
                "SUPABASE_DB_URL nao definido. Configure no .env do seu repo."
            )
        _engine = create_engine(
            url,
            pool_size=2,
            max_overflow=2,
            pool_pre_ping=True,
            pool_recycle=300,           # recicla conexoes a cada 5min (evita timeout do PgBouncer)
            connect_args={
                "options": "-c search_path=sienge,public",
                "connect_timeout": 30,
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 3,
            },
        )
    return _engine


@contextmanager
def conexao():
    eng = get_engine()
    with eng.begin() as conn:
        yield conn


def hash_linha(row: pd.Series, colunas: Iterable[str]) -> str:
    """Hash determinista da identidade da linha (32 hex chars)."""
    parts = []
    for col in colunas:
        v = row.get(col)
        parts.append("" if pd.isna(v) else str(v))
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def adicionar_hash(df: pd.DataFrame, colunas_identidade: list[str],
                   nome_coluna: str = "hash_linha") -> pd.DataFrame:
    df = df.copy()
    df[nome_coluna] = df.apply(lambda r: hash_linha(r, colunas_identidade), axis=1)
    return df


def upsert_dataframe(df: pd.DataFrame, tabela: str, pk_cols: list[str],
                     schema: str = "sienge", batch_size: int = 200) -> dict:
    """INSERT ... ON CONFLICT DO UPDATE em batches.

    Retorna {'inseridas': N, 'atualizadas': M} (estimado por contagem).
    """
    if df.empty:
        return {"inseridas": 0, "atualizadas": 0}

    from sqlalchemy import MetaData, Table

    eng = get_engine()
    meta = MetaData(schema=schema)
    tbl = Table(tabela, meta, autoload_with=eng)

    colunas = [c.name for c in tbl.columns if c.name in df.columns]
    df_carga = df[colunas]

    with eng.begin() as conn:
        antes = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.{tabela}")).scalar() or 0

        for inicio in range(0, len(df_carga), batch_size):
            lote = df_carga.iloc[inicio:inicio + batch_size]
            registros = lote.where(pd.notnull(lote), None).to_dict(orient="records")
            stmt = pg_insert(tbl).values(registros)
            update_cols = {c.name: stmt.excluded[c.name]
                           for c in tbl.columns
                           if c.name not in pk_cols and c.name in df.columns}
            if update_cols:
                stmt = stmt.on_conflict_do_update(index_elements=pk_cols, set_=update_cols)
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
            conn.execute(stmt)

        depois = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.{tabela}")).scalar() or 0

    inseridas = depois - antes
    atualizadas = len(df_carga) - inseridas
    return {"inseridas": int(inseridas), "atualizadas": int(max(atualizadas, 0))}


def registrar_log(relatorio: str, dt_ref, arquivo: str | None,
                  linhas_lidas: int, inseridas: int, atualizadas: int,
                  status: str, erro: str | None = None,
                  duracao_seg: float | None = None) -> None:
    """Insere em sienge.log_ingestao."""
    with conexao() as conn:
        conn.execute(text("""
            INSERT INTO sienge.log_ingestao
                (dt_ref, relatorio, arquivo, linhas_lidas, linhas_inseridas,
                 linhas_atualizadas, status, erro, duracao_seg)
            VALUES (:dt_ref, :relatorio, :arquivo, :linhas_lidas, :inseridas,
                    :atualizadas, :status, :erro, :duracao_seg)
        """), {
            "dt_ref": dt_ref, "relatorio": relatorio, "arquivo": arquivo,
            "linhas_lidas": linhas_lidas, "inseridas": inseridas,
            "atualizadas": atualizadas, "status": status,
            "erro": erro, "duracao_seg": duracao_seg,
        })


class Cronometro:
    def __init__(self):
        self.inicio = None
    def __enter__(self):
        self.inicio = time.time()
        return self
    def __exit__(self, *_):
        self.duracao = time.time() - self.inicio
