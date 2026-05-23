"""Transformacao do relatorio 'MEDIDO X COMPROMETIDO - *.xlsx'.

Schema destino: sienge.fato_medido_comprometido.
Granularidade: 1 linha por (obra, codigo_servico) hierarquico.

Indices das colunas do Excel (validados em 2026-05-22):
  0  Codigo (hierarquia: 01, 01.001, 01.001.001, ...)
  1  Descricao
  5  Medido (%)
  6  Acumulado Comprometido
  9  Comprometido no Periodo
  10 Comprometido Total
  12 Planejado Total           (= Orcado)
  13 Medido Total
  15 Estoque
  17 Comprometido / Medido (%)
  19 Comp. / Medido com Estoque (%)
"""
import os
import re
import pandas as pd


_PAT_COD_NOME = re.compile(r"^\s*([\w.]+)\s*-\s*(.+)$")
# Codigos hierarquicos validos: 01, 01.001, 01.001.001 (so digitos com pontos)
_PAT_HIER_COD = re.compile(r"^\d{2}(\.\d{3})*$")


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
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _extrair_obra(df: pd.DataFrame) -> str | None:
    """Le 'Obra' do cabecalho do Excel (geralmente linha 4-5, col 3)."""
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
        if pd.isna(col0):
            continue
        s0 = str(col0).strip()
        if not _PAT_HIER_COD.match(s0):
            continue

        # Pega os indices conhecidos (alguns podem nao existir em linhas mais curtas)
        def at(idx):
            return linha.iloc[idx] if len(linha) > idx else None

        descricao         = None if pd.isna(at(1))  else str(at(1)).strip()
        medido_pct        = _safe_num(at(5))
        valor_comprometido = _safe_num(at(10))
        valor_orcado      = _safe_num(at(12))
        valor_medido      = _safe_num(at(13))
        valor_estoque     = _safe_num(at(15))
        pct_comp_medido   = _safe_num(at(17))
        pct_comp_estoque  = _safe_num(at(19))

        # Linhas todas zero/null nao agregam - pula
        if all(v is None or v == 0 for v in [valor_medido, valor_comprometido, valor_orcado, valor_estoque]):
            continue

        rows.append({
            "empresa": None,
            "cod_obra": cod_obra,
            "cod_servico": s0,
            "descricao": descricao,
            "valor_orcado": valor_orcado or 0.0,
            "valor_medido": valor_medido or 0.0,
            "valor_comprometido": valor_comprometido or 0.0,
            "valor_estoque": valor_estoque or 0.0,
            "percentual_medido": medido_pct,
            "percentual_comprometido_medido": pct_comp_medido,
            "percentual_comprometido_medido_estoque": pct_comp_estoque,
            "_arquivo": os.path.basename(arquivo) if arquivo else "",
        })

    if not rows:
        return pd.DataFrame()

    df_rows = pd.DataFrame(rows)
    agg = (df_rows
           .groupby(["cod_obra", "cod_servico", "_arquivo"], dropna=False, as_index=False)
           .agg(empresa=("empresa", "first"),
                descricao=("descricao", "first"),
                valor_orcado=("valor_orcado", "sum"),
                valor_medido=("valor_medido", "sum"),
                valor_comprometido=("valor_comprometido", "sum"),
                valor_estoque=("valor_estoque", "sum"),
                percentual_medido=("percentual_medido", "first"),
                percentual_comprometido_medido=("percentual_comprometido_medido", "first"),
                percentual_comprometido_medido_estoque=("percentual_comprometido_medido_estoque", "first")))

    # Saldo a Executar = Orcado - Comprometido
    agg["saldo_executar"] = agg["valor_orcado"] - agg["valor_comprometido"]
    # Saldo Agregado = Comprometido - Medido (representa "comprometido nao pago ainda")
    agg["saldo_agregado"] = agg["valor_comprometido"] - agg["valor_medido"]
    # Mantem 'saldo' (campo antigo) = saldo_agregado pra retrocompatibilidade
    agg["saldo"] = agg["saldo_agregado"]
    # Mantem 'percentual' (campo antigo) = percentual_medido pra retrocompatibilidade
    agg["percentual"] = agg["percentual_medido"]

    return agg[[
        "empresa", "cod_obra", "cod_servico", "descricao",
        "valor_orcado", "valor_medido", "valor_comprometido", "valor_estoque",
        "saldo_executar", "saldo_agregado",
        "percentual_medido", "percentual_comprometido_medido",
        "percentual_comprometido_medido_estoque",
        "saldo", "percentual",
        "_arquivo",
    ]]
