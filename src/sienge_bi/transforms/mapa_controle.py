"""Transformacao do relatorio "MAPA DE CONTROLE - <empresa>.xlsx".

Atualmente esse arquivo eh a "Relacao de Solicitacoes" detalhada do Sienge
(o relatorio "Mapa de Controle" original esta em descontinuacao). Quando o
"Painel de Compras" estiver liberado pra o usuario do RPA, este transform
sera estendido pra incluir PC/NF.

Schema do Excel (linha 4 = cabecalho):
  col 0: Insumo (cod + nome)
  col 2: Obra (cod + nome)
  col 4: Data (dt_solicitacao)
  col 6: Solicitante
  col 7: Solicitacao (num_solicitacao)
  col 8: Aut. (S/N)
  col 9: Dt. aut
  col10: Qt. pendente
  col11: Un.
  col13: Qt. atendida
  col14: Sd. (saldo pendente S/N)
  col15: Dt. previsao
  col16: Dt. atend.
  col17: Diferenca (dias)

Destino: sienge.fato_mapa_controle
"""
import os
import re
import pandas as pd


_PAT_COD_NOME = re.compile(r"^\s*([\w.]+)\s*-\s*(.+)$", re.DOTALL)


def _parse_cod_nome(s):
    if pd.isna(s):
        return (None, None)
    m = _PAT_COD_NOME.match(str(s).strip())
    if m:
        return (m.group(1), m.group(2).strip())
    return (None, str(s).strip())


def _to_date_br(v):
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


def _to_int(v):
    if pd.isna(v):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _str_clean(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    return s or None


def transformar(df: pd.DataFrame, arquivo: str | None = None) -> pd.DataFrame:
    """Mapeia o Excel de Mapa de Controle (Relacao de Solicitacoes detalhada)."""
    if df.empty:
        return df

    # L0 vira header pelo orquestrador. L4 (real header do Sienge) eh linha
    # 3 do df (porque o orquestrador le com header=0 e pulamos linhas).
    # Os dados comecam em L5 do Excel (iloc[4] do df ja sem header).
    raw = df.iloc[4:].reset_index(drop=True)

    # Filtra so linhas com Insumo preenchido
    raw = raw[raw.iloc[:, 0].notna()].reset_index(drop=True)
    if raw.empty:
        return pd.DataFrame()

    insumo_split = raw.iloc[:, 0].apply(_parse_cod_nome)
    obra_split = raw.iloc[:, 2].apply(_parse_cod_nome)

    out = pd.DataFrame({
        "empresa": None,
        "cod_obra": obra_split.apply(lambda t: t[0]),
        "_nome_obra": obra_split.apply(lambda t: t[1]),
        "cod_insumo": insumo_split.apply(lambda t: t[0]),
        "descricao": insumo_split.apply(lambda t: t[1]),
        "dt_solicitacao": raw.iloc[:, 4].apply(_to_date_br),
        "solicitante": raw.iloc[:, 6].apply(_str_clean),
        "num_solicitacao": raw.iloc[:, 7].apply(lambda v: str(_to_int(v)) if _to_int(v) is not None else _str_clean(v)),
        "autorizado": raw.iloc[:, 8].apply(_str_clean),
        "dt_autorizacao": raw.iloc[:, 9].apply(_to_date_br),
        "qtd_pendente": raw.iloc[:, 10].apply(_to_decimal),
        "unidade": raw.iloc[:, 11].apply(_str_clean),
        "qtd_atendida": raw.iloc[:, 13].apply(_to_decimal),
        "saldo_pendente": raw.iloc[:, 14].apply(_str_clean),
        "dt_previsao": raw.iloc[:, 15].apply(_to_date_br),
        "dt_atendimento": raw.iloc[:, 16].apply(_to_date_br),
        "dif_dias": raw.iloc[:, 17].apply(_to_int),
        "_arquivo": os.path.basename(arquivo) if arquivo else "",
    })

    # Descarta linhas sem cod_insumo OU sem cod_obra (sao subtotais/cabecalhos)
    out = out[out["cod_insumo"].notna() & out["cod_obra"].notna()].reset_index(drop=True)

    return out
