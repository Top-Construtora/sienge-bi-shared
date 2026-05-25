"""Transformacao do relatorio 'Cadastros de Contratos-XXX.xlsx'.

Granularidade: 1 linha por contrato (PK: num_contrato).
Schema destino: sienge.fato_contratos.

Le por POSICAO porque o Sienge exporta os cabecalhos com encoding quebrado
(mojibake tipo 'C�d.', 'Situa��o'). Mapeia ao schema fixo.
"""
import re
import pandas as pd


# Indices das colunas no Excel exportado pelo Sienge (validado em 2026-05-21).
# Se o Sienge mudar a ordem das colunas, ajuste aqui.
COL = {
    "contrato": 0,
    "cod_fornecedor": 3,
    "fornecedor": 4,
    "cnpj_fornecedor": 5,
    "objeto": 9,
    "empresa_str": 10,        # "1021 - SPE RIO VERDE LTDA"
    "cod_empresa": 11,
    "obra_str": 13,           # "2231 - MALL BNP - RIO VERDE - FAT. DIRETO"
    "dt_contrato": 14,
    "dt_inicio": 15,
    "dt_termino": 16,
    "situacao": 17,           # 'Situacao do Contrato' (texto cru do Sienge)
    "total": 21,
    "total_medido": 22,
    "saldo": 23,
    "tipo_contrato": 31,      # 'Tipo do Contrato' (descricao)
}


def _split_codigo_nome(valor):
    """'1021 - SPE RIO VERDE LTDA' -> ('1021', 'SPE RIO VERDE LTDA').
    Faz split apenas no primeiro ' - ' (nomes podem conter mais ' - ').
    """
    if pd.isna(valor):
        return (None, None)
    s = str(valor).strip()
    m = re.match(r"^\s*(\d+)\s*-\s*(.+)$", s)
    if m:
        return (m.group(1), m.group(2).strip())
    return (None, s)


def _to_date(v):
    if pd.isna(v):
        return None
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None


def _to_decimal(v):
    """Converte para float. Trata strings com vírgula brasileira e 'R$ '.
    Retorna None se nao for um numero finito."""
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
    # String: limpa R$, pontos de milhar e troca virgula por ponto
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
    """
    Le um DataFrame do Excel de Cadastros de Contratos e devolve um
    DataFrame pronto pra upsert em sienge.fato_contratos.

    Colunas de saida (devem casar com o schema, exceto dt_ref e hash_linha
    que sao adicionados pelo orquestrador):
      num_contrato, empresa, cod_obra, cod_fornecedor, objeto,
      dt_assinatura, dt_inicio, dt_fim,
      valor_original, valor_aditivos, valor_total,
      total_medido, saldo,
      tipo_contrato, status
    """
    if df.empty:
        return df

    # Extrai por posicao
    raw = df.iloc[:, [COL[k] for k in COL]].copy()
    raw.columns = list(COL.keys())

    # Separa codigos compostos (empresa, obra)
    obra_split = raw["obra_str"].apply(_split_codigo_nome)

    out = pd.DataFrame({
        "num_contrato": raw["contrato"].apply(_str_clean),
        "empresa": None,  # identifica o robo (TOP/HABITAT/IMPULSI/...)
        "cod_obra": obra_split.apply(lambda t: t[0]),
        # Nome da obra (parseado da string "cod - nome"). Coluna prefixada com '_'
        # nao vai pro fato (upsert filtra pelas colunas do schema); o orquestrador
        # usa esse campo pra popular sienge.dim_obra automaticamente.
        "_nome_obra": obra_split.apply(lambda t: t[1]),
        "cod_fornecedor": raw["cod_fornecedor"].apply(
            lambda v: str(int(float(v))) if pd.notna(v) and str(v).strip() else None
        ),
        "objeto": raw["objeto"].apply(_str_clean),
        "dt_assinatura": raw["dt_contrato"].apply(_to_date),
        "dt_inicio": raw["dt_inicio"].apply(_to_date),
        "dt_fim": raw["dt_termino"].apply(_to_date),
        "valor_original": raw["total"].apply(_to_decimal),
        "valor_aditivos": None,  # nao exportado pelo Sienge neste relatorio
        "valor_total": raw["total"].apply(_to_decimal),
        "total_medido": raw["total_medido"].apply(_to_decimal),
        "saldo": raw["saldo"].apply(_to_decimal),
        "tipo_contrato": raw["tipo_contrato"].apply(_str_clean),
        "status": raw["situacao"].apply(_str_clean),
    })

    # Remove linhas onde a PK (num_contrato) ficou nula - subtotal/cabecalho.
    out = out[out["num_contrato"].notna()].reset_index(drop=True)

    return out
