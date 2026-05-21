"""Transformacao do relatorio 'MEDIDO X COMPROMETIDO - *.xlsx'.

Schema destino: sienge.fato_medido_comprometido.
Granularidade: 1 linha por (obra, codigo_servico) hierarquico.
"""
import os
import re
import pandas as pd


_PAT_COD_NOME = re.compile(r"^\s*([\w.]+)\s*-\s*(.+)$")


def _parse_cod_nome(s):
    if pd.isna(s):
        return (None, None)
    m = _PAT_COD_NOME.match(str(s).strip())
    if m:
        return (m.group(1), m.group(2).strip())
    return (None, None)


def _safe_num(v):
    if pd.isna(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _extrair_obra(df: pd.DataFrame) -> str | None:
    for i in range(min(10, len(df))):
        for j in range(min(5, df.shape[1])):
            v = df.iloc[i, j]
            if isinstance(v, str) and v.strip() == "Obra":
                for k in (j + 1, j + 2, j + 3):
                    if k < df.shape[1]:
                        cod, _ = _parse_cod_nome(df.iloc[i, k])
                        if cod:
                            return cod
    return None


def transformar(df: pd.DataFrame, arquivo: str | None = None) -> pd.DataFrame:
    if df.empty:
        return df

    cod_obra = _extrair_obra(df)

    rows = []
    for _, linha in df.iterrows():
        col0 = linha.iloc[0] if len(linha) > 0 else None
        col1 = linha.iloc[1] if len(linha) > 1 else None
        col5 = linha.iloc[5] if len(linha) > 5 else None    # Medido (%)
        col10 = linha.iloc[10] if len(linha) > 10 else None  # Comprometido Total
        col13 = linha.iloc[13] if len(linha) > 13 else None  # Medido Total

        if pd.isna(col0):
            continue
        s0 = str(col0).strip()
        if not re.match(r"^\d{2}(\.\d{3})*$", s0):
            continue

        valor_medido = _safe_num(col13)
        valor_comprometido = _safe_num(col10)
        if valor_medido is None and valor_comprometido is None:
            continue

        # Saldo: Comprometido - Medido (se ambos disponiveis)
        saldo = None
        if valor_comprometido is not None and valor_medido is not None:
            saldo = valor_comprometido - valor_medido

        rows.append({
            "empresa": None,
            "cod_obra": cod_obra,
            "cod_servico": s0,
            "descricao": None if pd.isna(col1) else str(col1).strip(),
            "valor_medido": valor_medido or 0,
            "valor_comprometido": valor_comprometido or 0,
            "saldo": saldo,
            "percentual": _safe_num(col5),
            "_arquivo": os.path.basename(arquivo) if arquivo else "",
        })

    if not rows:
        return pd.DataFrame()

    df_rows = pd.DataFrame(rows)
    agg = (df_rows
           .groupby(["cod_obra", "cod_servico", "_arquivo"], dropna=False, as_index=False)
           .agg(empresa=("empresa", "first"),
                descricao=("descricao", "first"),
                valor_medido=("valor_medido", "sum"),
                valor_comprometido=("valor_comprometido", "sum"),
                percentual=("percentual", "first")))
    agg["saldo"] = agg["valor_comprometido"] - agg["valor_medido"]
    return agg[
        ["empresa", "cod_obra", "cod_servico", "descricao",
         "valor_medido", "valor_comprometido", "saldo", "percentual", "_arquivo"]
    ]
