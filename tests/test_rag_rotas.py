import pytest
from httpx import ASGITransport, AsyncClient

from app.principal import app
from app.rotas.conhecimento import status_conhecimento


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


def test_status_informa_ausencia_de_fontes_pesos_indice_e_credencial(tmp_path, monkeypatch):
    from app.inteligencia_artificial.rag import fabrica
    from app.nucleo.configuracoes import Configuracoes

    monkeypatch.setattr(
        fabrica,
        "obter_configuracoes",
        lambda: Configuracoes(rag_caminho_embeddings=tmp_path / "modelo-ausente"),
    )
    estado = status_conhecimento()
    assert estado["estado"] == "CONFIGURACAO_INCOMPLETA"
    assert estado["documentos_cientificos_oficiais_verificados"] is False
    assert estado["componentes"]["documentos_locais"] == "AUSENTES"
    assert estado["componentes"]["modelo_embeddings"] == "AUSENTE"
    assert estado["componentes"]["provedor_generativo"] == "NAO_CONFIGURADO"


def test_openapi_registra_busca_analise_e_nao_expoe_ingestao():
    paths = app.openapi()["paths"]
    assert "/api/v1/conhecimento/status" in paths
    assert "/api/v1/conhecimento/buscar" in paths
    assert "/api/v1/analises/agronomicas" in paths
    assert not any("ingest" in caminho.casefold() for caminho in paths)
    parametros = paths["/api/v1/analises/agronomicas"]["post"]["parameters"]
    assert any(parametro["name"] == "X-API-Key" and parametro["in"] == "header" for parametro in parametros)


@pytest.mark.anyio
async def test_analise_sem_modelo_local_retorna_indisponibilidade_clara(tmp_path, monkeypatch):
    from app.inteligencia_artificial.rag import fabrica
    from app.rotas import conhecimento
    from app.nucleo.configuracoes import Configuracoes

    monkeypatch.setattr(
        fabrica,
        "obter_configuracoes",
        lambda: Configuracoes(rag_caminho_embeddings=tmp_path / "modelo-ausente"),
    )
    monkeypatch.setattr(
        conhecimento,
        "obter_configuracoes",
        lambda: Configuracoes(
            rag_caminho_embeddings=tmp_path / "modelo-ausente",
            rag_analise_permitir_sem_chave_local=True,
        ),
    )
    fabrica.obter_servico_rag.cache_clear()
    conhecimento.obter_servico_cacheado.cache_clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as cliente:
        resposta = await cliente.post(
            "/api/v1/analises/agronomicas",
            json={"pergunta": "Como avaliar a umidade do solo?", "dadosAgricolas": {}},
        )
    assert resposta.status_code == 503
    assert "RAG_REVISAO_EMBEDDINGS" in resposta.json()["erro"]["mensagem"] or "embeddings" in resposta.text.casefold()


@pytest.mark.anyio
async def test_json_com_profundidade_excessiva_retorna_422():
    aninhado = "fim"
    for _ in range(40):
        aninhado = {"nivel": aninhado}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as cliente:
        resposta = await cliente.post(
            "/api/v1/analises/agronomicas",
            json={"pergunta": "Como avaliar o solo?", "dadosAgricolas": aninhado},
        )
    assert resposta.status_code == 422
    assert "profundidade máxima" in resposta.json()["erro"]["mensagem"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "dados",
    [
        {f"campo_{indice}": indice for indice in range(41)},
        {"texto": "x" * 20_001},
    ],
)
async def test_limites_existentes_de_dados_agricolas_retorna_422(dados):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as cliente:
        resposta = await cliente.post(
            "/api/v1/analises/agronomicas",
            json={"pergunta": "Como avaliar o solo?", "dadosAgricolas": dados},
        )
    assert resposta.status_code == 422
