-- Migration: expande fato_mapa_controle pra refletir as colunas REAIS do Excel
-- "MAPA DE CONTROLE - TOP.xlsx" (que na verdade eh "Relacao de Solicitacoes"
-- detalhada do Sienge). Quando o Painel de Compras destravar, adiciona PC/NF.
SET search_path TO sienge, public;

ALTER TABLE fato_mapa_controle
    ADD COLUMN IF NOT EXISTS num_solicitacao   TEXT,
    ADD COLUMN IF NOT EXISTS solicitante       TEXT,
    ADD COLUMN IF NOT EXISTS unidade           TEXT,
    ADD COLUMN IF NOT EXISTS dt_solicitacao    DATE,
    ADD COLUMN IF NOT EXISTS dt_autorizacao    DATE,
    ADD COLUMN IF NOT EXISTS dt_previsao       DATE,
    ADD COLUMN IF NOT EXISTS dt_atendimento    DATE,
    ADD COLUMN IF NOT EXISTS qtd_pendente      NUMERIC(18,4),
    ADD COLUMN IF NOT EXISTS qtd_atendida      NUMERIC(18,4),
    ADD COLUMN IF NOT EXISTS dif_dias          INTEGER,
    ADD COLUMN IF NOT EXISTS autorizado        TEXT,
    ADD COLUMN IF NOT EXISTS saldo_pendente    TEXT;
