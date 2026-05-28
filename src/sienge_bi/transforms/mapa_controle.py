"""Transformacao do relatorio "sienge_relatorio-*.xlsx" (Mapa de Controle integrado).

Esse relatorio do Sienge traz, num unico arquivo, a cadeia inteira de cada
item: Solicitacao de Compra (SC) -> Pedido de Compra (PC) -> Nota Fiscal
(NF) -> Entrega na obra. Eh ele que destrava os 4 SLAs do PBI:

    SLA Geral do Processo         = dt_entrega_obra - dt_solicitacao
    SLA Entrada Obra x Vcto NF    = dt_entrega_obra - dt_nf
    SLA Solicitacao x Pedido      = dt_pedido       - dt_solicitacao
    SLA Pedido x Emissao NF       = dt_nf           - dt_pedido

Schema do Excel (cabecalho na linha 1, dados a partir da linha 2):
  0 N. Solicitacao            20 Data do pedido
  1 Cod. Obra                 21 Situacao do pedido
  2 Obra                      22 Comprador
  3 Cod. Insumo               23 Cod. Fornecedor
  4 Descricao do insumo       24 Fornecedor
  5 Cod. Grupo de insumo      25 Previsao de entrega
  6 Grupo de insumo           26 Data autorizacao do pedido
  7 Comprador distribuido     27 Situacao autorizacao do pedido
  8 Detalhe                   28 Alcada (Pedido)
  9 Marca                     29 Quantidade entregue
 10 Quantidade solicitada     30 Saldo
 11 Unidade de movimento      31 Data da Nota fiscal
 12 Data da solicitacao       32 N. da Nota fiscal
 13 Solicitante               33 Valor da nota
 14 Situacao da solicitacao   34 Chave NF-e
 15 Data para chegada obra    35 Anexo (Nota Fiscal)
 16 Data autorizacao SC       36 Numero de parcelas
 17 Situacao autorizacao item 37 Situacao pagamento
 18 Alcada (Solicitacao)      38 Data entrega na obra
 19 N. do Pedido

Destino: sienge.fato_mapa_controle (schema reescrito em
2026-05-27-mapa-controle-integrado.sql).
"""
import os
import re
import pandas as pd


_RE_VALOR = re.compile(r"[^0-9,\-]")


def _to_date_br(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return None
    try:
        d = pd.to_datetime(v, dayfirst=True, errors="coerce")
        return None if pd.isna(d) else d.date()
    except Exception:
        return None


def _to_decimal(v):
    """Aceita float, '1,0000', 'R$ 145,53', 'R$\xa02.900,00'."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    s = _RE_VALOR.sub("", s).replace(",", ".")
    if s in ("", "-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_int(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _str_clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return None
    s = str(v).strip()
    return s or None


def _split_cod_nome(v):
    """'20191 - ADM CENTRAL ...' -> ('20191', 'ADM CENTRAL ...').

    Quando ja vem o cod separado (numeros puros), retorna (str(v), None).
    """
    s = _str_clean(v)
    if s is None:
        return (None, None)
    m = re.match(r"^\s*([\w.\-/]+)\s*-\s*(.+)$", s, flags=re.DOTALL)
    if m:
        return (m.group(1).strip(), m.group(2).strip())
    return (s, None)


def transformar(df: pd.DataFrame, arquivo: str | None = None) -> pd.DataFrame:
    """Mapeia o relatorio integrado de SC/PC/NF para fato_mapa_controle."""
    if df.empty:
        return df

    raw = df.copy()
    # remove linhas totalmente vazias
    raw = raw.dropna(how="all").reset_index(drop=True)
    # descarta linhas sem N. Solicitacao
    raw = raw[raw.iloc[:, 0].notna()].reset_index(drop=True)
    if raw.empty:
        return pd.DataFrame()

    obra_split = raw.iloc[:, 2].apply(_split_cod_nome)
    insumo_split = raw.iloc[:, 4].apply(_split_cod_nome)
    grupo_split = raw.iloc[:, 6].apply(_split_cod_nome)
    forn_split = raw.iloc[:, 24].apply(_split_cod_nome)

    out = pd.DataFrame({
        "empresa": None,
        "num_solicitacao": raw.iloc[:, 0].apply(lambda v: str(_to_int(v)) if _to_int(v) is not None else _str_clean(v)),
        "cod_obra": raw.iloc[:, 1].apply(lambda v: str(_to_int(v)) if _to_int(v) is not None else _str_clean(v)),
        "_nome_obra": obra_split.apply(lambda t: t[1]),
        "cod_insumo": raw.iloc[:, 3].apply(lambda v: str(_to_int(v)) if _to_int(v) is not None else _str_clean(v)),
        "descricao_insumo": insumo_split.apply(lambda t: t[1] or t[0]),
        "cod_grupo": raw.iloc[:, 5].apply(_str_clean),
        "nome_grupo": grupo_split.apply(lambda t: t[1]),
        "comprador_distribuido": raw.iloc[:, 7].apply(_str_clean),
        "detalhe": raw.iloc[:, 8].apply(_str_clean),
        "marca": raw.iloc[:, 9].apply(_str_clean),
        "qtd_solicitada": raw.iloc[:, 10].apply(_to_decimal),
        "unidade": raw.iloc[:, 11].apply(_str_clean),
        "dt_solicitacao": raw.iloc[:, 12].apply(_to_date_br),
        "solicitante": raw.iloc[:, 13].apply(_str_clean),
        "situacao_solicitacao": raw.iloc[:, 14].apply(_str_clean),
        "dt_chegada_obra": raw.iloc[:, 15].apply(_to_date_br),
        "dt_autorizacao_sc": raw.iloc[:, 16].apply(_to_date_br),
        "situacao_autorizacao_item": raw.iloc[:, 17].apply(_str_clean),
        "num_pedido": raw.iloc[:, 19].apply(lambda v: str(_to_int(v)) if _to_int(v) is not None else _str_clean(v)),
        "dt_pedido": raw.iloc[:, 20].apply(_to_date_br),
        "situacao_pedido": raw.iloc[:, 21].apply(_str_clean),
        "comprador": raw.iloc[:, 22].apply(_str_clean),
        "cod_fornecedor": raw.iloc[:, 23].apply(lambda v: str(_to_int(v)) if _to_int(v) is not None else _str_clean(v)),
        "nome_fornecedor": forn_split.apply(lambda t: t[1]),
        "dt_previsao_entrega": raw.iloc[:, 25].apply(_to_date_br),
        "dt_autorizacao_pc": raw.iloc[:, 26].apply(_to_date_br),
        "situacao_autorizacao_pedido": raw.iloc[:, 27].apply(_str_clean),
        "qtd_entregue": raw.iloc[:, 29].apply(_to_decimal),
        "saldo": raw.iloc[:, 30].apply(_to_decimal),
        "dt_nf": raw.iloc[:, 31].apply(_to_date_br),
        "num_nf": raw.iloc[:, 32].apply(_str_clean),
        "valor_nf": raw.iloc[:, 33].apply(_to_decimal),
        "chave_nfe": raw.iloc[:, 34].apply(_str_clean),
        "num_parcelas": raw.iloc[:, 36].apply(_to_int),
        "situacao_pagamento": raw.iloc[:, 37].apply(_str_clean),
        "dt_entrega_obra": raw.iloc[:, 38].apply(_to_date_br),
        "_arquivo": os.path.basename(arquivo) if arquivo else "",
    })

    # SLAs derivados (em dias) - calculados aqui pra simplificar consultas
    def _diff(a, b):
        if a is None or b is None:
            return None
        return (a - b).days

    out["sla_geral"]        = [_diff(eo, ds) for eo, ds in zip(out["dt_entrega_obra"], out["dt_solicitacao"])]
    out["sla_sc_pc"]        = [_diff(pe, ds) for pe, ds in zip(out["dt_pedido"],       out["dt_solicitacao"])]
    out["sla_pc_nf"]        = [_diff(nf, pe) for nf, pe in zip(out["dt_nf"],           out["dt_pedido"])]
    out["sla_nf_entrega"]   = [_diff(eo, nf) for eo, nf in zip(out["dt_entrega_obra"], out["dt_nf"])]

    out = out[out["num_solicitacao"].notna()].reset_index(drop=True)
    return out
