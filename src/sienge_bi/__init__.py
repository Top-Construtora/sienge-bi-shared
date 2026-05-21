"""sienge-bi — pipelines compartilhados de ingestao Sienge para o BI da TOP.

Uso tipico no repo de cada robo (ex: automacao-top, automacao-habitat):

    from sienge_bi import Relatorio, IngestaoRunner
    from sienge_bi.transforms import contratos, apropriacao, pedidos_compra

    RELATORIOS = [
        Relatorio(
            nome='contratos',
            pasta='/app/relatorios/engenharia',
            padrao_nome='Cadastros de Contratos-TOP',
            transformar=contratos.transformar,
            tabela='fato_contratos',
            colunas_identidade=['num_contrato'],
        ),
        # ...
    ]

    if __name__ == '__main__':
        IngestaoRunner(empresa='TOP', catalogo=RELATORIOS).executar()
"""

from .catalogo import Relatorio
from .ingestao import IngestaoRunner

__version__ = "0.1.0"
__all__ = ["Relatorio", "IngestaoRunner"]
