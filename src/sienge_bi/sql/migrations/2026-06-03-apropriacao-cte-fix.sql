-- Migration: reescreve apropriacao_*_mensal pra eliminar correlated subquery.
--
-- A definicao anterior tinha:
--   WHERE dt_ref = (SELECT MAX(dt_ref) FROM sienge.fato_apropriacao WHERE empresa = a.empresa)
-- Isso e correlated subquery (re-roda por linha) e levava o REFRESH a estourar
-- o statement_timeout de 600s em alguns bancos (IMPULSI, TANGARA, INOVAR em 2026-06-03).
--
-- Substituicao: CTE 'latest' calculada uma vez + JOIN.

DROP MATERIALIZED VIEW IF EXISTS bi.apropriacao_emissao_mensal CASCADE;

CREATE MATERIALIZED VIEW bi.apropriacao_emissao_mensal AS
WITH latest AS (
  SELECT empresa, MAX(dt_ref) AS dt_ref
  FROM sienge.fato_apropriacao
  GROUP BY empresa
)
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
JOIN latest l ON l.empresa = a.empresa AND l.dt_ref = a.dt_ref
WHERE a.dt_emissao IS NOT NULL
  AND a.unidade_construtiva IS NOT NULL AND a.unidade_construtiva <> ''
GROUP BY a.empresa, a.unidade_construtiva, a.etapa, a.subetapa,
         a.cod_servico, a.descricao_servico, a.tipo_or, mes;

CREATE INDEX IF NOT EXISTS idx_bi_aprop_em_emp_mes ON bi.apropriacao_emissao_mensal (empresa, mes);
CREATE INDEX IF NOT EXISTS idx_bi_aprop_em_uc      ON bi.apropriacao_emissao_mensal (uc);

DROP MATERIALIZED VIEW IF EXISTS bi.apropriacao_vencimento_mensal CASCADE;

CREATE MATERIALIZED VIEW bi.apropriacao_vencimento_mensal AS
WITH latest AS (
  SELECT empresa, MAX(dt_ref) AS dt_ref
  FROM sienge.fato_apropriacao
  GROUP BY empresa
)
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
    BOOL_OR(a.dt_vencimento < CURRENT_DATE)                        AS tem_vencido
FROM sienge.fato_apropriacao a
JOIN latest l ON l.empresa = a.empresa AND l.dt_ref = a.dt_ref
WHERE a.dt_vencimento IS NOT NULL
  AND a.dt_emissao IS NULL
  AND a.unidade_construtiva IS NOT NULL AND a.unidade_construtiva <> ''
GROUP BY a.empresa, a.unidade_construtiva, a.etapa, a.subetapa,
         a.cod_servico, a.descricao_servico, a.tipo_or, mes;

CREATE INDEX IF NOT EXISTS idx_bi_aprop_vc_emp_mes ON bi.apropriacao_vencimento_mensal (empresa, mes);
