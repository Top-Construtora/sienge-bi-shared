-- Migration: aumenta precision dos percentuais em fato_medido_comprometido
-- de NUMERIC(7,4) (max 999.9999%) pra NUMERIC(12,4) (max ~99M).
-- Necessario porque algumas linhas tem percentuais > 1000% (medido > 10x orcado,
-- geralmente dados quebrados do Excel) que estouravam o overflow.
SET search_path TO sienge, public;

ALTER TABLE fato_medido_comprometido
    ALTER COLUMN percentual                      TYPE NUMERIC(12,4),
    ALTER COLUMN percentual_medido               TYPE NUMERIC(12,4),
    ALTER COLUMN percentual_comprometido_medido  TYPE NUMERIC(12,4),
    ALTER COLUMN percentual_comprometido_medido_estoque TYPE NUMERIC(12,4);
