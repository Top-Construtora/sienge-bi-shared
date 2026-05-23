-- Migration: adiciona colunas extras em fato_medido_comprometido
-- (valor_orcado, valor_estoque, saldo_executar, saldo_agregado,
--  percentual_medido, percentual_comprometido_medido,
--  percentual_comprometido_medido_estoque)
-- pra replicar a pagina MedComp do PowerBI fielmente.
SET search_path TO sienge, public;

ALTER TABLE fato_medido_comprometido ADD COLUMN IF NOT EXISTS valor_orcado    NUMERIC(18,2);
ALTER TABLE fato_medido_comprometido ADD COLUMN IF NOT EXISTS valor_estoque   NUMERIC(18,2);
ALTER TABLE fato_medido_comprometido ADD COLUMN IF NOT EXISTS saldo_executar  NUMERIC(18,2);
ALTER TABLE fato_medido_comprometido ADD COLUMN IF NOT EXISTS saldo_agregado  NUMERIC(18,2);
ALTER TABLE fato_medido_comprometido ADD COLUMN IF NOT EXISTS percentual_medido                      NUMERIC(7,4);
ALTER TABLE fato_medido_comprometido ADD COLUMN IF NOT EXISTS percentual_comprometido_medido         NUMERIC(7,4);
ALTER TABLE fato_medido_comprometido ADD COLUMN IF NOT EXISTS percentual_comprometido_medido_estoque NUMERIC(7,4);
