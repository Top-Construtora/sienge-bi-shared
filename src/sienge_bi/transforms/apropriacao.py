"""Transformacao do relatorio 'ANALITICO_DE_APROPRIACAO_TOP-EMISSAO.xlsx' e
'ANALITICO_DE_APROPRIACAO_TOP-VENCIMENTO.xlsx'.

Schema destino: sienge.fato_apropriacao.
Granularidade: 1 linha por (documento, obra, servico) de apropriacao.

Estrutura do Excel:
  L0: ['Periodo', None, None, '01/01/2000 a 01/01/2050']
  L1: cabecalho real ['Obra', None, None, 'Unidade construtiva',
       None, 'Celula', None, 'Etapa', 'Subetapa', 'Servico',
       'Data', 'Data da baixa', 'Documento', 'Titulo/Parcela', 'Or',
       'Credor/Historico', 'Valor do documento', 'Valor', 'Observacao']
  L2+: dados

Como o arquivo de emissao usa col 10 como 'Data de emissao' e o de vencimento
usa col 10 como 'Data de vencimento', o nome do arquivo controla qual data
prevalece.
"""
import os
import re
import pandas as pd


_PAT_COD_NOME = re.compile(r"^\s*([\w.]+)\s*-\s*(.+)$", re.DOTALL)


# Indices das colunas (consistente para emissao e vencimento)
COL = {
    "obra_str": 0,         # "211 - CASAS SOLAR PLANALTO..."
    "unidade": 3,
    "celula": 5,
    "etapa": 7,
    "subetapa": 8,
    "servico_str": 9,      # "01.001.001.001 - Despesas com CREA"
    "data": 10,            # data principal (emissao OU vencimento)
    "data_baixa": 11,
    "documento": 12,
    "titulo": 13,
    "tipo_or": 14,         # AC, GI, CP, ME, FP, ...
    "credor": 15,
    "valor_doc": 16,
    "valor": 17,
    "obs": 18,
}


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


def _str_clean(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    return s or None


def transformar(df: pd.DataFrame, arquivo: str | None = None) -> pd.DataFrame:
    """Mapeia o Excel de Apropriacao Analitica para sienge.fato_apropriacao."""
    if df.empty:
        return df

    # Decide se a "Data" principal e emissao ou vencimento pelo nome do arquivo
    nome_arq = (arquivo or "").upper()
    is_vencimento = "VENCIMENTO" in nome_arq

    # L0 vira header pelo orquestrador (que le com header=0); L1 (cabecalho
    # real do Sienge) e linha 0 do df. Pulamos a partir de iloc[1:].
    raw = df.iloc[1:].reset_index(drop=True)

    # Filtra so linhas com Obra preenchida (col 0)
    raw = raw[raw.iloc[:, COL["obra_str"]].notna()].reset_index(drop=True)
    if raw.empty:
        return pd.DataFrame()

    obra_split = raw.iloc[:, COL["obra_str"]].apply(_parse_cod_nome)
    servico_split = raw.iloc[:, COL["servico_str"]].apply(_parse_cod_nome)

    data = raw.iloc[:, COL["data"]].apply(_to_date_br)
    data_baixa = raw.iloc[:, COL["data_baixa"]].apply(_to_date_br)

    out = pd.DataFrame({
        "empresa": None,
        "cod_obra": obra_split.apply(lambda t: t[0]),
        "_nome_obra": obra_split.apply(lambda t: t[1]),
        "unidade_construtiva": raw.iloc[:, COL["unidade"]].apply(_str_clean),
        "celula": raw.iloc[:, COL["celula"]].apply(_str_clean),
        "etapa": raw.iloc[:, COL["etapa"]].apply(_str_clean),
        "subetapa": raw.iloc[:, COL["subetapa"]].apply(_str_clean),
        "cod_servico": servico_split.apply(lambda t: t[0]),
        "descricao_servico": servico_split.apply(lambda t: t[1]),
        "cod_fornecedor": None,
        "tipo_or": raw.iloc[:, COL["tipo_or"]].apply(_str_clean),
        # dt_competencia = data principal do relatorio
        "dt_competencia": data,
        # Se for relatorio de Emissao: data=emissao, data_baixa=vencimento
        # Se for relatorio de Vencimento: data=vencimento, data_baixa=baixa
        "dt_emissao": data if not is_vencimento else None,
        "dt_vencimento": data if is_vencimento else data_baixa,
        "documento": raw.iloc[:, COL["documento"]].apply(_str_clean),
        "titulo_parcela": raw.iloc[:, COL["titulo"]].apply(_str_clean),
        "historico": raw.iloc[:, COL["credor"]].apply(_str_clean),
        "valor": raw.iloc[:, COL["valor"]].apply(_to_decimal),
        "valor_documento": raw.iloc[:, COL["valor_doc"]].apply(_to_decimal),
        "quantidade": None,
        "observacao": raw.iloc[:, COL["obs"]].apply(_str_clean),
        "_arquivo": os.path.basename(arquivo) if arquivo else "",
    })

    # Linhas sem documento OU sem cod_obra sao subtotais/cabecalhos - descartar
    out = out[
        out["documento"].notna() & out["cod_obra"].notna()
    ].reset_index(drop=True)

    # Dedup interna: mesmo (obra, servico, documento, valor) pode aparecer
    # quando ha varias parcelas/titulos - adiciona _seq pra desambiguar.
    grupo = ["cod_obra", "cod_servico", "documento", "valor", "_arquivo"]
    out["_seq"] = out.groupby(grupo, dropna=False).cumcount()

    return out
