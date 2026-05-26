-- Helper pra limpar NaN no cast pra float
CREATE OR REPLACE FUNCTION bi.safe_float(v numeric) RETURNS float AS $$
  SELECT CASE WHEN v IS NULL OR v = 'NaN'::numeric THEN NULL ELSE v::float END;
$$ LANGUAGE SQL IMMUTABLE;

-- Recria views numericas usando safe_float

DROP MATERIALIZED VIEW IF EXISTS bi.contratos CASCADE;
CREATE MATERIALIZED VIEW bi.contratos AS
SELECT
    c.empresa,
    c.num_contrato,
    c.objeto,
    NULLIF(NULLIF(c.cod_obra, 'NaN'), '')        AS cod_obra,
    NULLIF(NULLIF(c.cod_fornecedor, 'NaN'), '')  AS cod_fornecedor,
    c.dt_assinatura,
    c.dt_inicio,
    c.dt_fim,
    bi.safe_float(c.valor_total)                  AS valor_total,
    bi.safe_float(c.total_medido)                 AS total_medido,
    bi.safe_float(c.saldo)                        AS saldo,
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
    CASE WHEN COALESCE(bi.safe_float(c.valor_total), 0) > 0
         THEN bi.safe_float(c.total_medido) / bi.safe_float(c.valor_total)
         ELSE NULL
    END                                           AS pct_contrato
FROM sienge.fato_contratos c
WHERE c.dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_contratos WHERE empresa = c.empresa);
CREATE INDEX idx_bi_contratos_emp_obra ON bi.contratos (empresa, cod_obra);
CREATE INDEX idx_bi_contratos_status ON bi.contratos (status_contrato);

-- Re-cria medido_comprometido com safe_float
DROP MATERIALIZED VIEW IF EXISTS bi.medido_comprometido CASCADE;
CREATE MATERIALIZED VIEW bi.medido_comprometido AS
SELECT
    m.empresa,
    NULLIF(NULLIF(m.cod_obra, 'NaN'), '') AS cod_obra,
    m.cod_servico,
    (LENGTH(m.cod_servico) - LENGTH(REPLACE(m.cod_servico, '.', '')))::int AS nivel,
    m.descricao,
    bi.safe_float(m.valor_orcado)                              AS valor_orcado,
    bi.safe_float(m.valor_medido)                              AS valor_medido,
    bi.safe_float(m.valor_comprometido)                        AS valor_comprometido,
    bi.safe_float(m.valor_estoque)                             AS valor_estoque,
    bi.safe_float(m.saldo_executar)                            AS saldo_executar,
    bi.safe_float(m.saldo_agregado)                            AS saldo_agregado,
    bi.safe_float(m.percentual_medido)                         AS pct_medido,
    bi.safe_float(m.percentual_comprometido_medido)            AS pct_comp_med,
    bi.safe_float(m.percentual_comprometido_medido_estoque)    AS pct_comp_med_est
FROM sienge.fato_medido_comprometido m
WHERE m.dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_medido_comprometido WHERE empresa = m.empresa);
CREATE INDEX idx_bi_medcomp_emp_obra ON bi.medido_comprometido (empresa, cod_obra);
CREATE INDEX idx_bi_medcomp_nivel ON bi.medido_comprometido (nivel);

-- Pedidos
DROP MATERIALIZED VIEW IF EXISTS bi.pedidos_compra CASCADE;
CREATE MATERIALIZED VIEW bi.pedidos_compra AS
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
        SUM(bi.safe_float(p.valor_total)) AS valor_total
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
CREATE INDEX idx_bi_pedidos_emp ON bi.pedidos_compra (empresa);
CREATE INDEX idx_bi_pedidos_obra ON bi.pedidos_compra (empresa, cod_obra);
CREATE INDEX idx_bi_pedidos_faixa ON bi.pedidos_compra (faixa_valor);
CREATE INDEX idx_bi_pedidos_mes ON bi.pedidos_compra (mes_emissao);

-- Apropriacao detalhe (com safe_float)
DROP MATERIALIZED VIEW IF EXISTS bi.apropriacao_detalhe CASCADE;
CREATE MATERIALIZED VIEW bi.apropriacao_detalhe AS
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
    bi.safe_float(a.valor)                        AS valor,
    bi.safe_float(a.valor_documento)              AS valor_documento,
    a.observacao,
    CASE
        WHEN a.dt_emissao IS NOT NULL THEN 'Emissao'
        WHEN a.dt_vencimento IS NOT NULL THEN 'Vencimento'
        ELSE 'Outro'
    END                                           AS origem
FROM sienge.fato_apropriacao a
WHERE a.dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_apropriacao WHERE empresa = a.empresa);
CREATE INDEX idx_bi_aprop_det_emp ON bi.apropriacao_detalhe (empresa);
CREATE INDEX idx_bi_aprop_det_obra ON bi.apropriacao_detalhe (empresa, cod_obra);
CREATE INDEX idx_bi_aprop_det_origem ON bi.apropriacao_detalhe (origem);
CREATE INDEX idx_bi_aprop_det_dt_em ON bi.apropriacao_detalhe (dt_emissao);
CREATE INDEX idx_bi_aprop_det_dt_vc ON bi.apropriacao_detalhe (dt_vencimento);

-- Apropriacao mensal (recria com safe)
DROP MATERIALIZED VIEW IF EXISTS bi.apropriacao_emissao_mensal CASCADE;
CREATE MATERIALIZED VIEW bi.apropriacao_emissao_mensal AS
SELECT
    a.empresa,
    a.unidade_construtiva                                          AS uc,
    COALESCE(NULLIF(a.etapa, ''), 'Sem etapa')                     AS etapa,
    COALESCE(NULLIF(a.subetapa, ''), 'Sem subetapa')               AS subetapa,
    a.cod_servico,
    a.descricao_servico,
    a.tipo_or,
    TO_CHAR(date_trunc('month', a.dt_emissao), 'YYYY-MM')          AS mes,
    SUM(bi.safe_float(a.valor))                                    AS valor
FROM sienge.fato_apropriacao a
WHERE a.dt_emissao IS NOT NULL
  AND a.unidade_construtiva IS NOT NULL AND a.unidade_construtiva <> ''
  AND a.dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_apropriacao WHERE empresa = a.empresa)
GROUP BY a.empresa, a.unidade_construtiva, a.etapa, a.subetapa,
         a.cod_servico, a.descricao_servico, a.tipo_or, mes;
CREATE INDEX idx_bi_aprop_em_emp_mes ON bi.apropriacao_emissao_mensal (empresa, mes);
CREATE INDEX idx_bi_aprop_em_uc ON bi.apropriacao_emissao_mensal (uc);

DROP MATERIALIZED VIEW IF EXISTS bi.apropriacao_vencimento_mensal CASCADE;
CREATE MATERIALIZED VIEW bi.apropriacao_vencimento_mensal AS
SELECT
    a.empresa,
    a.unidade_construtiva                                          AS uc,
    COALESCE(NULLIF(a.etapa, ''), 'Sem etapa')                     AS etapa,
    COALESCE(NULLIF(a.subetapa, ''), 'Sem subetapa')               AS subetapa,
    a.cod_servico,
    a.descricao_servico,
    a.tipo_or,
    TO_CHAR(date_trunc('month', a.dt_vencimento), 'YYYY-MM')       AS mes,
    SUM(bi.safe_float(a.valor))                                    AS valor,
    BOOL_OR(a.dt_vencimento < CURRENT_DATE)                        AS tem_vencido
FROM sienge.fato_apropriacao a
WHERE a.dt_vencimento IS NOT NULL
  AND a.dt_emissao IS NULL
  AND a.unidade_construtiva IS NOT NULL AND a.unidade_construtiva <> ''
  AND a.dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_apropriacao WHERE empresa = a.empresa)
GROUP BY a.empresa, a.unidade_construtiva, a.etapa, a.subetapa,
         a.cod_servico, a.descricao_servico, a.tipo_or, mes;
CREATE INDEX idx_bi_aprop_vc_emp_mes ON bi.apropriacao_vencimento_mensal (empresa, mes);

-- Insumos (recria com safe)
DROP MATERIALIZED VIEW IF EXISTS bi.insumos_apropriacao CASCADE;
CREATE MATERIALIZED VIEW bi.insumos_apropriacao AS
SELECT
    i.empresa,
    NULLIF(NULLIF(i.cod_obra, 'NaN'), '')        AS cod_obra,
    i.unidade_construtiva                         AS uc,
    i.cod_servico,
    i.descricao_servico,
    i.cod_insumo,
    i.descricao,
    i.unidade,
    COALESCE(bi.safe_float(i.qtd_orcada), 0)      AS qtd_orcada,
    COALESCE(bi.safe_float(i.qtd_apropriada), 0)  AS qtd_apropriada,
    COALESCE(bi.safe_float(i.valor_orcado), 0)    AS valor_orcado,
    COALESCE(bi.safe_float(i.valor_apropriado), 0) AS valor_apropriado,
    CASE WHEN COALESCE(bi.safe_float(i.qtd_orcada), 0) > 0
         THEN bi.safe_float(i.valor_orcado) / bi.safe_float(i.qtd_orcada)
         ELSE 0 END                               AS vunit_orcado,
    CASE WHEN COALESCE(bi.safe_float(i.qtd_apropriada), 0) > 0
         THEN bi.safe_float(i.valor_apropriado) / bi.safe_float(i.qtd_apropriada)
         ELSE 0 END                               AS vunit_apropriado
FROM sienge.fato_analitico_insumos i
WHERE i.cod_servico IS NOT NULL AND i.cod_servico <> ''
  AND i.dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_analitico_insumos WHERE empresa = i.empresa);
CREATE INDEX idx_bi_insumos_emp ON bi.insumos_apropriacao (empresa);
CREATE INDEX idx_bi_insumos_obra ON bi.insumos_apropriacao (empresa, cod_obra);
CREATE INDEX idx_bi_insumos_cod ON bi.insumos_apropriacao (cod_insumo);
