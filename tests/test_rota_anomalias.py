import json
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.principal import app
from app.rotas import anomalias as rota

DADOS = json.loads((Path(__file__).parent / "fixtures" / "isolation_forest_rotulado.json").read_text(encoding="utf-8"))

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
async def test_endpoint_demo_retorna_inferencia_real(tmp_path, monkeypatch):
    from app.inteligencia_artificial.aprendizado_maquina.detector_anomalias import DetectorAnomalias
    from app.inteligencia_artificial.aprendizado_maquina.esquemas import LeituraParaModelo
    from app.nucleo.configuracoes import obter_configuracoes

    configuracoes = obter_configuracoes()
    monkeypatch.setattr(configuracoes, "ambiente", "desenvolvimento")
    monkeypatch.setattr(configuracoes, "ml_caminho_modelo", tmp_path / "modelo.joblib")
    detector = DetectorAnomalias(minimo_observacoes=32)
    detector.treinar([LeituraParaModelo.model_validate(item) for item in DADOS["treinamento"]])
    detector.salvar(configuracoes.ml_caminho_modelo)
    rota.carregar_detector_demo.cache_clear()
    valores = {nome: 7.0 for nome in DADOS["metadados"]["unidades"]}
    leitura = {
        "idObservacao": "endpoint-demo",
        "valores": valores,
        "unidades": DADOS["metadados"]["unidades"],
        "qualidade": "VALIDA",
        "origem": "SIMULADO_TESTE",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as cliente:
        resposta = await cliente.post("/api/v1/anomalias/analisar-demo", json=leitura)
    rota.carregar_detector_demo.cache_clear()
    assert resposta.status_code == 200
    assert resposta.json()["classificadaComoAnomalia"] is True

@pytest.mark.anyio
async def test_endpoint_demo_recusa_origem_nao_simulada(monkeypatch):
    from app.nucleo.configuracoes import obter_configuracoes
    monkeypatch.setattr(obter_configuracoes(), "ambiente", "desenvolvimento")
    leitura = DADOS["treinamento"][0] | {"origem": "producao"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as cliente:
        resposta = await cliente.post("/api/v1/anomalias/analisar-demo", json=leitura)
    assert resposta.status_code == 422


@pytest.mark.anyio
async def test_endpoint_demo_nao_existe_em_producao(monkeypatch):
    from app.nucleo.configuracoes import obter_configuracoes
    monkeypatch.setattr(obter_configuracoes(), "ambiente", "producao")
    leitura = DADOS["treinamento"][0]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as cliente:
        resposta = await cliente.post("/api/v1/anomalias/analisar-demo", json=leitura)
    assert resposta.status_code == 404

@pytest.mark.anyio
async def test_endpoint_demo_retorna_503_sem_artefato_treinado(tmp_path, monkeypatch):
    from app.nucleo.configuracoes import obter_configuracoes
    monkeypatch.setattr(obter_configuracoes(), "ambiente", "desenvolvimento")
    monkeypatch.setattr(obter_configuracoes(), "ml_caminho_modelo", tmp_path / "ausente.joblib")
    rota.carregar_detector_demo.cache_clear()
    leitura = DADOS["treinamento"][0]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as cliente:
        resposta = await cliente.post("/api/v1/anomalias/analisar-demo", json=leitura)
    rota.carregar_detector_demo.cache_clear()
    assert resposta.status_code == 503
