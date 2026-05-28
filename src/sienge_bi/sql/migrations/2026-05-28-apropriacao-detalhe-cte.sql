-- Fix: bi.apropriacao_detalhe estava usando subquery correlato no WHERE
-- (SELECT MAX(dt_ref) ... WHERE empresa = a.empresa) — executa POR LINHA,
-- gerando timeout no Supabase (statement_timeout default 60s). Mesmo padrao
-- ja corrigido em bi.contratos / bi.pedidos_compra / bi.medido_comprometido /
-- bi.apropriacao_emissao_mensal etc.
--
-- Aqui troco por CTE + JOIN. Mantem como view normal (nao materializada) porque
-- ja eh rapida (0.8s pra count, 7.8s pra group by em 235k linhas).
--
-- Data: 2026-05-28

CREATE OR REPLACE VIEW bi.apropriacao_detalhe AS
WITH mr AS (
  SELECT empresa, MAX(dt_ref) AS dt_ref
  FROM sienge.fato_apropriacao
  GROUP BY empresa
)
SELECT
    a.empresa,
    NULLIF(NULLIF(a.cod_obra, 'NaN'), '')   AS cod_obra,
    a.unidade_construtiva                    AS uc,
    a.cod_servico,
    a.descricao_servico,
    a.tipo_or,
    a.documento,
    a.titulo_parcela,
    a.historico,
    a.dt_emissao,
    a.dt_vencimento,
    bi.safe_float(a.valor)                   AS valor,
    bi.safe_float(a.valor_documento)         AS valor_documento,
    a.observacao,
    CASE
        WHEN a.dt_emissao    IS NOT NULL THEN 'Emissao'
        WHEN a.dt_vencimento IS NOT NULL THEN 'Vencimento'
        ELSE 'Outro'
    END                                      AS origem
FROM sienge.fato_apropriacao a
JOIN mr ON mr.empresa = a.empresa AND mr.dt_ref = a.dt_ref;
