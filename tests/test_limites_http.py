import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncByteStream, AsyncClient

from app.nucleo.limites_http import LimiteCorpoHttpMiddleware


def criar_app(limite: int = 64) -> FastAPI:
    aplicacao = FastAPI()
    aplicacao.add_middleware(LimiteCorpoHttpMiddleware, limite_bytes=limite)

    @aplicacao.post("/")
    async def ecoar(request: Request):
        return JSONResponse({"bytes": len(await request.body())})

    return aplicacao


@pytest.mark.anyio
async def test_corpo_valido_abaixo_do_limite():
    async with AsyncClient(transport=ASGITransport(app=criar_app()), base_url="http://teste") as cliente:
        resposta = await cliente.post("/", content=b"x" * 63)
    assert resposta.status_code == 200
    assert resposta.json() == {"bytes": 63}


@pytest.mark.anyio
async def test_corpo_exatamente_no_limite_e_aceito():
    async with AsyncClient(transport=ASGITransport(app=criar_app()), base_url="http://teste") as cliente:
        resposta = await cliente.post("/", content=b"x" * 64)
    assert resposta.status_code == 200
    assert resposta.json() == {"bytes": 64}


@pytest.mark.anyio
async def test_corpo_acima_do_limite_com_content_length_retorna_413_sem_detalhes():
    async with AsyncClient(transport=ASGITransport(app=criar_app()), base_url="http://teste") as cliente:
        resposta = await cliente.post("/", content=b"DADO_INTERNO_" + b"x" * 64)
    assert resposta.status_code == 413
    assert "DADO_INTERNO" not in resposta.text
    assert resposta.json()["erro"]["codigo"] == "PAYLOAD_TOO_LARGE"


class CorpoEmPartes(AsyncByteStream):
    def __init__(self, partes: list[bytes]) -> None:
        self.partes = partes

    async def __aiter__(self):
        for parte in self.partes:
            yield parte

    async def aclose(self) -> None:
        return None


@pytest.mark.anyio
async def test_corpo_sem_content_length_e_em_partes_e_limitado():
    async with AsyncClient(transport=ASGITransport(app=criar_app()), base_url="http://teste") as cliente:
        resposta = await cliente.post("/", content=CorpoEmPartes([b"a" * 30, b"b" * 35]))
    assert resposta.status_code == 413
    assert "PAYLOAD_TOO_LARGE" in resposta.text


@pytest.mark.anyio
async def test_corpo_em_partes_ate_o_limite_e_aceito_sem_content_length():
    async with AsyncClient(transport=ASGITransport(app=criar_app()), base_url="http://teste") as cliente:
        resposta = await cliente.post("/", content=CorpoEmPartes([b"a" * 30, b"b" * 34]))
    assert resposta.status_code == 200
    assert resposta.json() == {"bytes": 64}
