-- Entidades do catálogo agrícola e histórico das decisões determinísticas.
-- Aplicar somente no PostgreSQL local próprio da API, após 003_anomaly_four_features.sql.
BEGIN;

CREATE TABLE IF NOT EXISTS tipos_semente (
    id UUID PRIMARY KEY,
    codigo VARCHAR(40) NOT NULL UNIQUE,
    nome VARCHAR(120) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS tipos_solo (
    id UUID PRIMARY KEY,
    codigo VARCHAR(40) NOT NULL UNIQUE,
    nome VARCHAR(120) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS compatibilidades (
    id UUID PRIMARY KEY,
    semente_id UUID NOT NULL REFERENCES tipos_semente(id) ON DELETE RESTRICT,
    solo_id UUID NOT NULL REFERENCES tipos_solo(id) ON DELETE RESTRICT,
    resultado VARCHAR(30) NOT NULL
        CHECK (resultado IN ('COMPATIVEL', 'INCOMPATIVEL', 'DADOS_INSUFICIENTES')),
    criterios JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(criterios) = 'array'),
    justificativa VARCHAR(2000) NOT NULL,
    referencia_fonte VARCHAR(1000) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_compatibilidades_semente_solo UNIQUE (semente_id, solo_id)
);

CREATE TABLE IF NOT EXISTS analises_compatibilidade (
    id UUID PRIMARY KEY,
    semente_id UUID NOT NULL REFERENCES tipos_semente(id) ON DELETE RESTRICT,
    solo_id UUID NOT NULL REFERENCES tipos_solo(id) ON DELETE RESTRICT,
    compatibilidade_id UUID REFERENCES compatibilidades(id) ON DELETE SET NULL,
    semente_codigo VARCHAR(40) NOT NULL,
    semente_nome VARCHAR(120) NOT NULL,
    solo_codigo VARCHAR(40) NOT NULL,
    solo_nome VARCHAR(120) NOT NULL,
    resultado VARCHAR(30) NOT NULL
        CHECK (resultado IN ('COMPATIVEL', 'INCOMPATIVEL', 'DADOS_INSUFICIENTES')),
    criterios JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(criterios) = 'array'),
    justificativa VARCHAR(2000),
    referencia_fonte VARCHAR(1000),
    analisado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_compatibilidades_ativos
    ON compatibilidades (semente_id, solo_id) WHERE ativo = TRUE;
CREATE INDEX IF NOT EXISTS ix_analises_compatibilidade_data
    ON analises_compatibilidade (analisado_em DESC);

COMMIT;