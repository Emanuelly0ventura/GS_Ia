import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.inteligencia_artificial.aprendizado_maquina.detector_anomalias import DetectorAnomalias
from app.inteligencia_artificial.aprendizado_maquina.esquemas import LeituraParaModelo
from app.telemetria.modelos import AnaliseAnomalia, Dispositivo, Leitura
from app.inteligencia_artificial.generativa.orquestracao import ResultadoExplicacaoGenerativa

DATABASE_URL = os.getenv("TEST_TELEMETRY_DATABASE_URL")
pytestmark = pytest.mark.integration
FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "isolation_forest_rotulado.json"


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


def detector_sintetico():
    dados = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    modelo = DetectorAnomalias()
    modelo.treinar(
        [LeituraParaModelo.model_validate(item) for item in dados["treinamento"]],
        identificador_dados="tests/fixtures/isolation_forest_rotulado.json",
    )
    return modelo


def configurar_rota(rotas, monkeypatch, factory, detector):
    configuracoes = SimpleNamespace(
        telemetry_soil_moisture_temp_min_c=15.0,
        telemetry_soil_moisture_temp_max_c=35.0,
        telemetry_device_timeout_seconds=60,
        ml_caminho_modelo="fixture-test.joblib",
        ml_versao_modelo="isolation-forest-v3",
    )
    monkeypatch.setattr(rotas, "_sessao", lambda: factory())
    monkeypatch.setattr(rotas, "obter_configuracoes", lambda: configuracoes)
    monkeypatch.setattr(rotas, "carregar_detector_telemetria", lambda _: detector)
    monkeypatch.setattr(rotas, "tentar_explicar_anomalia", lambda *args, **kwargs: ResultadoExplicacaoGenerativa("CONCLUIDA", texto="Descrição complementar simulada por mock."))


def criar_payload(device_id, observation_id, values):
    from app.telemetria.esquemas import LeituraIoT
    return LeituraIoT.model_validate({
        "deviceId": device_id,
        "observationId": observation_id,
        "source": "FIXTURE_TESTE_FASE3",
        "measuredAt": datetime.now(timezone.utc).isoformat(),
        "quality": "VALID",
        "values": values,
        "units": {"temperaturaAr": "°C", "umidadeSolo": "°C", "umidadeAr": "%", "luminosidade": "ADC"},
    })


def test_postgres_persiste_captura_e_inferencia_de_quatro_features(postgres_engine, monkeypatch):
    from app.telemetria import rotas

    inspector = inspect(postgres_engine)
    assert {"iot_devices", "iot_readings", "iot_anomaly_analyses"}.issubset(set(inspector.get_table_names()))
    expected_columns = {
        "iot_devices": {"id", "device_id", "source", "last_seen_at", "created_at", "updated_at"},
        "iot_readings": {"id", "device_id", "observation_id", "measured_at", "received_at", "source", "quality", "analysis_status", "sensor_values", "units", "complements"},
        "iot_anomaly_analyses": {"id", "reading_id", "model_version", "is_anomaly", "score", "analyzed_at", "variables", "explanation", "generative_explanation", "generative_status", "generative_error_code"},
    }
    for table, expected in expected_columns.items():
        assert {column["name"] for column in inspector.get_columns(table)} == expected

    factory = sessionmaker(postgres_engine, expire_on_commit=False)
    model = detector_sintetico()
    configurar_rota(rotas, monkeypatch, factory, model)
    device_id = f"pytest-fase3-{uuid4().hex}"
    normal_id = f"normal-{uuid4().hex}"
    anomaly_id = f"anomaly-{uuid4().hex}"
    normal_payload = criar_payload(device_id, normal_id, {
        "temperaturaAr": 25.1, "umidadeSolo": 25.0, "umidadeAr": 62.0, "luminosidade": 1870.0,
    })
    anomaly_payload = criar_payload(device_id, anomaly_id, {
        "temperaturaAr": 5.0, "umidadeSolo": 15.0, "umidadeAr": 10.0, "luminosidade": 3956.5,
    })
    try:
        from app.principal import app
        client = TestClient(app)
        normal_http = client.post("/api/v1/iot/readings", json=normal_payload.model_dump(mode="json"))
        anomaly_http = client.post("/api/v1/iot/readings", json=anomaly_payload.model_dump(mode="json"))
        assert normal_http.status_code == 201
        assert anomaly_http.status_code == 201
        normal_response = normal_http.json()
        anomaly_response = anomaly_http.json()
        assert normal_response["analysisStatus"] == "CONCLUIDA"
        assert normal_response["analysis"]["executed"] is True
        assert normal_response["analysis"]["isAnomaly"] is False
        assert normal_response["analysis"]["score"] >= 0
        assert normal_response["analysis"]["variables"] == ["temperaturaAr", "umidadeSolo", "umidadeAr", "luminosidade"]
        assert anomaly_response["analysisStatus"] == "CONCLUIDA"
        assert anomaly_response["analysis"]["isAnomaly"] is True
        assert anomaly_response["analysis"]["score"] >= 0

        with Session(postgres_engine) as db:
            rows = db.scalars(
                select(Leitura).options(joinedload(Leitura.anomaly)).where(Leitura.device_id == device_id)
            ).all()
            by_id = {row.observation_id: row for row in rows}
            normal = by_id[normal_id]
            assert normal.values == {
                "temperaturaAr": 25.1, "umidadeSolo": 50.0, "umidadeAr": 62.0, "luminosidade": 1870.0,
            }
            assert normal.complements["umidadeSolo"]["temperaturaFonteC"] == 25.0
            assert normal.analysis_status == "CONCLUIDA"
            assert normal.anomaly is not None and normal.anomaly.is_anomaly is False
            assert normal.anomaly.variables == ["temperaturaAr", "umidadeSolo", "umidadeAr", "luminosidade"]
            assert normal.anomaly.model_version == "isolation-forest-v3"
            assert normal.anomaly.generative_status == "CONCLUIDA"
            assert normal.anomaly.generative_explanation == "Descrição complementar simulada por mock."
            assert normal_response["analysis"]["generativeExplanation"] == normal.anomaly.generative_explanation
            assert normal.anomaly.score == pytest.approx(normal_response["analysis"]["score"])
            anomaly = by_id[anomaly_id]
            assert anomaly.analysis_status == "CONCLUIDA"
            assert anomaly.anomaly is not None and anomaly.anomaly.is_anomaly is True

        duplicate = client.post("/api/v1/iot/readings", json=normal_payload.model_dump(mode="json"))
        assert duplicate.status_code == 409
        with Session(postgres_engine) as db:
            assert db.scalar(select(func.count(Leitura.id)).where(Leitura.device_id == device_id)) == 2
            assert db.scalar(select(func.count(AnaliseAnomalia.id)).join(Leitura).where(Leitura.device_id == device_id)) == 2
    finally:
        with Session(postgres_engine) as db:
            device = db.scalar(select(Dispositivo).where(Dispositivo.device_id == device_id))
            if device is not None:
                db.delete(device)
                db.commit()


def test_falha_modelo_mantem_captura_e_nao_cria_analise(postgres_engine, monkeypatch, caplog):
    from app.telemetria import rotas
    factory = sessionmaker(postgres_engine, expire_on_commit=False)
    device_id = f"pytest-fase3-falha-{uuid4().hex}"
    payload = criar_payload(device_id, f"failure-{uuid4().hex}", {
        "temperaturaAr": 25.1, "umidadeSolo": 25.0, "umidadeAr": 62.0, "luminosidade": 1870.0,
    })
    configuracoes = SimpleNamespace(
        telemetry_soil_moisture_temp_min_c=15.0,
        telemetry_soil_moisture_temp_max_c=35.0,
        ml_caminho_modelo="inexistente.joblib",
        ml_versao_modelo="isolation-forest-v3",
    )
    monkeypatch.setattr(rotas, "_sessao", lambda: factory())
    monkeypatch.setattr(rotas, "obter_configuracoes", lambda: configuracoes)
    def detector_ausente(_):
        raise FileNotFoundError("fixture de indisponibilidade do modelo")
    monkeypatch.setattr(rotas, "carregar_detector_telemetria", detector_ausente)
    try:
        from app.principal import app
        response = TestClient(app).post("/api/v1/iot/readings", json=payload.model_dump(mode="json"))
        assert response.status_code == 201
        response = response.json()
        assert response["analysisStatus"] == "FALHA"
        assert response["analysis"]["executed"] is False
        assert "falhou" in response["analysis"]["message"].lower()
        assert "Falha na análise ML após persistir captura" in caplog.text
        with Session(postgres_engine) as db:
            row = db.scalar(select(Leitura).where(Leitura.device_id == device_id))
            assert row is not None and row.analysis_status == "FALHA"
            assert db.scalar(select(func.count(AnaliseAnomalia.id)).where(AnaliseAnomalia.reading_id == row.id)) == 0
    finally:
        with Session(postgres_engine) as db:
            device = db.scalar(select(Dispositivo).where(Dispositivo.device_id == device_id))
            if device is not None:
                db.delete(device)
                db.commit()
