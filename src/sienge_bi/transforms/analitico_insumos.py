"""Transformacao do relatorio 'RELATÓRIO_DE_APROPRIAÇÕES_DE_INSUMOS-*.xlsx'.

Schema destino: sienge.fato_analitico_insumos.
Granularidade: 1 linha por (obra, servico, insumo) com qtd e valor (Orcado /
Apropriado / Consumido).

Estrutura do Excel (relatorio hierarquico, nao tabular):
  L0+ headers: Periodo, Obra, Unidade Construtiva, Correcao
  Bloco aninhado: Celula Construtiva > Etapa > Subetapa > Servico > Insumos
  Cabecalho da tabela de insumos:
    col 0: Insumo  | col 4: Un.
    cols 5..7: Quantidades (Orcado, Apropriado, Consumido)
    cols 9..11: Valores (Orcado, Apropriado, Consumido)
  Linhas intercaladas: 'Total do Servico', 'Total da Subetapa', etc — pular.
"""
import os
import re
import pandas as pd


_PAT_COD_NOME = re.compile(r"^\s*(\d+)\s*-\s*(.+)$")
_PAT_COD_NOME_PONTOS = re.compile(r"^\s*([\d.]+)\s*-?\s*(.*)$")


def _parse_cod_nome(s):
    if pd.isna(s):
        return (None, None)
    m = _PAT_COD_NOME.match(str(s).strip())
    if m:
        return (m.group(1), m.group(2).strip())
    return (None, None)


def _parse_cod_nome_pontos(s):
    """Parser pra codigos hierarquicos tipo '01.001.001.001 Coordenacao...'."""
    if pd.isna(s):
        return (None, None)
    txt = str(s).strip()
    m = _PAT_COD_NOME_PONTOS.match(txt)
    if m and m.group(1):
        return (m.group(1), m.group(2).strip() if m.group(2) else None)
    return (None, txt)


def _safe_num(v):
    if pd.isna(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


ROTULOS_IGNORAR = {
    "Total do Serviço", "Total da Subetapa", "Total da Etapa",
    "Total da Célula Construtiva", "Total da Unidade Construtiva",
    "Total Geral", "Insumo",
}

ROTULOS_CONTEXTO = {
    "Obra": "obra",
    "Unidade Construtiva": "unidade_construtiva",
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
        "cod_obra": None,
        "nome_obra": None,
        "unidade_construtiva": None,
        "celula": None,
        "etapa": None,
        "subetapa": None,
        "cod_servico": None,
        "descricao_servico": None,
    }
    rows = []

    for _, linha in df.iterrows():
        col0 = linha.iloc[0] if len(linha) > 0 else None
        col1 = linha.iloc[1] if len(linha) > 1 else None
        col4 = linha.iloc[4] if len(linha) > 4 else None
        col5 = linha.iloc[5] if len(linha) > 5 else None
        col6 = linha.iloc[6] if len(linha) > 6 else None
        col7 = linha.iloc[7] if len(linha) > 7 else None
        col9 = linha.iloc[9] if len(linha) > 9 else None
        col10 = linha.iloc[10] if len(linha) > 10 else None
        col11 = linha.iloc[11] if len(linha) > 11 else None

        s0 = None if pd.isna(col0) else str(col0).strip()
        if not s0:
            continue

        # Linhas de contexto atualizam estado
        if s0 in ROTULOS_CONTEXTO:
            chave = ROTULOS_CONTEXTO[s0]
            if chave == "obra":
                cod, nome = _parse_cod_nome(col1)
                estado["cod_obra"] = cod
                estado["nome_obra"] = nome
            elif chave == "servico":
                cod, desc = _parse_cod_nome_pontos(col1)
                estado["cod_servico"] = cod
                estado["descricao_servico"] = desc
            else:
                # unidade_construtiva, celula, etapa, subetapa: guarda o texto
                # completo (cod + descricao) ou bruto se nao parsear
                if pd.isna(col1):
                    estado[chave] = None
                else:
                    cod, desc = _parse_cod_nome_pontos(col1)
                    estado[chave] = (
                        f"{cod} - {desc}" if cod and desc
                        else (desc or str(col1).strip())
                    )
            continue

        if s0 in ROTULOS_IGNORAR or s0.startswith("Total"):
            continue

        # Linha de dados de insumo: 'cod - nome' em col0
        cod_insumo, descricao = _parse_cod_nome(col0)
        if cod_insumo is None:
            continue

        qtd_orcada = _safe_num(col5)
        qtd_apropriada = _safe_num(col6)
        qtd_consumida = _safe_num(col7)
        valor_orcado = _safe_num(col9)
        valor_apropriado = _safe_num(col10)
        valor_consumido = _safe_num(col11)

        # Descarta linhas totalmente vazias
        if all(v is None for v in [qtd_orcada, qtd_apropriada, qtd_consumida,
                                    valor_orcado, valor_apropriado, valor_consumido]):
            continue

        rows.append({
            "empresa": None,
            "cod_obra": estado["cod_obra"],
            "_nome_obra": estado["nome_obra"],
            "unidade_construtiva": estado["unidade_construtiva"],
            "celula": estado["celula"],
            "etapa": estado["etapa"],
            "subetapa": estado["subetapa"],
            "cod_servico": estado["cod_servico"],
            "descricao_servico": estado["descricao_servico"],
            "cod_insumo": cod_insumo,
            "descricao": descricao,
            "unidade": None if pd.isna(col4) else str(col4).strip(),
            "qtd_orcada": qtd_orcada or 0,
            "qtd_apropriada": qtd_apropriada or 0,
            "qtd_consumida": qtd_consumida or 0,
            "valor_orcado": valor_orcado or 0,
            "valor_apropriado": valor_apropriado or 0,
            "valor_consumido": valor_consumido or 0,
        })

    if not rows:
        return pd.DataFrame()

    df_rows = pd.DataFrame(rows)
    # Agrega 1 linha por (obra, servico, insumo) — mantem servico no group
    # porque o mesmo insumo pode aparecer em servicos diferentes da mesma obra
    # com qtd/valor distintos
    agg_cols = ["cod_obra", "cod_servico", "cod_insumo"]
    agg = (df_rows
           .groupby(agg_cols, dropna=False, as_index=False)
           .agg(
               empresa=("empresa", "first"),
               unidade_construtiva=("unidade_construtiva", "first"),
               celula=("celula", "first"),
               etapa=("etapa", "first"),
               subetapa=("subetapa", "first"),
               descricao_servico=("descricao_servico", "first"),
               descricao=("descricao", "first"),
               unidade=("unidade", "first"),
               qtd_orcada=("qtd_orcada", "sum"),
               qtd_apropriada=("qtd_apropriada", "sum"),
               qtd_consumida=("qtd_consumida", "sum"),
               valor_orcado=("valor_orcado", "sum"),
               valor_apropriado=("valor_apropriado", "sum"),
               valor_consumido=("valor_consumido", "sum"),
           ))
    agg["_arquivo"] = os.path.basename(arquivo) if arquivo else ""
    return agg[
        ["empresa", "cod_obra", "unidade_construtiva", "celula", "etapa",
         "subetapa", "cod_servico", "descricao_servico", "cod_insumo",
         "descricao", "unidade", "qtd_orcada", "qtd_apropriada", "qtd_consumida",
         "valor_orcado", "valor_apropriado", "valor_consumido", "_arquivo"]
    ]
