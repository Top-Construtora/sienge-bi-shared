-- Migration: adiciona colunas total_medido, saldo, tipo_contrato em fato_contratos
-- Aplicar via Supabase SQL Editor uma vez. Idempotente.
SET search_path TO sienge, public;

ALTER TABLE fato_contratos ADD COLUMN IF NOT EXISTS total_medido  NUMERIC(18,2);
ALTER TABLE fato_contratos ADD COLUMN IF NOT EXISTS saldo         NUMERIC(18,2);
ALTER TABLE fato_contratos ADD COLUMN IF NOT EXISTS tipo_contrato TEXT;
