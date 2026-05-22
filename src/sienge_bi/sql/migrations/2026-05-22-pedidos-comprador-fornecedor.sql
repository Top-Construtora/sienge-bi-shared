-- Migration: adiciona colunas extras em fato_pedidos_compra
-- (nome_fornecedor, total_pendente, total_entregue, comprador,
--  departamento, centro_custo) para replicar o PowerBI fielmente.
-- Aplicar via Supabase SQL Editor. Idempotente.
SET search_path TO sienge, public;

ALTER TABLE fato_pedidos_compra ADD COLUMN IF NOT EXISTS nome_fornecedor TEXT;
ALTER TABLE fato_pedidos_compra ADD COLUMN IF NOT EXISTS total_pendente  NUMERIC(18,2);
ALTER TABLE fato_pedidos_compra ADD COLUMN IF NOT EXISTS total_entregue  NUMERIC(18,2);
ALTER TABLE fato_pedidos_compra ADD COLUMN IF NOT EXISTS comprador       TEXT;
ALTER TABLE fato_pedidos_compra ADD COLUMN IF NOT EXISTS departamento    TEXT;
ALTER TABLE fato_pedidos_compra ADD COLUMN IF NOT EXISTS centro_custo    TEXT;
