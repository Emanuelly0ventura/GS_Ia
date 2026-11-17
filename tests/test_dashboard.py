from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.nucleo.configuracoes import Configuracoes
from app.principal import app
from app.telemetria.banco import BaseTelemetria
from app.telemetria.modelos import AnaliseAnomalia, Dispositivo, Leitura
from sqlalchemy import create_engine


def test_dashboard_web_tem_navegacao_formulario_e_estados_vazios():
    with TestClient(app) as cliente:
        resposta = cliente.get("/dashboard")
    assert resposta.status_code == 200
    assert "AgroConnect AI" in resposta.text
    assert 'id="compatForm"' in resposta.text
    assert 'id="chartEmpty"' in resposta.text
    assert "DADOS_INSUFICIENTES" in resposta.text
    assert "/api/v1/dashboard/readings?limit=50" in resposta.text
    assert "/api/v1/agricultura/analises?limit=10" in resposta.text
    assert "setInterval(refresh, 15000)" in resposta.text


def test_configuracao_da_base_url_aceita_origem_e_rejeita_credenciais_ou_caminho():
    configuracao = Configuracoes(_env_file=None, dashboard_api_base_url="https://api.exemplo.com/")
    assert configuracao.dashboard_api_base_url == "https://api.exemplo.com"
    for url in (
        "javascript:alert(1)",
        "https://usuario:senha@api.exemplo.com",
        "https://api.exemplo.com/v1",
        "https://api.exemplo.com:99999",
    ):
        with pytest.raises(ValueError):
            Configuracoes(_env_file=None, dashboard_api_base_url=url)


def test_endpoint_dashboard_retorna_decisao_e_explicacao_em_campos_separados(monkeypatch):
    from app.telemetria import rotas

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    BaseTelemetria.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    with factory() as db:
        device = Dispositivo(device_id="dashboard-test-device", source="FIXTURE_TESTE", last_seen_at=now)
        db.add(device)
        db.flush()
        reading = Leitura(
            device_id=device.device_id,
            observation_id="dashboard-test-observation",
            measured_at=now,
            source="FIXTURE_TESTE",
            quality="VALID",
            analysis_status="CONCLUIDA",
            values={"temperaturaAr": 24.5, "umidadeSolo": 50.0, "umidadeAr": 61.0, "luminosidade": 1200.0},
            units={"temperaturaAr": "°C", "umidadeSolo": "%", "umidadeAr": "%", "luminosidade": "ADC"},
            complements={"umidadeSolo": {"simulado": True}},
        )
        db.add(reading)
        db.flush()
        db.add(AnaliseAnomalia(
            reading_id=reading.id,
            model_version="isolation-forest-v3",
            is_anomaly=False,
            score=0.123456,
            analyzed_at=now,
            variables=["temperaturaAr", "umidadeSolo", "umidadeAr", "luminosidade"],
            explanation="Justificativa determinística.",
            generative_status="CONCLUIDA",
            generative_explanation="Explicação generativa complementar.",
            generative_error_code=None,
        ))
        db.commit()

    monkeypatch.setattr(rotas, "_sessao", lambda: factory())
    monkeypatch.setattr(rotas, "obter_configuracoes", lambda: SimpleNamespace(telemetry_device_timeout_seconds=60))
    try:
        with TestClient(app) as cliente:
            resposta = cliente.get("/api/v1/dashboard/readings?limit=1")
            vazio = cliente.get("/api/v1/dashboard/readings?limit=10&device_id=sem-dados")
        assert resposta.status_code == 200
        item = resposta.json()[0]
        assert item["values"]["umidadeSolo"] == 50.0
        assert item["analysis"]["classification"] == "NAO_ATIPICA_ESTIMADA"
        assert item["analysis"]["score"] == pytest.approx(0.123456)
        assert item["analysis"]["explanation"] == "Justificativa determinística."
        assert item["analysis"]["generativeExplanation"] == "Explicação generativa complementar."
        assert item["analysis"]["generativeStatus"] == "CONCLUIDA"
        assert vazio.status_code == 200 and vazio.json() == []
    finally:
        BaseTelemetria.metadata.drop_all(engine)
        engine.dispose()
