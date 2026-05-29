"""Transformacao do relatorio 'RELACAO DE PEDIDOS DE COMPRAS - XXX.xlsx'.

Granularidade do Excel: 1 linha por pedido (agregado, sem detalhe por insumo).
Schema destino: sienge.fato_pedidos_compra.

Os campos detalhados por insumo (cod_insumo, descricao_insumo, quantidade,
valor_unitario) ficam NULL porque o Sienge nao exporta no nivel de item neste
relatorio. Se precisar de itens, é outro relatório (Analítico de Pedidos
Diretos).
"""
import pandas as pd


COL = {
    "num_pedido": 0,
    "num_acordo_preco": 1,
    "num_versao_acordo": 2,
    "cod_fornecedor": 3,
    "nome_fornecedor": 4,
    "cod_obra": 5,
    "obra_str": 6,
    "dt_pedido": 7,
    "comprador": 8,
    "status": 9,
    "valor_total": 10,
    "total_pendente": 11,
    "total_entregue": 12,
    "departamento": 14,
    "centro_custo": 16,
}


def _to_str_int(v):
    if pd.isna(v):
        return None
    try:
        return str(int(float(v)))
    except (TypeError, ValueError):
        s = str(v).strip()
        return s or None


def _to_date_br(v):
    if pd.isna(v):
        return None
    try:
        ts = pd.to_datetime(v, dayfirst=True, errors="coerce")
    except Exception:
        return None
    if pd.isna(ts):
        return None
    return ts.date()


def _to_decimal(v):
    if pd.isna(v):
        return None
    if isinstance(v, (int, float)):
        try:
            f = float(v)
            if f != f or f in (float("inf"), float("-inf")):
                return None
            return f
        except (TypeError, ValueError):
            return None
    s = str(v).strip()
    if not s:
        return None
    s = s.replace("R$", "").replace(" ", "").strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        f = float(s)
        if f != f or f in (float("inf"), float("-inf")):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _str_clean(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    return s or None


def transformar(df: pd.DataFrame, arquivo: str | None = None) -> pd.DataFrame:
    """Mapeia o Excel de Pedidos de Compra para sienge.fato_pedidos_compra."""
    if df.empty:
        return df

    # Le por posicao (cabecalho do Sienge tem mojibake)
    raw = df.iloc[:, [COL[k] for k in COL]].copy()
    raw.columns = list(COL.keys())

    out = pd.DataFrame({
        "num_pedido":       raw["num_pedido"].apply(_to_str_int),
        "num_acordo_preco": raw["num_acordo_preco"].apply(_to_str_int),
        "num_versao_acordo": raw["num_versao_acordo"].apply(_to_str_int),
        "empresa":          None,
        "cod_obra":         raw["cod_obra"].apply(_to_str_int),
        "_nome_obra":       raw["obra_str"].apply(lambda v: (
            str(v).split(' - ', 1)[1].strip() if not pd.isna(v) and ' - ' in str(v) else None
        )),
        "cod_fornecedor":   raw["cod_fornecedor"].apply(_to_str_int),
        "nome_fornecedor":  raw["nome_fornecedor"].apply(_str_clean),
        "cod_insumo":       None,         # granularidade por pedido, sem item
        "descricao_insumo": None,
        "dt_emissao":       raw["dt_pedido"].apply(_to_date_br),
        "dt_entrega":       None,
        "quantidade":       None,
        "valor_unitario":   None,
        "valor_total":      raw["valor_total"].apply(_to_decimal),
        "total_pendente":   raw["total_pendente"].apply(_to_decimal),
        "total_entregue":   raw["total_entregue"].apply(_to_decimal),
        "comprador":        raw["comprador"].apply(_str_clean),
        "departamento":     raw["departamento"].apply(_str_clean),
        "centro_custo":     raw["centro_custo"].apply(_str_clean),
        "status":           raw["status"].apply(_str_clean),
    })

    out = out[out["num_pedido"].notna()].reset_index(drop=True)
    return out
