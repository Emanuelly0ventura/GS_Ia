-- Extensão aditiva do cadastro de dispositivos. Pode ser reaplicada com segurança.
-- Executar depois de 001_create_schema.sql no banco local da IA.
BEGIN;

ALTER TABLE iot_devices
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE iot_devices
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

COMMIT;
