"""Transformacoes por relatorio.

Cada modulo expoe `transformar(df, arquivo) -> DataFrame` que mapeia o Excel
do Sienge pras colunas da tabela destino.

A coluna `empresa` NAO precisa ser preenchida aqui - o IngestaoRunner adiciona
automaticamente baseado no parametro `empresa` do runner.
"""

from . import (
    apropriacao,
    contratos,
    pedidos_compra,
    solicitacoes,
    analitico_insumos,
    orcado_comprometido,
    medido_comprometido,
    mapa_controle,
)

__all__ = [
    "apropriacao",
    "contratos",
    "pedidos_compra",
    "solicitacoes",
    "analitico_insumos",
    "orcado_comprometido",
    "medido_comprometido",
    "mapa_controle",
]
