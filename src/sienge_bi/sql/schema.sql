-- =============================================================================
-- Schema do banco de dados Sienge -> Supabase
-- Star schema: dimensoes compartilhadas + um fato por relatorio
-- Aplicar no SQL Editor do Supabase com role postgres
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Schemas
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS sienge;
SET search_path TO sienge, public;

-- -----------------------------------------------------------------------------
-- Tabela de log de ingestao
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_ingestao (
    id              BIGSERIAL PRIMARY KEY,
    dt_ref          DATE NOT NULL,
    relatorio       TEXT NOT NULL,
    arquivo         TEXT,
    linhas_lidas    INTEGER,
    linhas_inseridas INTEGER,
    linhas_atualizadas INTEGER,
    status          TEXT NOT NULL CHECK (status IN ('OK', 'ERRO', 'PARCIAL')),
    erro            TEXT,
    duracao_seg     NUMERIC,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_log_dt_ref ON log_ingestao (dt_ref DESC);
CREATE INDEX IF NOT EXISTS idx_log_relatorio ON log_ingestao (relatorio, dt_ref DESC);

-- -----------------------------------------------------------------------------
-- Dimensoes compartilhadas
-- -----------------------------------------------------------------------------
-- Obra: chave composta (empresa, cod_obra) porque o codigo se repete entre empresas.
CREATE TABLE IF NOT EXISTS dim_obra (
    empresa         TEXT NOT NULL,
    cod_obra        TEXT NOT NULL,
    nome_obra       TEXT NOT NULL,
    nome_completo   TEXT,
    cidade          TEXT,
    uf              TEXT,
    ativa           BOOLEAN DEFAULT TRUE,
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (empresa, cod_obra)
);
CREATE INDEX IF NOT EXISTS idx_obra_nome ON dim_obra (nome_obra);

CREATE TABLE IF NOT EXISTS dim_servico (
    cod_servico     TEXT PRIMARY KEY,
    nome_servico    TEXT NOT NULL,
    etapa           TEXT,
    subetapa        TEXT,
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dim_fornecedor (
    cod_fornecedor  TEXT PRIMARY KEY,
    nome_fornecedor TEXT NOT NULL,
    cnpj_cpf        TEXT,
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dim_centro_custo (
    cod_centro_custo TEXT PRIMARY KEY,
    nome_centro_custo TEXT NOT NULL,
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- INCC mensal (Indice Nacional de Custo da Construcao)
-- Web scraping mensal do Secovi-SP (republica dados oficiais da FGV).
-- Usado para correcao monetaria de valores apropriados.
CREATE TABLE IF NOT EXISTS dim_incc (
    data        DATE PRIMARY KEY,    -- primeiro dia do mes de referencia
    indice      NUMERIC(15,6) NOT NULL,
    variacao    NUMERIC(8,4),        -- variacao percentual mensal
    fonte       TEXT DEFAULT 'Secovi-SP / FGV',
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_incc_data ON dim_incc(data DESC);

-- -----------------------------------------------------------------------------
-- Fato: Analitico de Apropriacao
-- Granularidade: uma linha por lancamento de apropriacao (Or x obra x servico x data)
-- PK composta inclui dt_ref para permitir snapshots historicos
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_apropriacao (
    dt_ref               DATE NOT NULL,
    empresa              TEXT NOT NULL,
    cod_obra             TEXT NOT NULL,
    unidade_construtiva  TEXT,
    celula               TEXT,
    etapa                TEXT,
    subetapa             TEXT,
    cod_servico          TEXT,
    descricao_servico    TEXT,
    cod_fornecedor       TEXT,
    tipo_or              TEXT,            -- AC, ME, FP, etc
    dt_competencia       DATE,
    dt_emissao           DATE,
    dt_vencimento        DATE,
    documento            TEXT,
    titulo_parcela       TEXT,
    historico            TEXT,
    valor                NUMERIC(18,2),
    valor_documento      NUMERIC(18,2),
    quantidade           NUMERIC(18,4),
    observacao           TEXT,
    hash_linha           TEXT NOT NULL,   -- hash de identidade da linha (idempotencia)
    PRIMARY KEY (dt_ref, hash_linha),
    FOREIGN KEY (empresa, cod_obra) REFERENCES dim_obra(empresa, cod_obra) DEFERRABLE
);
CREATE INDEX IF NOT EXISTS idx_aprop_obra ON fato_apropriacao (empresa, cod_obra, dt_ref);
CREATE INDEX IF NOT EXISTS idx_aprop_competencia ON fato_apropriacao (dt_competencia);

-- -----------------------------------------------------------------------------
-- Fato: Contratos (Suprimentos)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_contratos (
    dt_ref          DATE NOT NULL,
    num_contrato    TEXT NOT NULL,
    empresa         TEXT,
    cod_obra        TEXT,
    cod_fornecedor  TEXT,
    objeto          TEXT,
    dt_assinatura   DATE,
    dt_inicio       DATE,
    dt_fim          DATE,
    valor_original  NUMERIC(18,2),
    valor_aditivos  NUMERIC(18,2),
    valor_total     NUMERIC(18,2),
    total_medido    NUMERIC(18,2),
    saldo           NUMERIC(18,2),
    tipo_contrato   TEXT,
    status          TEXT,
    hash_linha      TEXT NOT NULL,
    PRIMARY KEY (dt_ref, hash_linha)
);
CREATE INDEX IF NOT EXISTS idx_contratos_obra ON fato_contratos (empresa, cod_obra, dt_ref);

-- -----------------------------------------------------------------------------
-- Fato: Pedidos de Compra
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_pedidos_compra (
    dt_ref               DATE NOT NULL,
    num_pedido           TEXT NOT NULL,
    num_acordo_preco     TEXT,            -- col 1 do Excel; preenchido = pedido tem contrato
    num_versao_acordo    TEXT,
    empresa              TEXT,
    cod_obra             TEXT,
    cod_fornecedor       TEXT,
    nome_fornecedor      TEXT,
    cod_insumo           TEXT,
    descricao_insumo     TEXT,
    dt_emissao           DATE,
    dt_entrega           DATE,
    quantidade           NUMERIC(18,4),
    valor_unitario       NUMERIC(18,4),
    valor_total          NUMERIC(18,2),
    total_pendente       NUMERIC(18,2),
    total_entregue       NUMERIC(18,2),
    comprador            TEXT,
    departamento         TEXT,
    centro_custo         TEXT,
    status               TEXT,
    hash_linha           TEXT NOT NULL,
    PRIMARY KEY (dt_ref, hash_linha)
);

-- -----------------------------------------------------------------------------
-- Fato: Mapa de Controle
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_mapa_controle (
    dt_ref          DATE NOT NULL,
    empresa         TEXT,
    cod_obra        TEXT,
    cod_insumo      TEXT,
    descricao       TEXT,
    qtd_orcada      NUMERIC(18,4),
    qtd_comprada    NUMERIC(18,4),
    qtd_solicitada  NUMERIC(18,4),
    saldo           NUMERIC(18,4),
    hash_linha      TEXT NOT NULL,
    PRIMARY KEY (dt_ref, hash_linha)
);

-- -----------------------------------------------------------------------------
-- Fato: Orcado x Comprometido
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_orcado_comprometido (
    dt_ref          DATE NOT NULL,
    empresa         TEXT,
    cod_obra        TEXT,
    cod_servico     TEXT,
    descricao       TEXT,
    valor_orcado    NUMERIC(18,2),
    valor_comprometido NUMERIC(18,2),
    saldo           NUMERIC(18,2),
    percentual      NUMERIC(7,4),
    hash_linha      TEXT NOT NULL,
    PRIMARY KEY (dt_ref, hash_linha)
);

-- -----------------------------------------------------------------------------
-- Fato: Medido x Comprometido
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_medido_comprometido (
    dt_ref          DATE NOT NULL,
    empresa         TEXT,
    cod_obra        TEXT,
    cod_servico     TEXT,
    descricao       TEXT,
    valor_orcado    NUMERIC(18,2),
    valor_medido    NUMERIC(18,2),
    valor_comprometido NUMERIC(18,2),
    valor_estoque   NUMERIC(18,2),
    saldo_executar  NUMERIC(18,2),
    saldo_agregado  NUMERIC(18,2),
    percentual_medido                       NUMERIC(12,4),
    percentual_comprometido_medido          NUMERIC(12,4),
    percentual_comprometido_medido_estoque  NUMERIC(12,4),
    -- retrocompatibilidade:
    saldo           NUMERIC(18,2),
    percentual      NUMERIC(12,4),
    hash_linha      TEXT NOT NULL,
    PRIMARY KEY (dt_ref, hash_linha)
);

-- -----------------------------------------------------------------------------
-- Fato: Relacao de Solicitacoes
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_solicitacoes (
    dt_ref          DATE NOT NULL,
    num_solicitacao TEXT NOT NULL,
    empresa         TEXT,
    cod_obra        TEXT,
    cod_insumo      TEXT,
    descricao       TEXT,
    quantidade      NUMERIC(18,4),
    dt_solicitacao  DATE,
    dt_necessidade  DATE,
    status          TEXT,
    solicitante     TEXT,
    hash_linha      TEXT NOT NULL,
    PRIMARY KEY (dt_ref, hash_linha)
);

-- -----------------------------------------------------------------------------
-- Fato: Analitico de Insumos
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_analitico_insumos (
    dt_ref               DATE NOT NULL,
    empresa              TEXT,
    cod_obra             TEXT,
    unidade_construtiva  TEXT,
    celula               TEXT,
    etapa                TEXT,
    subetapa             TEXT,
    cod_servico          TEXT,
    descricao_servico    TEXT,
    cod_insumo           TEXT,
    descricao            TEXT,
    unidade              TEXT,
    qtd_orcada           NUMERIC(18,4),
    qtd_apropriada       NUMERIC(18,4),
    qtd_consumida        NUMERIC(18,4),
    valor_orcado         NUMERIC(18,2),
    valor_apropriado     NUMERIC(18,2),
    valor_consumido      NUMERIC(18,2),
    hash_linha           TEXT NOT NULL,
    PRIMARY KEY (dt_ref, hash_linha)
);

-- -----------------------------------------------------------------------------
-- Fato: Insumos por Centro de Custo
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_insumos_centro_custo (
    dt_ref          DATE NOT NULL,
    empresa         TEXT,
    cod_obra        TEXT,
    cod_centro_custo TEXT,
    cod_insumo      TEXT,
    descricao       TEXT,
    quantidade      NUMERIC(18,4),
    valor           NUMERIC(18,2),
    hash_linha      TEXT NOT NULL,
    PRIMARY KEY (dt_ref, hash_linha)
);

-- =============================================================================
-- Views de consumo (camada semantica)
-- =============================================================================

-- Snapshot mais recente de apropriacao
CREATE OR REPLACE VIEW vw_apropriacao_atual AS
WITH ultima AS (
    SELECT MAX(dt_ref) AS dt_ref FROM fato_apropriacao
)
SELECT f.*
FROM fato_apropriacao f
JOIN ultima u ON f.dt_ref = u.dt_ref;

-- Apropriacao mensal por etapa
CREATE OR REPLACE VIEW vw_apropriacao_mensal_por_etapa AS
SELECT
    DATE_TRUNC('month', f.dt_competencia)::DATE AS mes,
    f.empresa,
    f.cod_obra,
    o.nome_obra,
    s.etapa,
    SUM(f.valor) AS valor_total,
    COUNT(*) AS lancamentos
FROM fato_apropriacao f
LEFT JOIN dim_obra o ON o.empresa = f.empresa AND o.cod_obra = f.cod_obra
LEFT JOIN dim_servico s ON s.cod_servico = f.cod_servico
WHERE f.dt_ref = (SELECT MAX(dt_ref) FROM fato_apropriacao)
  AND f.dt_competencia <= CURRENT_DATE
GROUP BY 1, 2, 3, 4, 5;

-- Top credores
CREATE OR REPLACE VIEW vw_top_credores AS
SELECT
    f.cod_fornecedor,
    fo.nome_fornecedor,
    SUM(f.valor) AS valor_total
FROM fato_apropriacao f
LEFT JOIN dim_fornecedor fo ON fo.cod_fornecedor = f.cod_fornecedor
WHERE f.dt_ref = (SELECT MAX(dt_ref) FROM fato_apropriacao)
  AND f.dt_competencia <= CURRENT_DATE
GROUP BY 1, 2
ORDER BY valor_total DESC;

-- Status da ultima ingestao
CREATE OR REPLACE VIEW vw_ultima_ingestao AS
SELECT relatorio,
       MAX(dt_ref) AS ultima_dt_ref,
       (ARRAY_AGG(status ORDER BY criado_em DESC))[1] AS ultimo_status,
       (ARRAY_AGG(criado_em ORDER BY criado_em DESC))[1] AS ultima_execucao
FROM log_ingestao
GROUP BY relatorio;

-- =============================================================================
-- Row-Level Security (preparado - habilitar quando necessario)
-- =============================================================================
-- Exemplo de RLS por empresa: cada usuario so ve as obras da sua empresa.
-- Para habilitar, descomente e crie politicas:
--
-- ALTER TABLE fato_apropriacao ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY fato_apropriacao_por_empresa ON fato_apropriacao
--     FOR SELECT
--     USING (empresa = current_setting('app.empresa', true));

-- =============================================================================
-- Usuarios e permissoes (rodar separadamente como postgres)
-- =============================================================================
-- CREATE ROLE app_ingest LOGIN PASSWORD '...';
-- CREATE ROLE app_reader LOGIN PASSWORD '...';
--
-- GRANT USAGE ON SCHEMA sienge TO app_ingest, app_reader;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA sienge TO app_ingest;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA sienge TO app_ingest;
-- GRANT SELECT ON ALL TABLES IN SCHEMA sienge TO app_reader;
--
-- ALTER DEFAULT PRIVILEGES IN SCHEMA sienge GRANT SELECT ON TABLES TO app_reader;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA sienge GRANT SELECT, INSERT, UPDATE ON TABLES TO app_ingest;
