"""Transformacao do relatorio 'RELATORIO DE RELACAO DE SOLICITACOES - TOP.xlsx'.

Schema destino: sienge.fato_solicitacoes.
Granularidade: 1 linha por (solicitacao, insumo, obra).

Particularidade: o Excel tem cabecalho complexo - titulo nas primeiras 4 linhas,
cabecalho real na linha 4, dados a partir da linha 5. Lemos por posicao.
"""
import re
import pandas as pd


# Indices das colunas no Excel (header na linha 4, validado em 2026-05-19).
COL = {
    "insumo_str": 0,     # "2 - Abraçadeira / 1/2 X 3/4"
    "obra_str": 2,       # "226 - TERMINAL NOVO MUNDO"
    "dt_solicitacao": 4,
    "solicitante": 6,
    "num_solicitacao": 7,
    "autorizado": 8,     # 'S' ou 'N'
    "dt_autorizacao": 9,
    "qt_pendente": 10,
    "unidade": 11,
    "qt_atendida": 13,
    "saldo": 14,
    "dt_previsao": 15,
    "dt_atendimento": 16,
    "diferenca": 17,
}


def _split_codigo_nome(valor):
    if pd.isna(valor):
        return (None, None)
    s = str(valor).strip()
    m = re.match(r"^\s*([0-9A-Z]+)\s*-\s*(.+)$", s)
    if m:
        return (m.group(1), m.group(2).strip())
    return (None, s)


def _to_date_br(v):
    if pd.isna(v):
        return None
    try:
        ts = pd.to_datetime(v, dayfirst=True, errors="coerce")
    except Exception:
        return None
    # to_datetime(errors="coerce") devolve NaT pra strings invalidas; NaT.date()
    # tambem retorna NaT, que SQLAlchemy serializa como literal 'NaT' e quebra
    # o INSERT no Postgres (InvalidDatetimeFormat).
    if pd.isna(ts):
        return None
    return ts.date()


def _to_decimal(v):
    if pd.isna(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_str_int(v):
    if pd.isna(v):
        return None
    try:
        return str(int(float(v)))
    except (TypeError, ValueError):
        s = str(v).strip()
        return s or None


def _str_clean(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    return s or None


def _autorizado_to_status(v):
    """'S' -> 'Autorizada'; 'N' -> 'Pendente'; outro -> valor cru."""
    if pd.isna(v):
        return None
    s = str(v).strip().upper()
    return {"S": "Autorizada", "N": "Pendente"}.get(s, s)


def transformar(df: pd.DataFrame, arquivo: str | None = None) -> pd.DataFrame:
    """Mapeia o Excel de Solicitacoes para sienge.fato_solicitacoes.

    O orquestrador le o Excel padrao (header=0). Como o cabecalho real esta
    na linha 4, ignoramos as primeiras linhas aqui dentro.
    """
    if df.empty:
        return df

    # Linhas 0-3 sao titulo/cabecalho - descartar. Os dados comecam na linha 4
    # do df (que veio do Excel ja com header=0 do orquestrador).
    raw = df.iloc[4:].copy().reset_index(drop=True)
    raw = raw.iloc[:, [COL[k] for k in COL]].copy()
    raw.columns = list(COL.keys())

    insumo_split = raw["insumo_str"].apply(_split_codigo_nome)
    obra_split = raw["obra_str"].apply(_split_codigo_nome)

    # Quantidade = atendida + pendente (total solicitado).
    qt_atendida = raw["qt_atendida"].apply(_to_decimal)
    qt_pendente = raw["qt_pendente"].apply(_to_decimal)
    quantidade = qt_atendida.fillna(0) + qt_pendente.fillna(0)

    out = pd.DataFrame({
        "num_solicitacao": raw["num_solicitacao"].apply(_to_str_int),
        "empresa": None,
        "cod_obra": obra_split.apply(lambda t: t[0]),
        "cod_insumo": insumo_split.apply(lambda t: t[0]),
        "descricao": insumo_split.apply(lambda t: t[1]),
        "quantidade": quantidade,
        "dt_solicitacao": raw["dt_solicitacao"].apply(_to_date_br),
        "dt_necessidade": raw["dt_previsao"].apply(_to_date_br),
        "status": raw["autorizado"].apply(_autorizado_to_status),
        "solicitante": raw["solicitante"].apply(_str_clean),
    })

    # Linhas sem num_solicitacao OU sem cod_insumo sao lixo
    out = out[
        out["num_solicitacao"].notna() & out["cod_insumo"].notna()
    ].reset_index(drop=True)

    # O Excel as vezes tem linhas absolutamente identicas (entregas parciais
    # repetidas). Adiciona um numero de sequencia dentro de cada grupo de
    # duplicatas para garantir hash unico (entra como _seq nas colunas de
    # identidade do orquestrador).
    grupo_cols = [
        "num_solicitacao", "cod_obra", "cod_insumo",
        "dt_solicitacao", "quantidade", "solicitante",
    ]
    out["_seq"] = out.groupby(grupo_cols, dropna=False).cumcount()

    return out
