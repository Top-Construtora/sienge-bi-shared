"""Transformacao do relatorio 'ORÇADO X COMPROMETIDO - *.xlsx'.

Schema destino: sienge.fato_orcado_comprometido.
Granularidade: 1 linha por (obra, codigo_servico) hierarquico (do nivel '01'
ate '01.001.001.NNN').

Header relevante:
  Linha 4: Obra (col 0 'Obra', col 2 '<cod> - <nome>')
  Linha 10: cabecalho da tabela
  Linha 11+: dados (col 0 = codigo orcamentario, col 1 = descricao)
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
    """Procura 'Obra' nas primeiras 10 linhas e retorna o codigo."""
    for i in range(min(10, len(df))):
        for j in range(min(4, df.shape[1])):
            v = df.iloc[i, j]
            if isinstance(v, str) and v.strip() == "Obra":
                # codigo geralmente esta a 2 colunas a direita
                for k in (j + 1, j + 2, j + 3):
                    if k < df.shape[1]:
                        cod, _ = _parse_cod_nome(df.iloc[i, k])
                        if cod:
                            return cod
    return None


def transformar(df: pd.DataFrame, arquivo: str | None = None) -> pd.DataFrame:
    """Mapeia o Excel hierarquico de Orcado x Comprometido para o schema."""
    if df.empty:
        return df

    cod_obra = _extrair_obra(df)

    rows = []
    for _, linha in df.iterrows():
        col0 = linha.iloc[0] if len(linha) > 0 else None
        col1 = linha.iloc[1] if len(linha) > 1 else None
        col9 = linha.iloc[9] if len(linha) > 9 else None    # Comprometido Total
        col12 = linha.iloc[12] if len(linha) > 12 else None  # Orcado Total
        col14 = linha.iloc[14] if len(linha) > 14 else None  # Saldo
        col15 = linha.iloc[15] if len(linha) > 15 else None  # Item/Orcamento (%)

        if pd.isna(col0):
            continue
        s0 = str(col0).strip()
        # Linhas de dado tem codigo orcamentario '01' / '01.001' / '01.001.001.NNN'
        if not re.match(r"^\d{2}(\.\d{3})*$", s0):
            continue

        valor_orcado = _safe_num(col12)
        valor_comprometido = _safe_num(col9)
        # Ignora linhas sem nenhum valor
        if valor_orcado is None and valor_comprometido is None:
            continue

        rows.append({
            "empresa": None,
            "cod_obra": cod_obra,
            "cod_servico": s0,
            "descricao": None if pd.isna(col1) else str(col1).strip(),
            "valor_orcado": valor_orcado or 0,
            "valor_comprometido": valor_comprometido or 0,
            "saldo": _safe_num(col14) or 0,
            "percentual": _safe_num(col15),
            "_arquivo": os.path.basename(arquivo) if arquivo else "",
        })

    if not rows:
        return pd.DataFrame()

    df_rows = pd.DataFrame(rows)
    # Mesmo cod_servico pode aparecer em multiplas Unidades Construtivas
    # do mesmo arquivo - agrega somando.
    agg = (df_rows
           .groupby(["cod_obra", "cod_servico", "_arquivo"], dropna=False, as_index=False)
           .agg(empresa=("empresa", "first"),
                descricao=("descricao", "first"),
                valor_orcado=("valor_orcado", "sum"),
                valor_comprometido=("valor_comprometido", "sum"),
                saldo=("saldo", "sum"),
                percentual=("percentual", "first")))
    return agg[
        ["empresa", "cod_obra", "cod_servico", "descricao",
         "valor_orcado", "valor_comprometido", "saldo", "percentual", "_arquivo"]
    ]
