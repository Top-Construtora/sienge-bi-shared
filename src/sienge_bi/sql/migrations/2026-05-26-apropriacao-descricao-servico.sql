-- Migration: adiciona descricao_servico em fato_apropriacao.
-- A col 9 do Excel ('Servico') vem como "01.002.000.004 - Despesas com CREA".
-- O transform ja separava em cod_servico (codigo) + descricao (texto), mas a
-- descricao estava sendo descartada. Necessario pra construir a hierarquia
-- de 4 niveis no Streamlit (UC > Etapa > Subetapa > Servico analitico).
SET search_path TO sienge, public;

ALTER TABLE fato_apropriacao
    ADD COLUMN IF NOT EXISTS descricao_servico TEXT;
