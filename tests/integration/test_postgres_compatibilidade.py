import os
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.compatibilidade.modelos import AnaliseCompatibilidade, Compatibilidade, TipoSemente, TipoSolo
from app.compatibilidade.rotas import obter_sessao, roteador
from app.compatibilidade import rotas as rotas_compatibilidade
from app.inteligencia_artificial.generativa.orquestracao import ResultadoExplicacaoGenerativa

pytestmark = pytest.mark.integration
DATABASE_URL = os.getenv("TEST_TELEMETRY_DATABASE_URL")


@pytest.fixture(scope="module")
def postgres_catalogo():
    if not DATABASE_URL:
        pytest.skip("Defina TEST_TELEMETRY_DATABASE_URL para um PostgreSQL cujo nome termine em _test.")
    url = make_url(DATABASE_URL)
    if not url.drivername.startswith("postgresql") or not (url.database or "").endswith("_test"):
        pytest.fail("TEST_TELEMETRY_DATABASE_URL deve apontar exclusivamente para PostgreSQL com banco _test.")
    from sqlalchemy import create_engine
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    fabrica = sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(roteador)

    def sessao_teste():
        with fabrica() as sessao:
            yield sessao

    app.dependency_overrides[obter_sessao] = sessao_teste
    with TestClient(app) as cliente:
        yield cliente, fabrica
    engine.dispose()


@pytest.fixture
def criar_solo_teste(postgres_catalogo):
    _, fabrica = postgres_catalogo
    identidade = str(uuid4())

    def criar():
        with fabrica() as sessao:
            sessao.add(TipoSolo(id=identidade, codigo=identidade, nome="Solo temporário"))
            sessao.commit()
        return identidade

    yield criar
    with fabrica() as sessao:
        solo = sessao.get(TipoSolo, identidade)
        if solo is not None:
            sessao.delete(solo)
            sessao.commit()


def test_postgres_catalogos_e_analise_sem_regra_persistida(postgres_catalogo, monkeypatch, criar_solo_teste):
    cliente, fabrica = postgres_catalogo
    monkeypatch.setattr(
        rotas_compatibilidade,
        "tentar_explicar_compatibilidade",
        lambda **kwargs: pytest.fail("Sem critérios, Gemini não deve ser chamado"),
    )
    sementes = cliente.get("/api/v1/agricultura/sementes")
    solos = cliente.get("/api/v1/agricultura/solos")
    assert sementes.status_code == 200 and len(sementes.json()) == 5
    assert solos.status_code == 200 and len(solos.json()) == 5

    with fabrica() as sessao:
        semente = sessao.scalar(select(TipoSemente).where(TipoSemente.codigo == "ALFACE"))
        solo = sessao.get(TipoSolo, criar_solo_teste())
        assert semente is not None and solo is not None
        assert sessao.scalar(select(Compatibilidade).where(
            Compatibilidade.semente_id == semente.id,
            Compatibilidade.solo_id == solo.id,
            Compatibilidade.ativo.is_(True),
        )) is None
        semente_id, solo_id = semente.id, solo.id

    resposta = cliente.post("/api/v1/agricultura/analises", json={"sementeId": semente_id, "soloId": solo_id})
    assert resposta.status_code == 201
    assert resposta.json()["resultado"] == "DADOS_INSUFICIENTES"
    analise_id = resposta.json()["id"]
    with fabrica() as sessao:
        persistida = sessao.get(AnaliseCompatibilidade, analise_id)
        assert persistida is not None
        assert persistida.compatibilidade_id is None
        assert persistida.estado_explicacao == "SEM_CRITERIOS"
        sessao.delete(persistida)
        sessao.commit()


def test_postgres_analise_aplica_regra_ativa_e_limpa_fixture(postgres_catalogo, monkeypatch, criar_solo_teste):
    cliente, fabrica = postgres_catalogo
    def explicar_por_mock(**kwargs):
        with fabrica() as observadora:
            pendente = observadora.scalar(select(AnaliseCompatibilidade))
            assert pendente is not None
            assert pendente.estado_explicacao == "PENDENTE"
            assert pendente.resultado == "COMPATIVEL"
        return ResultadoExplicacaoGenerativa("CONCLUIDA", texto="Explicação PostgreSQL de teste.")
    monkeypatch.setattr(rotas_compatibilidade, "tentar_explicar_compatibilidade", explicar_por_mock)
    with fabrica() as sessao:
        semente = sessao.scalar(select(TipoSemente).where(TipoSemente.codigo == "TOMATE"))
        solo = sessao.get(TipoSolo, criar_solo_teste())
        assert semente is not None and solo is not None
        regra_id = str(uuid4())
        sessao.add(Compatibilidade(
            id=regra_id,
            semente_id=semente.id,
            solo_id=solo.id,
            resultado="COMPATIVEL",
            criterios=["fixture de integração; não representa recomendação agronômica"],
            justificativa="Regra transitória usada somente para validar a persistência.",
            referencia_fonte="fixture-test-only",
            ativo=True,
        ))
        sessao.commit()
        semente_id, solo_id = semente.id, solo.id
    analise_id = None
    try:
        resposta = cliente.post("/api/v1/agricultura/analises", json={"sementeId": semente_id, "soloId": solo_id})
        assert resposta.status_code == 201
        dados = resposta.json()
        analise_id = dados["id"]
        assert dados["resultado"] == "COMPATIVEL"
        assert dados["criterios"][0].startswith("fixture de integração")
        assert dados["estadoExplicacao"] == "CONCLUIDA"
        assert dados["explicacaoGemini"] == "Explicação PostgreSQL de teste."
        with fabrica() as sessao:
            persistida = sessao.get(AnaliseCompatibilidade, analise_id)
            assert persistida is not None
            assert persistida.resultado == "COMPATIVEL"
            assert persistida.estado_explicacao == "CONCLUIDA"
            assert persistida.explicacao_gemini == "Explicação PostgreSQL de teste."
    finally:
        with fabrica() as sessao:
            if analise_id:
                analise = sessao.get(AnaliseCompatibilidade, analise_id)
                if analise is not None:
                    sessao.delete(analise)
            regra = sessao.get(Compatibilidade, regra_id)
            if regra is not None:
                sessao.delete(regra)
            sessao.commit()
