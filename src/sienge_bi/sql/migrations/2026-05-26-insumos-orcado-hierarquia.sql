-- Migration: adiciona campos faltantes em fato_analitico_insumos.
-- O Excel "RELATORIO_DE_APROPRIACOES_DE_INSUMOS" tem qtd/valor Orcado, Apropriado
-- e Consumido, alem dos contextos UC/Celula/Etapa/Subetapa/Servico. O transform
-- so capturava apropriado (col 6 e 10) e descartava o resto.
-- Necessario pra replicar a tela "Aprop_Insumos" do PBI com semaforo verde/vermelho
-- (comparacao orcado x apropriado) e hierarquia Servico > Insumo.
SET search_path TO sienge, public;

ALTER TABLE fato_analitico_insumos
    ADD COLUMN IF NOT EXISTS unidade_construtiva  TEXT,
    ADD COLUMN IF NOT EXISTS celula               TEXT,
    ADD COLUMN IF NOT EXISTS etapa                TEXT,
    ADD COLUMN IF NOT EXISTS subetapa             TEXT,
    ADD COLUMN IF NOT EXISTS cod_servico          TEXT,
    ADD COLUMN IF NOT EXISTS descricao_servico    TEXT,
    ADD COLUMN IF NOT EXISTS qtd_orcada           NUMERIC(18,4),
    ADD COLUMN IF NOT EXISTS qtd_consumida        NUMERIC(18,4),
    ADD COLUMN IF NOT EXISTS valor_orcado         NUMERIC(18,2),
    ADD COLUMN IF NOT EXISTS valor_consumido      NUMERIC(18,2);
