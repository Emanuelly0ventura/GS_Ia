from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.principal import app
from app.nucleo.configuracoes import Configuracoes
from app.telemetria.banco import BaseTelemetria
from app.telemetria.conversoes import converter_temperatura_dht22_em_umidade_solo
from app.telemetria.esquemas import LeituraIoT, MetadadosUmidadeSolo
from app.telemetria.modelos import AnaliseAnomalia, Dispositivo, Leitura
from app.inteligencia_artificial.generativa.orquestracao import ResultadoExplicacaoGenerativa

BASE = {
    "deviceId": "esp32-test", "observationId": "sample-1", "source": "SIMULADOR_TESTE",
    "measuredAt": "2026-11-11T10:00:00-03:00", "quality": "VALID",
    "values": {"temperaturaAr": 26.4, "umidadeSolo": 25.0, "umidadeAr": 60.0, "luminosidade": 1200},
    "units": {"temperaturaAr": "°C", "umidadeSolo": "°C", "umidadeAr": "%", "luminosidade": "ADC"},
}


def _config():
    return SimpleNamespace(
        telemetry_soil_moisture_temp_min_c=15.0,
        telemetry_soil_moisture_temp_max_c=35.0,
        telemetry_device_timeout_seconds=60,
        ml_versao_modelo="isolation-forest-v3",
        ml_caminho_modelo="unused-test-artifact.joblib",
    )


def test_conversao_linear_marcos_15_25_35_graus():
    assert converter_temperatura_dht22_em_umidade_solo(15) == 0.0
    assert converter_temperatura_dht22_em_umidade_solo(25) == 50.0
    assert converter_temperatura_dht22_em_umidade_solo(35) == 100.0


@pytest.mark.parametrize(("temperatura", "esperado"), [(-5, 0.0), (14.9, 0.0), (35.1, 100.0), (80, 100.0)])
def test_conversao_aplica_limites_inferior_e_superior(temperatura, esperado):
    assert converter_temperatura_dht22_em_umidade_solo(temperatura) == esperado


def test_conversao_aceita_limites_configurados_e_rejeita_argumentos_invalidos():
    assert converter_temperatura_dht22_em_umidade_solo(20, limite_inferior_c=10, limite_superior_c=30) == 50.0
    for value in (None, True, float("nan"), float("inf"), "25"):
        with pytest.raises(ValueError):
            converter_temperatura_dht22_em_umidade_solo(value)
    with pytest.raises(ValueError, match="inferior"):
        converter_temperatura_dht22_em_umidade_solo(25, limite_inferior_c=35, limite_superior_c=15)
    with pytest.raises(ValidationError):
        Configuracoes(_env_file=None, telemetry_soil_moisture_temp_min_c=float("nan"))
    with pytest.raises(ValidationError):
        Configuracoes(_env_file=None, telemetry_soil_moisture_temp_min_c=35, telemetry_soil_moisture_temp_max_c=15)


def test_schema_node_red_exige_quatro_indicadores_e_unidades_de_entrada():
    parsed = LeituraIoT.model_validate(BASE)
    assert parsed.values["temperaturaAr"] == 26.4
    assert parsed.values["umidadeSolo"] == 25.0
    assert set(parsed.values) == {"temperaturaAr", "umidadeSolo", "umidadeAr", "luminosidade"}
    for change in (
        {"values": {k: v for k, v in BASE["values"].items() if k != "temperaturaAr"}},
        {"values": {**BASE["values"], "temperaturaAr": None}},
        {"values": {**BASE["values"], "umidadeSolo": None}},
        {"values": {**BASE["values"], "temperaturaGeral": 26.4}},
        {"units": {**BASE["units"], "umidadeSolo": "%"}},
        {"complements": {"temperaturaBmp": 26.4}},
        {"values": {**BASE["values"], "temperaturaAr": None}},
        {"values": {k: v for k, v in BASE["values"].items() if k != "luminosidade"}},
        {"complements": {"temperaturaBmp": None}},
        {"complements": {"temperaturaBmp": float("nan")}},
        {"units": {**BASE["units"], "luminosidade": "lux"}},

        {"values": {**BASE["values"], "umidadeAr": 101}},
        {"values": {**BASE["values"], "luminosidade": -1}},
        {"measuredAt": "2026-11-11T10:00:00"},
    ):
        with pytest.raises(ValidationError):
            LeituraIoT.model_validate({**BASE, **change})


def test_metadados_de_umidade_solo_validam_origem_metodo_e_simulacao():
    metadata = MetadadosUmidadeSolo.model_validate({
        "origem": "DHT22_TEMPERATURA",
        "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA",
        "simulado": True,
        "temperaturaFonteC": 25.0,
    })
    assert metadata.model_dump(mode="json", by_alias=True) == {
        "origem": "DHT22_TEMPERATURA",
        "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA",
        "simulado": True,
        "temperaturaFonteC": 25.0,
    }
    for change in ({"origem": "OUTRA"}, {"metodo": "MEDICAO_REAL"}, {"simulado": False}):
        with pytest.raises(ValidationError):
            MetadadosUmidadeSolo.model_validate({
                "origem": "DHT22_TEMPERATURA",
                "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA",
                "simulado": True,
                "temperaturaFonteC": 25,
                **change,
            })


def MetadadosAnomaliaStub(leitura):
    from app.inteligencia_artificial.aprendizado_maquina.esquemas import ResultadoAnomalia
    return ResultadoAnomalia(
        id_observacao=leitura.id_observacao,
        classificada_como_anomalia=False,
        classificacao="NAO_ATIPICA_ESTIMADA",
        pontuacao_anomalia=0.123,
        variaveis_utilizadas=["temperaturaAr", "umidadeSolo", "umidadeAr", "luminosidade"],
        data_analise=datetime.now(timezone.utc),
        data_leitura=leitura.registrado_em,
        origem_dados=leitura.origem,
        versao_modelo="isolation-forest-v3",
        configuracao_modelo={"algoritmo":"IsolationForest"},
        justificativa="Resultado técnico controlado em teste.",
    )


def test_adaptacao_persiste_quatro_indicadores_e_analise_ml(monkeypatch):
    from app.telemetria import rotas

    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseTelemetria.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(rotas, "_sessao", lambda: factory())
    monkeypatch.setattr(rotas, "obter_configuracoes", _config)
    def explicacao_mock(resultado, **kwargs):
        with factory() as observer:
            persistida = observer.scalar(select(AnaliseAnomalia))
            leitura_persistida = observer.scalar(select(Leitura))
            assert persistida is not None and leitura_persistida.analysis_status == "CONCLUIDA"
        return ResultadoExplicacaoGenerativa("CONCLUIDA", texto="Os indicadores são leituras dos sensores.")
    monkeypatch.setattr(rotas, "tentar_explicar_anomalia", explicacao_mock)
    received = {}

    class DetectorStub:
        versao_modelo = "isolation-forest-v3"
        def predizer(self, leitura):
            with factory() as observer:
                persisted = observer.scalar(select(Leitura).where(
                    Leitura.device_id == leitura.id_dispositivo,
                    Leitura.observation_id == leitura.id_observacao,
                ))
            received["persisted_before_analysis"] = persisted is not None
            received["leitura"] = leitura
            return MetadadosAnomaliaStub(leitura)

    monkeypatch.setattr(rotas, "carregar_detector_telemetria", lambda _: DetectorStub())

    result = rotas.receber(LeituraIoT.model_validate(BASE))
    assert result["values"] == {
        "temperaturaAr": 26.4,
        "umidadeSolo": 50.0,
        "umidadeAr": 60.0,
        "luminosidade": 1200.0,
    }
    assert result["units"] == {
        "temperaturaAr": "°C", "umidadeSolo": "%", "umidadeAr": "%", "luminosidade": "ADC"
    }
    assert result["analysisStatus"] == "CONCLUIDA"
    assert result["analysis"]["executed"] is True
    assert result["analysis"]["isAnomaly"] is False
    assert result["analysis"]["score"] == 0.123
    assert result["analysis"]["generativeStatus"] == "CONCLUIDA"
    assert result["analysis"]["generativeExplanation"] == "Os indicadores são leituras dos sensores."
    assert received["persisted_before_analysis"] is True
    assert received["leitura"].valores["umidadeSolo"] == 50.0
    assert received["leitura"].unidades["umidadeSolo"] == "%"

    with factory() as db:
        row = db.scalar(select(Leitura))
        assert row is not None
        assert set(row.values) == {"temperaturaAr", "umidadeSolo", "umidadeAr", "luminosidade"}
        assert row.complements["umidadeSolo"] == {
            "origem": "DHT22_TEMPERATURA",
            "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA",
            "simulado": True,
            "temperaturaFonteC": 25.0,
        }
        assert row.analysis_status == "CONCLUIDA"
        analysis = db.scalar(select(AnaliseAnomalia))
        assert analysis is not None
        assert analysis.variables == ["temperaturaAr", "umidadeSolo", "umidadeAr", "luminosidade"]
        assert analysis.score == 0.123
        assert analysis.generative_status == "CONCLUIDA"
        assert analysis.generative_explanation == "Os indicadores são leituras dos sensores."

    history = rotas.historico(limit=10)[0]
    assert history["values"]["umidadeSolo"] == 50.0
    assert history["analysis"]["status"] == "CONCLUIDA"
    assert history["analysis"]["generativeStatus"] == "CONCLUIDA"
    assert history["analysis"]["generativeExplanation"] == "Os indicadores são leituras dos sensores."
    assert rotas.status()["devices"][0]["connected"] is True



def test_falha_ml_nao_remove_captura_persistida(monkeypatch, caplog):
    from app.telemetria import rotas

    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseTelemetria.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(rotas, "_sessao", lambda: factory())
    monkeypatch.setattr(rotas, "obter_configuracoes", _config)
    monkeypatch.setattr(rotas, "tentar_explicar_anomalia", lambda *args, **kwargs: pytest.fail("Gemini não deve rodar sem análise ML"))
    def modelo_indisponivel(_):
        raise FileNotFoundError("fixture: artefato indisponível")
    monkeypatch.setattr(rotas, "carregar_detector_telemetria", modelo_indisponivel)

    result = rotas.receber(LeituraIoT.model_validate(BASE))
    assert result["analysisStatus"] == "FALHA"
    assert result["analysis"]["executed"] is False
    assert "consulte os logs" in result["analysis"]["message"].lower()
    assert "Falha na análise ML após persistir captura" in caplog.text
    with factory() as db:
        row = db.scalar(select(Leitura))
        assert row is not None
        assert row.analysis_status == "FALHA"
        assert db.scalar(select(AnaliseAnomalia)) is None


def test_falha_gemini_preserva_captura_e_resultado_ml(monkeypatch):
    from app.telemetria import rotas

    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseTelemetria.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(rotas, "_sessao", lambda: factory())
    monkeypatch.setattr(rotas, "obter_configuracoes", _config)
    monkeypatch.setattr(
        rotas,
        "tentar_explicar_anomalia",
        lambda *args, **kwargs: ResultadoExplicacaoGenerativa("FALHA", codigo_erro="GEMINI_TIMEOUT"),
    )
    monkeypatch.setattr(
        rotas,
        "carregar_detector_telemetria",
        lambda _: type(
            "Detector",
            (),
            {"versao_modelo": "isolation-forest-v3", "predizer": staticmethod(MetadadosAnomaliaStub)},
        )(),
    )

    resposta = rotas.receber(LeituraIoT.model_validate(BASE))
    assert resposta["analysisStatus"] == "CONCLUIDA"
    assert resposta["analysis"]["executed"] is True
    assert resposta["analysis"]["classification"] == "NAO_ATIPICA_ESTIMADA"
    assert resposta["analysis"]["generativeStatus"] == "FALHA"
    assert resposta["analysis"]["generativeErrorCode"] == "GEMINI_TIMEOUT"
    with factory() as db:
        assert db.scalar(select(Leitura)).analysis_status == "CONCLUIDA"
        analise = db.scalar(select(AnaliseAnomalia))
        assert analise is not None
        assert analise.is_anomaly is False
        assert analise.generative_status == "FALHA"
        assert analise.generative_error_code == "GEMINI_TIMEOUT"


def test_observation_id_repetido_continua_idempotente(monkeypatch):
    from app.telemetria import rotas

    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseTelemetria.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(rotas, "_sessao", lambda: factory())
    monkeypatch.setattr(rotas, "obter_configuracoes", _config)
    monkeypatch.setattr(rotas, "tentar_explicar_anomalia", lambda *args, **kwargs: ResultadoExplicacaoGenerativa("NAO_CONFIGURADO"))
    monkeypatch.setattr(rotas, "carregar_detector_telemetria", lambda _: type("Detector", (), {"versao_modelo":"isolation-forest-v3", "predizer":staticmethod(MetadadosAnomaliaStub)})())
    payload = LeituraIoT.model_validate(BASE)
    rotas.receber(payload)
    with pytest.raises(HTTPException) as error:
        rotas.receber(payload)
    assert error.value.status_code == 409
    with factory() as db:
        assert len(db.scalars(select(Leitura)).all()) == 1


def test_mobile_demo_permanece_fixo_e_independente():
    with TestClient(app) as client:
        response = client.get("/api/v1/mobile/demo/snapshot")
    assert response.status_code == 200
    body = response.json()
    assert body["dataMode"] == "PREDEFINED_DEMO"
    assert body["properties"][0]["fields"][0]["soilType"] == "SOLO_FICTICIO"
    assert body["indicators"]["luminosidade"]["unit"] == "ADC"


def test_tipos_jsonb_e_constraints_do_postgresql_permanecem_compativeis():
    values_column = Leitura.__table__.c.sensor_values
    assert Leitura.values.property.columns[0].name == "sensor_values"
    assert "JSONB" in values_column.type.dialect_impl(postgresql.dialect()).__class__.__name__.upper()
    assert "JSON" in values_column.type.dialect_impl(sqlite.dialect()).__class__.__name__.upper()
    assert "uq_iot_reading_observation" in {c.name for c in Leitura.__table__.constraints}
    assert "ck_iot_anomaly_variables_four" in {c.name for c in AnaliseAnomalia.__table__.constraints}


def test_falha_de_commit_reverte_dispositivo_e_leitura(monkeypatch):
    from app.telemetria import rotas

    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseTelemetria.metadata.create_all(engine)
    rollbacks = []

    class CommitFailsSession(Session):
        def commit(self):
            raise OperationalError("COMMIT", {}, RuntimeError("simulated commit failure"))
        def rollback(self):
            rollbacks.append(True)
            return super().rollback()

    monkeypatch.setattr(rotas, "_sessao", lambda: CommitFailsSession(bind=engine))
    monkeypatch.setattr(rotas, "obter_configuracoes", _config)
    with pytest.raises(HTTPException) as error:
        rotas.receber(LeituraIoT.model_validate(BASE))
    assert error.value.status_code == 503
    assert rollbacks
    with Session(engine) as db:
        assert db.scalar(select(Leitura)) is None
        assert db.scalar(select(Dispositivo)) is None
