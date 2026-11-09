import pytest
from httpx import ASGITransport, AsyncClient

from app.principal import app

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as cliente:
        resposta = await cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"

@pytest.mark.anyio
async def test_openapi_disponivel():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as cliente:
        resposta = await cliente.get("/openapi.json")
    assert resposta.status_code == 200
    especificacao = resposta.json()
    assert especificacao["info"]["title"] == "AgroConnect AI"
    assert "/health/ready" in especificacao["paths"]

@pytest.mark.anyio
async def test_prontidao_sem_banco_configurado(monkeypatch):
    monkeypatch.setattr("app.rotas.saude.verificar_conexao", lambda: False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as cliente:
        resposta = await cliente.get("/health/ready")
    assert resposta.status_code == 503
    assert resposta.json()["status"] == "indisponivel"
