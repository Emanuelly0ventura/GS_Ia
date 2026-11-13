import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.engine import make_url

from app.telemetria.modelos import AnaliseAnomalia, Dispositivo, Leitura

DATABASE_URL = os.getenv("TEST_TELEMETRY_DATABASE_URL")
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def postgres_engine():
    if not DATABASE_URL:
        pytest.skip("Defina TEST_TELEMETRY_DATABASE_URL para um PostgreSQL descartável.")
    url = make_url(DATABASE_URL)
    if not url.drivername.startswith("postgresql"):
        pytest.fail("TEST_TELEMETRY_DATABASE_URL precisa apontar para PostgreSQL.")
    if not (url.database or "").endswith("_test"):
        pytest.fail("Por segurança, use um banco de integração cujo nome termine em _test.")
    from sqlalchemy import create_engine
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


def test_postgres_persiste_leitura_jsonb_relacoes_e_unicidade(postgres_engine):
    tabelas_esperadas = {"iot_devices", "iot_readings", "iot_anomaly_analyses"}
    inspector = inspect(postgres_engine)
    assert tabelas_esperadas.issubset(set(inspector.get_table_names()))
    assert {"created_at", "updated_at"}.issubset(
        {col["name"] for col in inspector.get_columns("iot_devices")}
    )

    device_id = f"pytest-{uuid4()}"
    observation_id = f"capture-{uuid4()}"
    valores = {"temperaturaAr": 24.2, "umidadeAr": 61.0, "luminosidade": 1450}
    unidades = {"temperaturaAr": "°C", "umidadeAr": "%", "luminosidade": "ADC"}
    try:
        with Session(postgres_engine) as db:
            device = Dispositivo(device_id=device_id, source="TESTE_INTEGRACAO")
            reading = Leitura(
                device_id=device_id,
                observation_id=observation_id,
                measured_at=datetime.now(timezone.utc),
                source="TESTE_INTEGRACAO",
                quality="VALID",
                values=valores,
                units=unidades,
                complements={"umidadeSolo": {"value": 37, "unit": "%", "simulated": True}},
            )
            reading.anomaly = AnaliseAnomalia(
                model_version="integration-test-v1",
                is_anomaly=False,
                score=0.12,
                analyzed_at=datetime.now(timezone.utc),
                variables=["temperaturaAr", "umidadeAr", "luminosidade"],
                explanation="Resultado sintético de teste.",
            )
            db.add_all([device, reading])
            db.commit()
            reading_id = reading.id
            assert device.created_at is not None and device.updated_at is not None

        with Session(postgres_engine) as db:
            persisted = db.scalar(
                select(Leitura)
                .options(joinedload(Leitura.device), joinedload(Leitura.anomaly))
                .where(Leitura.id == reading_id)
            )
            assert persisted is not None
            assert persisted.values == valores
            assert persisted.units == unidades
            assert persisted.complements["umidadeSolo"]["simulated"] is True
            assert persisted.device.device_id == device_id
            assert persisted.anomaly.model_version == "integration-test-v1"
            assert db.scalar(
                select(func.count(Leitura.id)).where(
                    Leitura.device_id == device_id,
                    Leitura.observation_id == observation_id,
                )
            ) == 1

            duplicada = Leitura(
                device_id=device_id,
                observation_id=observation_id,
                measured_at=datetime.now(timezone.utc),
                source="TESTE_INTEGRACAO",
                quality="VALID",
                values=valores,
                units=unidades,
                complements={},
            )
            db.add(duplicada)
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
    finally:
        with Session(postgres_engine) as db:
            device = db.scalar(select(Dispositivo).where(Dispositivo.device_id == device_id))
            if device is not None:
                db.delete(device)
                db.commit()
