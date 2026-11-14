import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect, select, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.telemetria.modelos import Dispositivo, Leitura, AnaliseAnomalia

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


def test_postgres_ingere_quatro_indicadores_e_nao_executa_ml(postgres_engine, monkeypatch):
    from app.telemetria import rotas
    from app.telemetria.esquemas import LeituraIoT

    inspector = inspect(postgres_engine)
    assert {"iot_devices", "iot_readings", "iot_anomaly_analyses"}.issubset(
        set(inspector.get_table_names())
    )
    expected_columns = {
        "iot_devices": {"id", "device_id", "source", "last_seen_at", "created_at", "updated_at"},
        "iot_readings": {"id", "device_id", "observation_id", "measured_at", "received_at", "source", "quality", "sensor_values", "units", "complements"},
        "iot_anomaly_analyses": {"id", "reading_id", "model_version", "is_anomaly", "score", "analyzed_at", "variables", "explanation"},
    }
    for table, expected in expected_columns.items():
        assert {column["name"] for column in inspector.get_columns(table)} == expected

    factory = sessionmaker(postgres_engine, expire_on_commit=False)
    monkeypatch.setattr(rotas, "_sessao", lambda: factory())
    device_id = f"pytest-fase2-{uuid4().hex}"
    observation_id = f"capture-{uuid4().hex}"
    payload = LeituraIoT.model_validate({
        "deviceId": device_id,
        "observationId": observation_id,
        "source": "WOKWI_HIVEMQ_NODE_RED",
        "measuredAt": datetime.now(timezone.utc).isoformat(),
        "quality": "VALID",
        "values": {"temperaturaAr": 25.1, "umidadeSolo": 25.0, "umidadeAr": 62.0, "luminosidade": 1870},
        "units": {"temperaturaAr": "°C", "umidadeSolo": "°C", "umidadeAr": "%", "luminosidade": "ADC"},
    })
    try:
        response = rotas.receber(payload)
        assert response["analysisStatus"] == "PENDENTE_ADEQUACAO_CONTRATO_ML"
        assert response["analysis"]["executed"] is False
        with Session(postgres_engine) as db:
            reading = db.scalar(
                select(Leitura)
                .options(joinedload(Leitura.device))
                .where(Leitura.device_id == device_id, Leitura.observation_id == observation_id)
            )
            assert reading is not None
            assert reading.values == {
                "temperaturaAr": 25.1,
                "umidadeSolo": 50.0,
                "umidadeAr": 62.0,
                "luminosidade": 1870.0,
            }
            assert reading.units == {
                "temperaturaAr": "°C", "umidadeSolo": "%", "umidadeAr": "%", "luminosidade": "ADC"
            }
            assert reading.complements["umidadeSolo"] == {
                "origem": "DHT22_TEMPERATURA",
                "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA",
                "simulado": True,
                "temperaturaFonteC": 25.0,
            }
            assert reading.device.device_id == device_id
            assert db.scalar(select(func.count(AnaliseAnomalia.id)).where(AnaliseAnomalia.reading_id == reading.id)) == 0

        with pytest.raises(HTTPException) as error:
            rotas.receber(payload)
        assert error.value.status_code == 409
        with Session(postgres_engine) as db:
            assert db.scalar(select(func.count(Leitura.id)).where(Leitura.device_id == device_id)) == 1
    finally:
        with Session(postgres_engine) as db:
            device = db.scalar(select(Dispositivo).where(Dispositivo.device_id == device_id))
            if device is not None:
                db.delete(device)
                db.commit()
