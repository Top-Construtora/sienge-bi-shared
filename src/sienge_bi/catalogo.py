"""Modelo de catalogo de relatorios: cada repo declara seus Relatorio's
e passa pro IngestaoRunner."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional
import pandas as pd


@dataclass
class Relatorio:
    """Configuracao de um relatorio para ingestao.

    Campos:
        nome: identificador (vai pro log_ingestao). Ex: "contratos", "apropriacao_emissao".
        pasta: diretorio onde o Excel foi salvo pelo RPA.
        padrao_nome: prefixo do nome do arquivo (sem extensao). Glob '<padrao>*.xls*'.
        transformar: funcao que recebe DataFrame + arquivo e devolve DataFrame com
                     colunas do schema da tabela (sem dt_ref e hash_linha).
        tabela: nome da tabela destino em sienge.<tabela>.
        colunas_identidade: colunas usadas pra calcular hash_linha (idempotencia).
                            dt_ref e empresa sao adicionados automaticamente.
        multi_arquivo: se True, ingere TODOS os arquivos que casam com padrao_nome
                       (caso de relatorios "1 arquivo por obra"). Default: False.
        skiprows: numero de linhas a pular no Excel antes do cabecalho (default 0).
    """
    nome: str
    pasta: str
    padrao_nome: str
    transformar: Callable[[pd.DataFrame, Optional[str]], pd.DataFrame]
    tabela: str
    colunas_identidade: List[str]
    multi_arquivo: bool = False
    skiprows: int = 0
    extra: dict = field(default_factory=dict)
