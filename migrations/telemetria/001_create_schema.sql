-- Aplicar somente no banco PostgreSQL SEPARADO da demonstração.
-- Execução manual por DBA/ambiente; nunca é executada no startup da API.
BEGIN;

CREATE TABLE IF NOT EXISTS iot_devices (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(120) NOT NULL UNIQUE,
    source VARCHAR(80) NOT NULL,
    last_seen_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS iot_readings (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(120) NOT NULL
        REFERENCES iot_devices(device_id) ON DELETE CASCADE,
    observation_id VARCHAR(120) NOT NULL,
    measured_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source VARCHAR(80) NOT NULL,
    quality VARCHAR(30) NOT NULL CHECK (quality IN ('VALID')),
    sensor_values JSONB NOT NULL,
    units JSONB NOT NULL,
    complements JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_iot_reading_observation
        UNIQUE (device_id, observation_id)
);
CREATE INDEX IF NOT EXISTS ix_iot_readings_device_id
    ON iot_readings(device_id);
CREATE INDEX IF NOT EXISTS ix_iot_readings_measured_at
    ON iot_readings(measured_at DESC);

CREATE TABLE IF NOT EXISTS iot_anomaly_analyses (
    id BIGSERIAL PRIMARY KEY,
    reading_id BIGINT NOT NULL UNIQUE
        REFERENCES iot_readings(id) ON DELETE CASCADE,
    model_version VARCHAR(80) NOT NULL,
    is_anomaly BOOLEAN NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    analyzed_at TIMESTAMPTZ NOT NULL,
    variables JSONB NOT NULL
        CHECK (jsonb_array_length(variables) = 3),
    explanation VARCHAR(500) NOT NULL
);

COMMIT;
