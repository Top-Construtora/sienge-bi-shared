-- Migration: adiciona num_acordo_preco em fato_pedidos_compra.
-- Permite derivar tipo_pedido na query (Contrato se acordo preenchido, senao Direto)
-- usado pelas telas ADM/Ped_Diretos R$/Qtd/Distribuicao.
SET search_path TO sienge, public;

ALTER TABLE fato_pedidos_compra
    ADD COLUMN IF NOT EXISTS num_acordo_preco   TEXT,
    ADD COLUMN IF NOT EXISTS num_versao_acordo  TEXT;
