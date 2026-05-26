-- Schema bi.*: camada agregada/consumível pelo dashboard.
-- Materialized views derivadas das tabelas sienge.fato_* (raw).
-- Refresh esperado após cada ingest (ver pipelines.ingestao.executar).

CREATE SCHEMA IF NOT EXISTS bi;
SET search_path TO bi, sienge, public;

-- ============================================================================
-- DIM: empresas e obras (pra slicers)
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS bi.dim_empresas AS
SELECT DISTINCT empresa
FROM sienge.fato_contratos
WHERE empresa IS NOT NULL AND empresa <> ''
UNION
SELECT DISTINCT empresa FROM sienge.fato_pedidos_compra WHERE empresa IS NOT NULL AND empresa <> ''
UNION
SELECT DISTINCT empresa FROM sienge.fato_apropriacao WHERE empresa IS NOT NULL AND empresa <> ''
UNION
SELECT DISTINCT empresa FROM sienge.fato_analitico_insumos WHERE empresa IS NOT NULL AND empresa <> ''
ORDER BY empresa;
CREATE UNIQUE INDEX IF NOT EXISTS idx_bi_empresas ON bi.dim_empresas (empresa);

CREATE MATERIALIZED VIEW IF NOT EXISTS bi.dim_obras AS
SELECT DISTINCT empresa, cod_obra
FROM (
    SELECT empresa, NULLIF(NULLIF(cod_obra, 'NaN'), '') AS cod_obra FROM sienge.fato_contratos
    UNION
    SELECT empresa, NULLIF(NULLIF(cod_obra, 'NaN'), '') FROM sienge.fato_pedidos_compra
    UNION
    SELECT empresa, NULLIF(NULLIF(cod_obra, 'NaN'), '') FROM sienge.fato_apropriacao
    UNION
    SELECT empresa, NULLIF(NULLIF(cod_obra, 'NaN'), '') FROM sienge.fato_analitico_insumos
    UNION
    SELECT empresa, NULLIF(NULLIF(cod_obra, 'NaN'), '') FROM sienge.fato_medido_comprometido
) t
WHERE empresa IS NOT NULL AND cod_obra IS NOT NULL
ORDER BY empresa, cod_obra;
CREATE UNIQUE INDEX IF NOT EXISTS idx_bi_obras ON bi.dim_obras (empresa, cod_obra);

-- ============================================================================
-- CONTRATOS (tela 1)
-- 1 linha por contrato com status calculado (replica DAX do PBI)
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS bi.contratos AS
SELECT
    c.empresa,
    c.num_contrato,
    c.objeto,
    NULLIF(NULLIF(c.cod_obra, 'NaN'), '')        AS cod_obra,
    NULLIF(NULLIF(c.cod_fornecedor, 'NaN'), '')  AS cod_fornecedor,
    c.dt_assinatura,
    c.dt_inicio,
    c.dt_fim,
    c.valor_total::float                          AS valor_total,
    c.total_medido::float                         AS total_medido,
    c.saldo::float                                AS saldo,
    c.tipo_contrato,
    c.status                                      AS status_raw,
    CASE
        WHEN c.dt_fim IS NULL THEN c.status
        WHEN c.dt_fim < CURRENT_DATE AND COALESCE(c.saldo, 0) > 0
            THEN 'Contrato vencido com saldo'
        WHEN c.dt_fim BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
             AND COALESCE(c.saldo, 0) > 0
            THEN 'Contrato com vencimento proximo'
        ELSE c.status
    END                                           AS status_contrato,
    CASE WHEN COALESCE(c.valor_total, 0) > 0
         THEN (c.total_medido / c.valor_total)::float
         ELSE NULL
    END                                           AS pct_contrato
FROM sienge.fato_contratos c
WHERE c.dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_contratos WHERE empresa = c.empresa);
CREATE INDEX IF NOT EXISTS idx_bi_contratos_emp_obra ON bi.contratos (empresa, cod_obra);
CREATE INDEX IF NOT EXISTS idx_bi_contratos_status ON bi.contratos (status_contrato);

-- ============================================================================
-- PEDIDOS DE COMPRA (telas 2, 3, 7, 8, 10)
-- 1 linha por pedido com faixa de valor pre-calculada
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS bi.pedidos_compra AS
WITH agregado AS (
    SELECT
        p.empresa,
        p.num_pedido,
        NULLIF(NULLIF(p.cod_obra, 'NaN'), '')        AS cod_obra,
        NULLIF(NULLIF(p.cod_fornecedor, 'NaN'), '')  AS cod_fornecedor,
        COALESCE(NULLIF(p.nome_fornecedor, ''), '(sem fornecedor)') AS nome_fornecedor,
        p.comprador,
        p.departamento,
        p.centro_custo,
        p.status,
        p.dt_emissao,
        SUM(CASE WHEN p.valor_total IS NOT NULL
                      AND NOT (p.valor_total = 'NaN'::numeric)
                 THEN p.valor_total END)::float AS valor_total
    FROM sienge.fato_pedidos_compra p
    WHERE p.dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_pedidos_compra WHERE empresa = p.empresa)
    GROUP BY p.empresa, p.num_pedido, p.cod_obra, p.cod_fornecedor, p.nome_fornecedor,
             p.comprador, p.departamento, p.centro_custo, p.status, p.dt_emissao
)
SELECT *,
    CASE
        WHEN valor_total IS NULL OR valor_total < 1000 THEN '<1K'
        WHEN valor_total >= 10000 THEN '>10K'
        WHEN valor_total >= 5000  THEN '5K-10K'
        ELSE '1K-5K'
    END                                              AS faixa_valor,
    EXTRACT(YEAR FROM dt_emissao)::int               AS ano_emissao,
    TO_CHAR(date_trunc('month', dt_emissao), 'YYYY-MM') AS mes_emissao
FROM agregado;
CREATE INDEX IF NOT EXISTS idx_bi_pedidos_emp ON bi.pedidos_compra (empresa);
CREATE INDEX IF NOT EXISTS idx_bi_pedidos_obra ON bi.pedidos_compra (empresa, cod_obra);
CREATE INDEX IF NOT EXISTS idx_bi_pedidos_faixa ON bi.pedidos_compra (faixa_valor);
CREATE INDEX IF NOT EXISTS idx_bi_pedidos_mes ON bi.pedidos_compra (mes_emissao);

-- ============================================================================
-- MEDIDO COMPROMETIDO (tela 4)
-- Hierarquia cod_servico (nivel = num de pontos) com valores cast pra float
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS bi.medido_comprometido AS
SELECT
    m.empresa,
    NULLIF(NULLIF(m.cod_obra, 'NaN'), '') AS cod_obra,
    m.cod_servico,
    (LENGTH(m.cod_servico) - LENGTH(REPLACE(m.cod_servico, '.', '')))::int AS nivel,
    m.descricao,
    m.valor_orcado::float                                AS valor_orcado,
    m.valor_medido::float                                AS valor_medido,
    m.valor_comprometido::float                          AS valor_comprometido,
    m.valor_estoque::float                               AS valor_estoque,
    m.saldo_executar::float                              AS saldo_executar,
    m.saldo_agregado::float                              AS saldo_agregado,
    m.percentual_medido::float                           AS pct_medido,
    m.percentual_comprometido_medido::float              AS pct_comp_med,
    m.percentual_comprometido_medido_estoque::float      AS pct_comp_med_est
FROM sienge.fato_medido_comprometido m
WHERE m.dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_medido_comprometido WHERE empresa = m.empresa);
CREATE INDEX IF NOT EXISTS idx_bi_medcomp_emp_obra ON bi.medido_comprometido (empresa, cod_obra);
CREATE INDEX IF NOT EXISTS idx_bi_medcomp_nivel ON bi.medido_comprometido (nivel);

-- ============================================================================
-- APROPRIACAO - MENSAL (telas 5, 6, 11)
-- Agregada por UC > Etapa > Subetapa > Servico × Mes, dt_emissao e dt_vencimento
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS bi.apropriacao_emissao_mensal AS
SELECT
    a.empresa,
    a.unidade_construtiva                                          AS uc,
    COALESCE(NULLIF(a.etapa, ''), 'Sem etapa')                     AS etapa,
    COALESCE(NULLIF(a.subetapa, ''), 'Sem subetapa')               AS subetapa,
    a.cod_servico,
    a.descricao_servico,
    a.tipo_or,
    TO_CHAR(date_trunc('month', a.dt_emissao), 'YYYY-MM')          AS mes,
    SUM(a.valor)::float                                            AS valor
FROM sienge.fato_apropriacao a
WHERE a.dt_emissao IS NOT NULL
  AND a.unidade_construtiva IS NOT NULL AND a.unidade_construtiva <> ''
  AND a.dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_apropriacao WHERE empresa = a.empresa)
GROUP BY a.empresa, a.unidade_construtiva, a.etapa, a.subetapa,
         a.cod_servico, a.descricao_servico, a.tipo_or, mes;
CREATE INDEX IF NOT EXISTS idx_bi_aprop_em_emp_mes ON bi.apropriacao_emissao_mensal (empresa, mes);
CREATE INDEX IF NOT EXISTS idx_bi_aprop_em_uc ON bi.apropriacao_emissao_mensal (uc);

CREATE MATERIALIZED VIEW IF NOT EXISTS bi.apropriacao_vencimento_mensal AS
SELECT
    a.empresa,
    a.unidade_construtiva                                          AS uc,
    COALESCE(NULLIF(a.etapa, ''), 'Sem etapa')                     AS etapa,
    COALESCE(NULLIF(a.subetapa, ''), 'Sem subetapa')               AS subetapa,
    a.cod_servico,
    a.descricao_servico,
    a.tipo_or,
    TO_CHAR(date_trunc('month', a.dt_vencimento), 'YYYY-MM')       AS mes,
    SUM(a.valor)::float                                            AS valor,
    -- pra calcular vencidos no backend:
    BOOL_OR(a.dt_vencimento < CURRENT_DATE)                        AS tem_vencido
FROM sienge.fato_apropriacao a
WHERE a.dt_vencimento IS NOT NULL
  AND a.dt_emissao IS NULL  -- linhas que vieram do relatorio de Vencimento
  AND a.unidade_construtiva IS NOT NULL AND a.unidade_construtiva <> ''
  AND a.dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_apropriacao WHERE empresa = a.empresa)
GROUP BY a.empresa, a.unidade_construtiva, a.etapa, a.subetapa,
         a.cod_servico, a.descricao_servico, a.tipo_or, mes;
CREATE INDEX IF NOT EXISTS idx_bi_aprop_vc_emp_mes ON bi.apropriacao_vencimento_mensal (empresa, mes);

-- ============================================================================
-- APROPRIACAO - DETALHE (tela 5, 6 - tabela de baixo)
-- Linhas individuais (nao agregadas) pra exibir credor/historico/valor/doc
-- ============================================================================

-- VIEW (nao materialized) pra evitar duplicar ~100MB de observacoes longas.
-- A query é simples (filtro por empresa) — view comum tem perf similar.
CREATE OR REPLACE VIEW bi.apropriacao_detalhe AS
SELECT
    a.empresa,
    NULLIF(NULLIF(a.cod_obra, 'NaN'), '')        AS cod_obra,
    a.unidade_construtiva                         AS uc,
    a.cod_servico,
    a.descricao_servico,
    a.tipo_or,
    a.documento,
    a.titulo_parcela,
    a.historico,
    a.dt_emissao,
    a.dt_vencimento,
    a.valor::float                                AS valor,
    a.valor_documento::float                      AS valor_documento,
    a.observacao,
    CASE
        WHEN a.dt_emissao IS NOT NULL THEN 'Emissao'
        WHEN a.dt_vencimento IS NOT NULL THEN 'Vencimento'
        ELSE 'Outro'
    END                                           AS origem
FROM sienge.fato_apropriacao a
WHERE a.dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_apropriacao WHERE empresa = a.empresa);
-- VIEW (nao materialized) nao aceita indices — eles ficam em sienge.fato_apropriacao

-- ============================================================================
-- INSUMOS APROPRIACAO (tela 9)
-- Hierarquia Insumo > Servico com qtd/valor orcado x apropriado
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS bi.insumos_apropriacao AS
SELECT
    i.empresa,
    NULLIF(NULLIF(i.cod_obra, 'NaN'), '')        AS cod_obra,
    i.unidade_construtiva                         AS uc,
    i.cod_servico,
    i.descricao_servico,
    i.cod_insumo,
    i.descricao,
    i.unidade,
    COALESCE(i.qtd_orcada, 0)::float              AS qtd_orcada,
    COALESCE(i.qtd_apropriada, 0)::float          AS qtd_apropriada,
    COALESCE(i.valor_orcado, 0)::float            AS valor_orcado,
    COALESCE(i.valor_apropriado, 0)::float        AS valor_apropriado,
    -- Calculados
    CASE WHEN COALESCE(i.qtd_orcada, 0) > 0
         THEN (i.valor_orcado / i.qtd_orcada)::float
         ELSE 0 END                               AS vunit_orcado,
    CASE WHEN COALESCE(i.qtd_apropriada, 0) > 0
         THEN (i.valor_apropriado / i.qtd_apropriada)::float
         ELSE 0 END                               AS vunit_apropriado
FROM sienge.fato_analitico_insumos i
WHERE i.cod_servico IS NOT NULL AND i.cod_servico <> ''
  AND i.dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_analitico_insumos WHERE empresa = i.empresa);
CREATE INDEX IF NOT EXISTS idx_bi_insumos_emp ON bi.insumos_apropriacao (empresa);
CREATE INDEX IF NOT EXISTS idx_bi_insumos_obra ON bi.insumos_apropriacao (empresa, cod_obra);
CREATE INDEX IF NOT EXISTS idx_bi_insumos_cod ON bi.insumos_apropriacao (cod_insumo);

-- ============================================================================
-- METADADOS - data da ultima atualizacao por dominio (pra rodape do dashboard)
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS bi.ultima_atualizacao AS
SELECT 'contratos' AS dominio, empresa, MAX(dt_ref) AS dt_ref FROM sienge.fato_contratos GROUP BY empresa
UNION ALL
SELECT 'pedidos_compra', empresa, MAX(dt_ref) FROM sienge.fato_pedidos_compra GROUP BY empresa
UNION ALL
SELECT 'apropriacao', empresa, MAX(dt_ref) FROM sienge.fato_apropriacao GROUP BY empresa
UNION ALL
SELECT 'medido_comprometido', empresa, MAX(dt_ref) FROM sienge.fato_medido_comprometido GROUP BY empresa
UNION ALL
SELECT 'analitico_insumos', empresa, MAX(dt_ref) FROM sienge.fato_analitico_insumos GROUP BY empresa;
CREATE INDEX IF NOT EXISTS idx_bi_ult_atu ON bi.ultima_atualizacao (dominio, empresa);
