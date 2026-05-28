-- Migration: fato_mapa_controle reescrito pro relatorio integrado SC+PC+NF
-- O Sienge exporta um unico Excel ("sienge_relatorio-*.xlsx") com a cadeia
-- inteira de cada item. Substituimos o schema antigo (que so tinha SC) por
-- um schema completo. Como nao houve ingestao real ainda do mapa, drop +
-- create eh seguro.
--
-- Data: 2026-05-27

DROP TABLE IF EXISTS sienge.fato_mapa_controle CASCADE;

CREATE TABLE sienge.fato_mapa_controle (
    dt_ref                       DATE NOT NULL,
    empresa                      TEXT,

    -- Solicitacao de Compra (SC)
    num_solicitacao              TEXT,
    cod_obra                     TEXT,
    cod_insumo                   TEXT,
    descricao_insumo             TEXT,
    cod_grupo                    TEXT,
    nome_grupo                   TEXT,
    comprador_distribuido        TEXT,
    detalhe                      TEXT,
    marca                        TEXT,
    qtd_solicitada               NUMERIC(18,4),
    unidade                      TEXT,
    dt_solicitacao               DATE,
    solicitante                  TEXT,
    situacao_solicitacao         TEXT,
    dt_chegada_obra              DATE,
    dt_autorizacao_sc            DATE,
    situacao_autorizacao_item    TEXT,

    -- Pedido de Compra (PC)
    num_pedido                   TEXT,
    dt_pedido                    DATE,
    situacao_pedido              TEXT,
    comprador                    TEXT,
    cod_fornecedor               TEXT,
    nome_fornecedor              TEXT,
    dt_previsao_entrega          DATE,
    dt_autorizacao_pc            DATE,
    situacao_autorizacao_pedido  TEXT,
    qtd_entregue                 NUMERIC(18,4),
    saldo                        NUMERIC(18,4),

    -- Nota Fiscal (NF) + entrega
    dt_nf                        DATE,
    num_nf                       TEXT,
    valor_nf                     NUMERIC(18,2),
    chave_nfe                    TEXT,
    num_parcelas                 INT,
    situacao_pagamento           TEXT,
    dt_entrega_obra              DATE,

    -- SLAs ja calculados (em dias) - simplifica consultas e graficos
    sla_geral                    INT,  -- dt_entrega_obra - dt_solicitacao
    sla_sc_pc                    INT,  -- dt_pedido       - dt_solicitacao
    sla_pc_nf                    INT,  -- dt_nf           - dt_pedido
    sla_nf_entrega               INT,  -- dt_entrega_obra - dt_nf

    hash_linha                   TEXT NOT NULL,
    PRIMARY KEY (dt_ref, hash_linha)
);

CREATE INDEX idx_mapa_empresa_dt    ON sienge.fato_mapa_controle (empresa, dt_solicitacao);
CREATE INDEX idx_mapa_obra          ON sienge.fato_mapa_controle (empresa, cod_obra);
CREATE INDEX idx_mapa_num_sc        ON sienge.fato_mapa_controle (empresa, num_solicitacao);
CREATE INDEX idx_mapa_dt_pedido     ON sienge.fato_mapa_controle (dt_pedido);
CREATE INDEX idx_mapa_dt_nf         ON sienge.fato_mapa_controle (dt_nf);
