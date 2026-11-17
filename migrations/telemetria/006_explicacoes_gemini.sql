-- Persistência opcional das explicações Gemini sem substituir decisões determinísticas.
-- Aplicar depois de 005_seed_catalogos_agricolas.sql; idempotente para colunas e constraints.
BEGIN;

ALTER TABLE iot_anomaly_analyses
    ADD COLUMN IF NOT EXISTS generative_explanation TEXT;
ALTER TABLE iot_anomaly_analyses
    ADD COLUMN IF NOT EXISTS generative_status VARCHAR(30) NOT NULL DEFAULT 'NAO_CONFIGURADO';
ALTER TABLE iot_anomaly_analyses
    ADD COLUMN IF NOT EXISTS generative_error_code VARCHAR(60);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_iot_anomaly_generative_status'
          AND conrelid = 'iot_anomaly_analyses'::regclass
    ) THEN
        ALTER TABLE iot_anomaly_analyses
            ADD CONSTRAINT ck_iot_anomaly_generative_status
            CHECK (generative_status IN ('PENDENTE', 'NAO_CONFIGURADO', 'CONCLUIDA', 'FALHA'));
    END IF;
END $$;

ALTER TABLE analises_compatibilidade
    ADD COLUMN IF NOT EXISTS explicacao_gemini TEXT;
ALTER TABLE analises_compatibilidade
    ADD COLUMN IF NOT EXISTS estado_explicacao VARCHAR(30) NOT NULL DEFAULT 'NAO_CONFIGURADO';
ALTER TABLE analises_compatibilidade
    ADD COLUMN IF NOT EXISTS codigo_erro_explicacao VARCHAR(60);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_analises_compatibilidade_estado_explicacao'
          AND conrelid = 'analises_compatibilidade'::regclass
    ) THEN
        ALTER TABLE analises_compatibilidade
            ADD CONSTRAINT ck_analises_compatibilidade_estado_explicacao
            CHECK (estado_explicacao IN ('PENDENTE', 'NAO_CONFIGURADO', 'SEM_CRITERIOS', 'CONCLUIDA', 'FALHA'));
    END IF;
END $$;

COMMIT;