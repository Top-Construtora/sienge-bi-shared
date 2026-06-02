"""IngestaoRunner: orquestrador que percorre o catalogo de Relatorio's
de um robo e ingere no Supabase."""
from __future__ import annotations

import datetime
import glob
import os
import traceback
from typing import Callable, List

import pandas as pd

from .catalogo import Relatorio
from .db import upsert_dataframe, registrar_log, adicionar_hash, Cronometro
from .storage import enviar_para_storage


def _carregar_excel(caminho: str) -> pd.DataFrame:
    """Le um Excel; trata .xls (xlrd) e .xlsx (openpyxl).
    Aborta arquivos vazios/corrompidos (< 1KB) com ValueError tratavel."""
    if os.path.getsize(caminho) < 1024:
        raise ValueError(f"Arquivo muito pequeno (provavelmente corrompido): {caminho}")
    if caminho.endswith(".xls"):
        return pd.read_excel(caminho, engine="xlrd")
    return pd.read_excel(caminho, engine="openpyxl")


def _encontrar_arquivos(pasta: str, padrao_nome: str, multi: bool) -> list[str]:
    """Acha arquivo(s) Excel que casam com padrao_nome."""
    glob_pattern = os.path.join(pasta, f"{padrao_nome}*.xls*")
    candidatos = glob.glob(glob_pattern)
    if not candidatos:
        return []
    if multi:
        return sorted(candidatos)
    candidatos.sort(key=os.path.getmtime, reverse=True)
    return [candidatos[0]]


class IngestaoRunner:
    """Executor de ingestao para um robo.

    Cada robo (TOP/HABITAT/IMPULSI/INNOVAR/TANGARA) cria um runner com:
      - empresa: codigo da empresa (vira coluna `empresa` em todos os fatos)
      - catalogo: lista de Relatorio
      - logger: funcao de log (default print)
    """

    def __init__(self, empresa: str, catalogo: List[Relatorio],
                 logger: Callable[[str], None] = print):
        self.empresa = empresa
        self.catalogo = catalogo
        self.logger = logger

    def _processar(self, rel: Relatorio, dt_ref: datetime.date) -> dict:
        log = self.logger
        arquivos = _encontrar_arquivos(rel.pasta, rel.padrao_nome, rel.multi_arquivo)
        if not arquivos:
            log(f"[ingestao] {rel.nome}: nenhum arquivo encontrado em {rel.pasta}.")
            registrar_log(rel.nome, dt_ref, None, 0, 0, 0, "ERRO",
                          erro="Nenhum arquivo encontrado", duracao_seg=0)
            return {"status": "ERRO", "inseridas": 0, "atualizadas": 0}

        # Snapshot raw para Storage
        for arq in arquivos:
            ts = f"{dt_ref.year}/{dt_ref.month:02d}/{dt_ref.day:02d}"
            path = f"{ts}/{rel.nome}/{os.path.basename(arq)}"
            enviar_para_storage(arq, path, logger=log)

        # Le + transforma cada arquivo
        dfs = []
        total_lidas = 0
        for arq in arquivos:
            try:
                df_raw = _carregar_excel(arq)
                total_lidas += len(df_raw)
                df_t = rel.transformar(df_raw, arq)
                if df_t is not None and not df_t.empty:
                    dfs.append(df_t)
            except Exception as e:
                log(f"[ingestao] {rel.nome}: erro ao transformar {arq}: {e}")
                log(traceback.format_exc())

        if not dfs:
            registrar_log(rel.nome, dt_ref, arquivos[0], total_lidas, 0, 0, "ERRO",
                          erro="Transformacao resultou em DataFrame vazio", duracao_seg=0)
            return {"status": "ERRO", "inseridas": 0, "atualizadas": 0}

        df_final = pd.concat(dfs, ignore_index=True)
        # Garante empresa preenchida (transform pode sobrescrever, mas se nao,
        # o runner preenche com o codigo do robo)
        if "empresa" in df_final.columns:
            df_final["empresa"] = df_final["empresa"].fillna(self.empresa)
        else:
            df_final["empresa"] = self.empresa

        # Popula sienge.dim_obra a partir de colunas '_nome_obra' opcionais que
        # transforms expoem (ex.: contratos). Nao bloqueia ingestao do fato em
        # caso de erro.
        if "_nome_obra" in df_final.columns and "cod_obra" in df_final.columns:
            try:
                self._popular_dim_obra(df_final)
            except Exception as e:
                log(f"[ingestao] {rel.nome}: aviso - falha ao popular dim_obra: {e}")

        df_final["dt_ref"] = dt_ref
        df_final = adicionar_hash(df_final, rel.colunas_identidade)

        pk = ["dt_ref", "hash_linha"]
        with Cronometro() as crono:
            resultado = upsert_dataframe(df_final, rel.tabela, pk)

        registrar_log(
            relatorio=rel.nome, dt_ref=dt_ref,
            arquivo=(os.path.basename(arquivos[0]) if not rel.multi_arquivo
                     else f"{len(arquivos)} arquivos"),
            linhas_lidas=total_lidas, inseridas=resultado["inseridas"],
            atualizadas=resultado["atualizadas"], status="OK",
            duracao_seg=crono.duracao,
        )
        log(f"[ingestao] {rel.nome}: OK - lidas={total_lidas}, "
            f"inseridas={resultado['inseridas']}, atualizadas={resultado['atualizadas']}.")
        return {"status": "OK", **resultado}

    def _popular_dim_obra(self, df: pd.DataFrame) -> None:
        """Upsert (empresa, cod_obra, nome_obra) em sienge.dim_obra.

        Le pares unicos das colunas auxiliares '_nome_obra' + 'cod_obra' + 'empresa'.
        """
        pares = (
            df[["empresa", "cod_obra", "_nome_obra"]]
            .dropna(subset=["cod_obra", "_nome_obra"])
            .drop_duplicates(subset=["empresa", "cod_obra"])
            .rename(columns={"_nome_obra": "nome_obra"})
        )
        if pares.empty:
            return
        resultado = upsert_dataframe(pares, "dim_obra", ["empresa", "cod_obra"])
        self.logger(
            f"[ingestao] dim_obra: +{resultado['inseridas']} novas, "
            f"{resultado['atualizadas']} atualizadas"
        )

    def executar(self, dt_ref: datetime.date | None = None) -> dict:
        """Executa todos os relatorios do catalogo. Retorna sumario."""
        log = self.logger
        if dt_ref is None:
            dt_ref = datetime.date.today()
        log(f"\n========== INGESTAO {self.empresa} -> SUPABASE (dt_ref={dt_ref}) ==========")

        sumario = {}
        for rel in self.catalogo:
            try:
                sumario[rel.nome] = self._processar(rel, dt_ref)
            except Exception as e:
                log(f"[ingestao] {rel.nome}: ERRO FATAL: {e}")
                log(traceback.format_exc())
                try:
                    registrar_log(rel.nome, dt_ref, None, 0, 0, 0, "ERRO",
                                  erro=str(e), duracao_seg=0)
                except Exception:
                    pass
                sumario[rel.nome] = {"status": "ERRO", "inseridas": 0, "atualizadas": 0}

        # Limpeza de snapshots antigos (politica: manter ultimos N dias)
        try:
            self._purge_snapshots_antigos(dias_retencao=1)
        except Exception as e:
            log(f"[purge] AVISO: falhou limpeza de snapshots antigos: {e}")

        # Limpeza de Excels antigos no Supabase Storage (mesma janela)
        try:
            from .storage import purgar_storage_antigos
            n = purgar_storage_antigos(dias_retencao=1, logger=log)
            if n > 0:
                log(f"[purge-storage] total: -{n} arquivos")
        except Exception as e:
            log(f"[purge-storage] AVISO: {e}")

        # Refresh da camada BI (materialized views) - alimenta o dashboard
        try:
            self._refresh_views_bi()
        except Exception as e:
            log(f"[refresh_bi] AVISO: falhou refresh das views bi.*: {e}")

        log("========== INGESTAO CONCLUIDA ==========\n")
        return sumario

    def _purge_snapshots_antigos(self, dias_retencao: int = 5):
        """Deleta snapshots com dt_ref mais antigos que `dias_retencao` dias.
        Mantem sempre o snapshot mais recente por empresa (mesmo que > N dias)."""
        from .db import get_engine
        from sqlalchemy import text
        log = self.logger
        tabelas = [
            "fato_apropriacao", "fato_pedidos_compra", "fato_analitico_insumos",
            "fato_contratos", "fato_solicitacoes", "fato_medido_comprometido",
            "fato_orcado_comprometido", "fato_mapa_controle",
        ]
        log(f"[purge] retencao={dias_retencao} dias ...")
        eng = get_engine().execution_options(isolation_level="AUTOCOMMIT")
        with eng.connect() as conn:
            for t in tabelas:
                try:
                    r = conn.execute(text(f"""
                        DELETE FROM sienge.{t}
                        WHERE dt_ref < CURRENT_DATE - INTERVAL '{dias_retencao} days'
                          AND (empresa, dt_ref) NOT IN (
                              SELECT empresa, MAX(dt_ref) FROM sienge.{t} GROUP BY empresa
                          )
                    """))
                    if r.rowcount > 0:
                        log(f"  {t}: -{r.rowcount} linhas")
                except Exception as e:
                    log(f"  {t}: ERRO {e}")

    def _refresh_views_bi(self):
        """REFRESH MATERIALIZED VIEW nas views bi.* (atualiza camada agregada)."""
        from .db import conexao
        from sqlalchemy import text
        log = self.logger
        views = [
            "bi.dim_empresas",
            "bi.dim_obras",
            "bi.contratos",
            "bi.pedidos_compra",
            "bi.medido_comprometido",
            "bi.apropriacao_emissao_mensal",
            "bi.apropriacao_vencimento_mensal",
            "bi.insumos_apropriacao",
            "bi.ultima_atualizacao",
        ]
        log("[refresh_bi] atualizando views bi.* ...")
        # Usa autocommit do engine pra cada REFRESH (nao pode rodar em transacao)
        from .db import get_engine
        eng = get_engine().execution_options(isolation_level="AUTOCOMMIT")
        with eng.connect() as conn:
            # Aumenta timeout pra evitar 'statement timeout' em views grandes
            try:
                conn.execute(text("SET statement_timeout = '600s'"))
            except Exception:
                pass
            for v in views:
                try:
                    conn.execute(text(f"REFRESH MATERIALIZED VIEW {v}"))
                    log(f"  {v}: ok")
                except Exception as e:
                    log(f"  {v}: ERRO {e}")
