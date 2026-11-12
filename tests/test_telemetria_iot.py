from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.principal import app
from app.telemetria.banco import BaseTelemetria
from app.telemetria.esquemas import LeituraIoT
from app.telemetria.modelos import AnaliseAnomalia, Dispositivo, Leitura

BASE = {
    "deviceId": "esp32-test", "observationId": "sample-1", "source": "SIMULADOR_TESTE",
    "measuredAt": "2026-11-11T10:00:00-03:00", "quality": "VALID",
    "values": {"temperaturaAr": 24.0, "umidadeAr": 60.0, "luminosidade": 1200},
    "units": {"temperaturaAr": "°C", "umidadeAr": "%", "luminosidade": "ADC"},
}

def test_schema_accepts_three_required_values_and_optional_bmp_complements():
    body = {**BASE, "complements": {"pressao": 1011.5}}
    parsed = LeituraIoT.model_validate(body)
    assert set(parsed.values) == {"temperaturaAr", "umidadeAr", "luminosidade"}
    assert parsed.complements["pressao"] == 1011.5

def test_schema_rejects_incomplete_unrecognized_bad_units_and_nonfinite_values():
    for change in [
        {"values": {"temperaturaAr": 24, "umidadeAr": 60}},
        {"values": {**BASE["values"], "campoDesconhecido": 40}},
        {"units": {**BASE["units"], "luminosidade": "lx"}},
        {"values": {**BASE["values"], "luminosidade": float("inf")}},
        {"values": {**BASE["values"], "umidadeAr": 101}},
        {"complements": {"pressao": float("nan")}},
        {"units": {**BASE["units"], "pressao": "Pa"}},
        {"measuredAt": "2026-11-11T10:00:00"},
    ]:
        with pytest.raises(ValidationError): LeituraIoT.model_validate({**BASE, **change})

def test_ingest_persists_reading_and_analysis_and_supports_dashboard(monkeypatch):
    from app.telemetria import rotas
    from app.inteligencia_artificial.aprendizado_maquina.esquemas import ResultadoAnomalia

    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseTelemetria.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(rotas, "_sessao", lambda: factory())
    monkeypatch.setattr(rotas, "obter_configuracoes", lambda: SimpleNamespace(
        ml_caminho_modelo="unused", ml_versao_modelo="isolation-forest-v2",
        telemetry_device_timeout_seconds=60))
    class Detector:
        versao_modelo = "isolation-forest-v2"
        def predizer(self, reading):
            return ResultadoAnomalia(idObservacao=reading.id_observacao,
                classificadaComoAnomalia=False, classificacao="NAO_ATIPICA_ESTIMADA",
                pontuacaoAnomalia=0.17, variaveisUtilizadas=["temperaturaAr","umidadeAr","luminosidade"],
                dataAnalise=datetime.now(timezone.utc), dataLeitura=reading.registrado_em,
                origemDados=reading.origem, versaoModelo=self.versao_modelo,
                configuracaoModelo={"algoritmo":"IsolationForest"}, justificativa="Escores estatísticos.")
    monkeypatch.setattr(rotas, "carregar_detector", lambda _: Detector())
    payload = LeituraIoT.model_validate(BASE)
    result = rotas.receber(payload)
    assert result["observationId"] == "sample-1"
    with factory() as db:
        rows = db.scalars(select(Leitura)).all()
        analyses = db.scalars(select(AnaliseAnomalia)).all()
        assert len(rows) == len(analyses) == 1
        assert rows[0].values["luminosidade"] == 1200
        assert analyses[0].variables == ["temperaturaAr","umidadeAr","luminosidade"]
    assert rotas.historico(limit=100)[0]["analysis"]["modelVersion"] == "isolation-forest-v2"
    assert rotas.status()["devices"][0]["connected"] is True

def test_duplicate_observation_id_is_rejected(monkeypatch):
    from app.telemetria import rotas
    from app.inteligencia_artificial.aprendizado_maquina.esquemas import ResultadoAnomalia
    from fastapi import HTTPException
    engine=create_engine("sqlite+pysqlite:///:memory:"); BaseTelemetria.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False); monkeypatch.setattr(rotas,"_sessao",lambda:factory())
    monkeypatch.setattr(rotas,"obter_configuracoes",lambda:SimpleNamespace(ml_caminho_modelo="unused",ml_versao_modelo="isolation-forest-v2"))
    class Detector:
        versao_modelo="isolation-forest-v2"
        def predizer(self,reading): return ResultadoAnomalia(idObservacao=reading.id_observacao,classificadaComoAnomalia=False,classificacao="NAO_ATIPICA_ESTIMADA",pontuacaoAnomalia=.1,variaveisUtilizadas=["temperaturaAr","umidadeAr","luminosidade"],dataAnalise=datetime.now(timezone.utc),dataLeitura=reading.registrado_em,origemDados=reading.origem,versaoModelo=self.versao_modelo,configuracaoModelo={},justificativa="Estatístico.")
    monkeypatch.setattr(rotas,"carregar_detector",lambda _:Detector())
    payload=LeituraIoT.model_validate(BASE); rotas.receber(payload)
    with pytest.raises(HTTPException) as error: rotas.receber(payload)
    assert error.value.status_code==409

def test_mobile_demo_is_static_and_has_no_soil_sensor_contract():
    with TestClient(app) as client:
        response=client.get("/api/v1/mobile/demo/snapshot")
    assert response.status_code==200
    body=response.json()
    assert body["dataMode"]=="PREDEFINED_DEMO"
    assert body["properties"][0]["fields"][0]["soilType"]=="SOLO_FICTICIO"
    assert set(body["indicators"])=={"temperaturaAr","umidadeAr","luminosidade"}
    assert body["indicators"]["luminosidade"]["unit"]=="ADC"


def test_model_types_match_postgresql_migration_and_keep_sqlite_compatibility():
    values_column = Leitura.__table__.c.sensor_values
    assert Leitura.values.property.columns[0].name == "sensor_values"
    assert "JSONB" in str(values_column.type.dialect_impl(postgresql.dialect())).upper()
    assert "JSONB" in values_column.type.dialect_impl(postgresql.dialect()).__class__.__name__.upper()
    assert "JSON" in values_column.type.dialect_impl(sqlite.dialect()).__class__.__name__.upper()
    assert str(Dispositivo.__table__.c.id.type.compile(dialect=postgresql.dialect())) == "BIGINT"
    assert str(Leitura.__table__.c.id.type.compile(dialect=postgresql.dialect())) == "BIGINT"
    assert str(AnaliseAnomalia.__table__.c.id.type.compile(dialect=postgresql.dialect())) == "BIGINT"
    assert str(AnaliseAnomalia.__table__.c.reading_id.type.compile(dialect=postgresql.dialect())) == "BIGINT"
    assert str(Leitura.__table__.c.id.type.compile(dialect=sqlite.dialect())) == "INTEGER"
    assert "uq_iot_reading_observation" in {c.name for c in Leitura.__table__.constraints}
    assert "ck_iot_anomaly_variables_three" in {c.name for c in AnaliseAnomalia.__table__.constraints}


def test_commit_failure_rolls_back_and_returns_503(monkeypatch):
    from app.telemetria import rotas
    from app.inteligencia_artificial.aprendizado_maquina.esquemas import ResultadoAnomalia
    from fastapi import HTTPException
    from sqlalchemy.exc import OperationalError

    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseTelemetria.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    rollbacks = []

    class CommitFailsSession(Session):
        def commit(self):
            raise OperationalError("COMMIT", {}, RuntimeError("simulated commit failure"))

        def rollback(self):
            rollbacks.append(True)
            return super().rollback()

    monkeypatch.setattr(rotas, "_sessao", lambda: CommitFailsSession(bind=engine))
    monkeypatch.setattr(rotas, "obter_configuracoes", lambda: SimpleNamespace(
        ml_caminho_modelo="unused", ml_versao_modelo="isolation-forest-v2"))

    class Detector:
        versao_modelo = "isolation-forest-v2"

        def predizer(self, reading):
            return ResultadoAnomalia(
                idObservacao=reading.id_observacao,
                classificadaComoAnomalia=False,
                classificacao="NAO_ATIPICA_ESTIMADA",
                pontuacaoAnomalia=0.1,
                variaveisUtilizadas=["temperaturaAr", "umidadeAr", "luminosidade"],
                dataAnalise=datetime.now(timezone.utc),
                dataLeitura=reading.registrado_em,
                origemDados=reading.origem,
                versaoModelo=self.versao_modelo,
                configuracaoModelo={},
                justificativa="Estatístico.",
            )

    monkeypatch.setattr(rotas, "carregar_detector", lambda _: Detector())
    with pytest.raises(HTTPException) as error:
        rotas.receber(LeituraIoT.model_validate(BASE))
    assert error.value.status_code == 503
    assert rollbacks
    with factory() as db:
        assert db.scalar(select(Leitura)) is None
        assert db.scalar(select(Dispositivo)) is None
