"""Transformacao do relatorio 'RELATÓRIO_DE_APROPRIAÇÕES_DE_INSUMOS-*.xlsx'.

Schema destino: sienge.fato_analitico_insumos.
Granularidade: 1 linha por (obra, insumo, servico) com qtd e valor apropriado.

Estrutura do Excel (relatorio hierarquico, nao tabular):
  Linhas de header (Periodo, Obra, Unidade Construtiva, ...) e
  blocos aninhados: Celula Construtiva > Etapa > Subetapa > Servico > Insumos.
  Intercalados com linhas 'Total ...'.

Estrategia: iterar linhas, manter contexto (obra), extrair so linhas de insumo
(identificadas por col 0 = '<cod> - <descricao>' com cod numerico).
"""
import re
import pandas as pd


_PAT_COD_NOME = re.compile(r"^\s*(\d+)\s*-\s*(.+)$")


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


# Rotulos que indicam linha de Total/cabecalho-secao (ignorar)
ROTULOS_IGNORAR = {
    "Total do Serviço", "Total da Subetapa", "Total da Etapa",
    "Total da Célula Construtiva", "Total da Unidade Construtiva",
    "Total Geral", "Insumo",
}

# Rotulos de contexto (atualizam estado mas nao sao linha de dados)
ROTULOS_CONTEXTO = {
    "Obra": "obra",
    "Unidade Construtiva": "unidade",
    "Célula Construtiva": "celula",
    "Etapa": "etapa",
    "Subetapa": "subetapa",
    "Serviço": "servico",
}


def transformar(df: pd.DataFrame, arquivo: str | None = None) -> pd.DataFrame:
    """Parseia o Excel hierarquico de Apropriacao de Insumos."""
    if df.empty:
        return df

    estado = {
        "cod_obra": None, "nome_obra": None,
        "etapa": None, "subetapa": None, "servico": None,
    }
    rows = []

    for _, linha in df.iterrows():
        col0 = linha.iloc[0] if len(linha) > 0 else None
        col1 = linha.iloc[1] if len(linha) > 1 else None
        col4 = linha.iloc[4] if len(linha) > 4 else None
        col6 = linha.iloc[6] if len(linha) > 6 else None
        col10 = linha.iloc[10] if len(linha) > 10 else None

        s0 = None if pd.isna(col0) else str(col0).strip()
        if not s0:
            continue

        # Linhas de contexto: 'Obra', 'Etapa', etc - atualiza estado
        if s0 in ROTULOS_CONTEXTO:
            chave = ROTULOS_CONTEXTO[s0]
            cod, nome = _parse_cod_nome(col1)
            if chave == "obra":
                estado["cod_obra"] = cod
                estado["nome_obra"] = nome
            elif chave == "etapa":
                estado["etapa"] = f"{cod} - {nome}" if cod else (nome or str(col1))
            elif chave == "subetapa":
                estado["subetapa"] = f"{cod} - {nome}" if cod else (nome or str(col1))
            elif chave == "servico":
                estado["servico"] = f"{cod} - {nome}" if cod else (nome or str(col1))
            continue

        # Linha de Total ou linha 'Insumo' (header da secao) - pular
        if s0 in ROTULOS_IGNORAR or s0.startswith("Total"):
            continue

        # Linhas de dados de insumo: 'cod - nome' em col0
        cod_insumo, descricao = _parse_cod_nome(col0)
        if cod_insumo is None:
            continue

        qtd_apropriada = _safe_num(col6)
        valor_apropriado = _safe_num(col10)
        if qtd_apropriada is None and valor_apropriado is None:
            continue

        rows.append({
            "empresa": None,
            "cod_obra": estado["cod_obra"],
            "cod_insumo": cod_insumo,
            "descricao": descricao,
            "unidade": None if pd.isna(col4) else str(col4).strip(),
            "qtd_apropriada": qtd_apropriada or 0,
            "valor_apropriado": valor_apropriado or 0,
        })

    if not rows:
        return pd.DataFrame()

    import os as _os
    df_rows = pd.DataFrame(rows)
    # Agrega 1 linha por (obra, insumo) DENTRO do arquivo (soma qtd e valor).
    # Entre arquivos da mesma obra (variantes BDI, FAT DIRETO etc), preservamos
    # separacao via _arquivo (entra no hash de identidade, nao persiste no banco).
    agg = (df_rows
           .groupby(["cod_obra", "cod_insumo"], dropna=False, as_index=False)
           .agg(empresa=("empresa", "first"),
                descricao=("descricao", "first"),
                unidade=("unidade", "first"),
                qtd_apropriada=("qtd_apropriada", "sum"),
                valor_apropriado=("valor_apropriado", "sum")))
    agg["_arquivo"] = _os.path.basename(arquivo) if arquivo else ""
    return agg[
        ["empresa", "cod_obra", "cod_insumo", "descricao", "unidade",
         "qtd_apropriada", "valor_apropriado", "_arquivo"]
    ]
