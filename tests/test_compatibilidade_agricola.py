from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.telemetria.modelos  # Registra as tabelas existentes no metadata compartilhado.
from app.compatibilidade.modelos import AnaliseCompatibilidade, Compatibilidade, TipoSemente, TipoSolo
from app.compatibilidade.rotas import obter_sessao, roteador
from app.compatibilidade import rotas as rotas_compatibilidade
from app.inteligencia_artificial.generativa.orquestracao import ResultadoExplicacaoGenerativa
from app.compatibilidade.sementes import SEMENTES_INICIAIS, SOLOS_INICIAIS, carregar_catalogos_iniciais
from app.telemetria.banco import BaseTelemetria


@pytest.fixture
def banco_teste(monkeypatch):
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def habilitar_chaves_estrangeiras(conexao, _):
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    BaseTelemetria.metadata.create_all(engine)
    fabrica = sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(roteador)

    def sessao_teste():
        with fabrica() as sessao:
            yield sessao

    app.dependency_overrides[obter_sessao] = sessao_teste
    monkeypatch.setattr(rotas_compatibilidade, "tentar_explicar_compatibilidade", lambda **kwargs: ResultadoExplicacaoGenerativa("NAO_CONFIGURADO"))
    with TestClient(app) as cliente:
        yield cliente, fabrica
    BaseTelemetria.metadata.drop_all(engine)
    engine.dispose()


def popular(fabrica):
    with fabrica() as sessao:
        quantidade = carregar_catalogos_iniciais(sessao)
        sessao.commit()
        return quantidade


def obter_ids(fabrica, codigo_semente="ALFACE", codigo_solo="FRANCO"):
    with fabrica() as sessao:
        semente = sessao.scalar(select(TipoSemente).where(TipoSemente.codigo == codigo_semente))
        solo = sessao.scalar(select(TipoSolo).where(TipoSolo.codigo == codigo_solo))
        return semente.id, solo.id


def inserir_regra(fabrica, resultado):
    semente_id, solo_id = obter_ids(fabrica)
    with fabrica() as sessao:
        sessao.add(Compatibilidade(
            id=str(uuid4()), semente_id=semente_id, solo_id=solo_id,
            resultado=resultado, criterios=["critério de fixture para teste determinístico"],
            justificativa="Regra de fixture; não é recomendação agronômica.",
            referencia_fonte="fixture-test-only", ativo=True,
        ))
        sessao.commit()
    return semente_id, solo_id


def test_catalogos_iniciais_listam_os_cinco_registros_ativos(banco_teste):
    cliente, fabrica = banco_teste
    assert popular(fabrica) == (5, 5)
    sementes = cliente.get("/api/v1/agricultura/sementes")
    solos = cliente.get("/api/v1/agricultura/solos")
    assert sementes.status_code == 200 and len(sementes.json()) == 5
    assert solos.status_code == 200 and len(solos.json()) == 5
    assert {item["codigo"] for item in sementes.json()} == {item[1] for item in SEMENTES_INICIAIS}
    assert {item["codigo"] for item in solos.json()} == {item[1] for item in SOLOS_INICIAIS}
    paths = cliente.get("/openapi.json").json()["paths"]
    assert {"/api/v1/agricultura/sementes", "/api/v1/agricultura/solos", "/api/v1/agricultura/analises"}.issubset(paths)


def test_carga_idempotente_preserva_alteracao_administrativa(banco_teste):
    _, fabrica = banco_teste
    assert popular(fabrica) == (5, 5)
    with fabrica() as sessao:
        semente = sessao.scalar(select(TipoSemente).where(TipoSemente.codigo == "ALFACE"))
        semente.nome = "Alface cadastrada pelo administrador"
        semente.ativo = False
        sessao.commit()
    assert popular(fabrica) == (0, 0)
    with fabrica() as sessao:
        semente = sessao.scalar(select(TipoSemente).where(TipoSemente.codigo == "ALFACE"))
        assert semente.nome == "Alface cadastrada pelo administrador"
        assert semente.ativo is False


def test_analisa_regra_compativel_e_persiste_historico(banco_teste, monkeypatch):
    cliente, fabrica = banco_teste
    popular(fabrica)
    semente_id, solo_id = inserir_regra(fabrica, "COMPATIVEL")
    def explicar_depois_do_commit(**kwargs):
        with fabrica() as observadora:
            persistida = observadora.scalar(select(AnaliseCompatibilidade))
            assert persistida is not None and persistida.estado_explicacao == "PENDENTE"
            assert persistida.resultado == "COMPATIVEL"
        return ResultadoExplicacaoGenerativa("CONCLUIDA", texto="Os critérios recebidos são descritos separadamente.")
    monkeypatch.setattr(rotas_compatibilidade, "tentar_explicar_compatibilidade", explicar_depois_do_commit)
    resposta = cliente.post("/api/v1/agricultura/analises", json={"sementeId": semente_id, "soloId": solo_id})
    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["resultado"] == "COMPATIVEL"
    assert dados["criterios"] == ["critério de fixture para teste determinístico"]
    assert dados["estadoExplicacao"] == "CONCLUIDA"
    assert dados["explicacaoGemini"] == "Os critérios recebidos são descritos separadamente."
    historico = cliente.get("/api/v1/agricultura/analises?limit=5")
    assert historico.status_code == 200
    assert historico.json()[0]["resultado"] == "COMPATIVEL"
    assert historico.json()[0]["estadoExplicacao"] == "CONCLUIDA"
    assert historico.json()[0]["explicacaoGemini"] == "Os critérios recebidos são descritos separadamente."
    with fabrica() as outra_sessao:
        persistida = outra_sessao.get(AnaliseCompatibilidade, dados["id"])
        assert persistida is not None
        assert persistida.compatibilidade_id is not None
        assert persistida.semente_codigo == "ALFACE"
        assert persistida.solo_codigo == "FRANCO"
        assert persistida.estado_explicacao == "CONCLUIDA"
        assert persistida.explicacao_gemini == "Os critérios recebidos são descritos separadamente."


def test_motor_devolve_regra_incompativel(banco_teste):
    cliente, fabrica = banco_teste
    popular(fabrica)
    semente_id, solo_id = inserir_regra(fabrica, "INCOMPATIVEL")
    resposta = cliente.post("/api/v1/agricultura/analises", json={"sementeId": semente_id, "soloId": solo_id})
    assert resposta.status_code == 201
    assert resposta.json()["resultado"] == "INCOMPATIVEL"


def test_falha_gemini_preserva_resultado_deterministico_agricola(banco_teste, monkeypatch):
    cliente, fabrica = banco_teste
    popular(fabrica)
    semente_id, solo_id = inserir_regra(fabrica, "COMPATIVEL")
    monkeypatch.setattr(
        rotas_compatibilidade,
        "tentar_explicar_compatibilidade",
        lambda **kwargs: ResultadoExplicacaoGenerativa("FALHA", codigo_erro="GEMINI_TIMEOUT"),
    )

    resposta = cliente.post("/api/v1/agricultura/analises", json={"sementeId": semente_id, "soloId": solo_id})
    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["resultado"] == "COMPATIVEL"
    assert dados["criterios"]
    assert dados["estadoExplicacao"] == "FALHA"
    assert dados["codigoErroExplicacao"] == "GEMINI_TIMEOUT"
    with fabrica() as sessao:
        persistida = sessao.get(AnaliseCompatibilidade, dados["id"])
        assert persistida is not None
        assert persistida.resultado == "COMPATIVEL"
        assert persistida.estado_explicacao == "FALHA"
        assert persistida.codigo_erro_explicacao == "GEMINI_TIMEOUT"


def test_combinacao_sem_regra_e_dados_insuficientes_sem_conclusao_inventada(banco_teste, monkeypatch):
    cliente, fabrica = banco_teste
    popular(fabrica)
    semente_id, solo_id = obter_ids(fabrica)
    monkeypatch.setattr(rotas_compatibilidade, "tentar_explicar_compatibilidade", lambda **kwargs: pytest.fail("Sem critérios, Gemini não deve ser chamado"))
    resposta = cliente.post("/api/v1/agricultura/analises", json={"sementeId": semente_id, "soloId": solo_id})
    dados = resposta.json()
    assert resposta.status_code == 201
    assert dados["resultado"] == "DADOS_INSUFICIENTES"
    assert dados["criterios"] == []
    assert dados["justificativa"] is None
    assert dados["referenciaFonte"] is None
    assert dados["estadoExplicacao"] == "SEM_CRITERIOS"
    assert dados["explicacaoGemini"] is None
    with fabrica() as sessao:
        analise = sessao.get(AnaliseCompatibilidade, dados["id"])
        assert analise.compatibilidade_id is None


def test_ids_inexistentes_e_registros_inativos_sao_rejeitados(banco_teste):
    cliente, fabrica = banco_teste
    popular(fabrica)
    semente_id, solo_id = obter_ids(fabrica)
    assert cliente.post("/api/v1/agricultura/analises", json={"sementeId": str(uuid4()), "soloId": solo_id}).status_code == 404
    assert cliente.post("/api/v1/agricultura/analises", json={"sementeId": semente_id, "soloId": str(uuid4())}).status_code == 404
    with fabrica() as sessao:
        sessao.get(TipoSemente, semente_id).ativo = False
        sessao.commit()
    assert cliente.get("/api/v1/agricultura/sementes").json()
    assert cliente.post("/api/v1/agricultura/analises", json={"sementeId": semente_id, "soloId": solo_id}).status_code == 409
    with fabrica() as sessao:
        sessao.get(TipoSemente, semente_id).ativo = True
        sessao.get(TipoSolo, solo_id).ativo = False
        sessao.commit()
    assert cliente.post("/api/v1/agricultura/analises", json={"sementeId": semente_id, "soloId": solo_id}).status_code == 409


def test_payload_invalido_e_integridade_referencial(banco_teste):
    cliente, fabrica = banco_teste
    popular(fabrica)
    assert cliente.post("/api/v1/agricultura/analises", json={"sementeId": "nao-uuid", "soloId": str(uuid4())}).status_code == 422
    with fabrica() as sessao, pytest.raises(IntegrityError):
        sessao.add(Compatibilidade(
            id=str(uuid4()), semente_id=str(uuid4()), solo_id=str(uuid4()),
            resultado="COMPATIVEL", criterios=[], justificativa="fixture", referencia_fonte="fixture",
        ))
        sessao.commit()
