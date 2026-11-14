-- Adapta a persistência de análise para quatro features e registra o estado ML.
-- Aplicar após 001_create_schema.sql e 002_device_timestamps.sql.
BEGIN;

ALTER TABLE iot_readings
    ADD COLUMN IF NOT EXISTS analysis_status VARCHAR(20) NOT NULL DEFAULT 'PENDENTE';
ALTER TABLE iot_readings
    DROP CONSTRAINT IF EXISTS ck_iot_readings_analysis_status;
ALTER TABLE iot_readings
    ADD CONSTRAINT ck_iot_readings_analysis_status
    CHECK (analysis_status IN ('PENDENTE', 'CONCLUIDA', 'FALHA'));

ALTER TABLE iot_anomaly_analyses
    DROP CONSTRAINT IF EXISTS iot_anomaly_analyses_variables_check;
ALTER TABLE iot_anomaly_analyses
    DROP CONSTRAINT IF EXISTS ck_iot_anomaly_variables_three;
ALTER TABLE iot_anomaly_analyses
    DROP CONSTRAINT IF EXISTS ck_iot_anomaly_variables_four;
ALTER TABLE iot_anomaly_analyses
    ADD CONSTRAINT ck_iot_anomaly_variables_four
    CHECK (jsonb_array_length(variables) = 4);

UPDATE iot_readings AS r
SET analysis_status = 'CONCLUIDA'
WHERE EXISTS (
    SELECT 1 FROM iot_anomaly_analyses AS a WHERE a.reading_id = r.id
);

COMMIT;