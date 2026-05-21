"""Transformacao do relatorio 'RELACAO DE PEDIDOS DE COMPRAS - TOP.xlsx'.

Granularidade do Excel: 1 linha por pedido (agregado, sem detalhe por insumo).
Schema destino: sienge.fato_pedidos_compra.

Os campos detalhados por insumo (cod_insumo, descricao_insumo, quantidade,
valor_unitario) ficam NULL porque o Sienge nao exporta no nivel de item neste
relatorio. Se precisar, e outro relatorio.
"""
import pandas as pd


def _to_str_int(v):
    """Converte float/int -> string sem .0 (ex: 645.0 -> '645'). NaN -> None."""
    if pd.isna(v):
        return None
    try:
        return str(int(v))
    except (TypeError, ValueError):
        s = str(v).strip()
        return s or None


def _to_date_br(v):
    """Parseia 'dd/mm/yyyy' -> date. NaN/erro -> None."""
    if pd.isna(v):
        return None
    try:
        return pd.to_datetime(v, dayfirst=True, errors="coerce").date()
    except Exception:
        return None


def _to_decimal(v):
    if pd.isna(v):
        return None
    try:
        return float(v)
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

    out = pd.DataFrame({
        "num_pedido": df["N. do Pedido"].apply(_to_str_int),
        "empresa": None,
        "cod_obra": df["Cód. Obra"].apply(_to_str_int),
        "cod_fornecedor": df["Cód. Fornecedor"].apply(_to_str_int),
        "cod_insumo": None,         # granularidade por pedido, sem item
        "descricao_insumo": None,
        "dt_emissao": df["Data do Pedido"].apply(_to_date_br),
        "dt_entrega": None,
        "quantidade": None,
        "valor_unitario": None,
        "valor_total": df["Total do Pedido"].apply(_to_decimal),
        "status": df["Situação dos Pedidos"].apply(_str_clean),
    })

    # Remove linhas sem num_pedido (subtotais/cabecalhos)
    out = out[out["num_pedido"].notna()].reset_index(drop=True)

    return out
