-- Migration: adiciona campos da Apropriacao usados pelo PBI mas nao capturados
-- antes pelo transform (unidade construtiva, celula, etapa, subetapa, titulo,
-- valor do documento, observacao). Necessario pra replicar a tela
-- "ENG / AnaltAprop_Emissao" do PBI TOPGERAL no Streamlit.
SET search_path TO sienge, public;

ALTER TABLE fato_apropriacao
    ADD COLUMN IF NOT EXISTS unidade_construtiva  TEXT,
    ADD COLUMN IF NOT EXISTS celula               TEXT,
    ADD COLUMN IF NOT EXISTS etapa                TEXT,
    ADD COLUMN IF NOT EXISTS subetapa             TEXT,
    ADD COLUMN IF NOT EXISTS titulo_parcela       TEXT,
    ADD COLUMN IF NOT EXISTS valor_documento      NUMERIC(18,2),
    ADD COLUMN IF NOT EXISTS observacao           TEXT;
