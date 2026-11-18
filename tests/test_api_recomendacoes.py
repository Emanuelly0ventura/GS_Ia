from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.inteligencia_artificial.generativa.cliente_gemini import (
    GeminiIndisponivel,
    GeminiRespostaInvalida,
)
from app.inteligencia_artificial.recomendacoes.esquemas import AVISO_UMIDADE_SOLO
from app.inteligencia_artificial.recomendacoes.gerador_gemini import ConteudoInsuficienteParaComposicao
from app.principal import app
from app.rotas import recomendacoes
from app.telemetria.banco import BaseTelemetria
from app.telemetria.modelos import Dispositivo, Leitura
from tests.test_orquestracao_recomendacoes import GeradorSimulado

URL = "/api/v1/recomendacoes"
SOLICITACAO = {"deviceId": "wokwi-1", "observationId": "captura-1", "cultura": "tomate"}
ORIGEM = "WOKWI_HIVEMQ_NODE_RED"


@pytest.fixture
def cliente_e_banco(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    BaseTelemetria.metadata.create_all(engine)
    fabrica = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(recomendacoes, "obter_fabrica_sessoes", lambda: fabrica)

    def gravar(**alteracoes):
        dados = {
            "device_id": SOLICITACAO["deviceId"],
            "observation_id": SOLICITACAO["observationId"],
            "measured_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "source": ORIGEM,
            "quality": "VALID",
            "values": {"umidadeSolo": 100, "umidadeAr": 80},
            "units": {"umidadeSolo": "%", "umidadeAr": "%"},
            "complements": {"umidadeSolo": {
                "simulado": True,
                "origem": "DHT22_TEMPERATURA",
                "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA",
                "temperaturaFonteC": 35,
            }},
        }
        dados.update(alteracoes)
        with fabrica() as sessao:
            if sessao.query(Dispositivo).filter_by(device_id=dados["device_id"]).first() is None:
                sessao.add(Dispositivo(device_id=dados["device_id"], source=dados["source"]))
                sessao.flush()
            sessao.add(Leitura(**dados))
            sessao.commit()

    try:
        with TestClient(app) as cliente:
            yield cliente, gravar
    finally:
        engine.dispose()


@pytest.fixture
def gerador(monkeypatch):
    simulado = GeradorSimulado()
    monkeypatch.setitem(app.dependency_overrides, recomendacoes.obter_gerador, lambda: simulado)
    return simulado


def test_captura_persistida_usa_o_par_de_ids_e_responde_no_contrato_do_dashboard(cliente_e_banco, gerador):
    cliente, gravar = cliente_e_banco
    gravar(device_id="outro-dispositivo", values={"temperaturaAr": 20},
           units={"temperaturaAr": "°C"}, complements={})
    gravar()
    resposta = cliente.post(URL, json=SOLICITACAO)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert {nome: corpo[nome] for nome in SOLICITACAO} == SOLICITACAO
    assert corpo["estado"] == "CONCLUIDA"
    assert corpo["codigoErro"] is None
    assert [item["id"] for item in corpo["recomendacoes"]] == ["REC027", "REC030"]
    solo, ar = corpo["recomendacoes"]
    assert solo["orientacao"].startswith("Orientação preliminar.")
    assert solo["prioridade"] == "MEDIA" and solo["justificativa"]
    assert solo["estadoApresentacao"] == "PRELIMINAR" and solo["estadoCuradoria"] == "PENDENTE"
    assert AVISO_UMIDADE_SOLO in solo["ressalvas"]
    assert solo["indicadores"] == [{
        "indicador": "umidadeSolo", "valor": 100, "unidade": "%",
        "origem": "DHT22_TEMPERATURA", "simulado": True,
        "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA",
    }]
    assert ar["indicadores"][0]["origem"] == "DHT22_UMIDADE"
    assert len(gerador.chamadas) == 1
    assert gerador.chamadas[0].recomendacoes[0].indicadores[0].valor == 100
    assert any(fonte["citada"] for fonte in solo["referencias"])
    assert all(fonte["estadoCuradoria"] == "PENDENTE" for fonte in solo["referencias"])
    assert "temperaturaFonteC" not in resposta.text


def test_id_inexistente_nao_chama_o_gerador(cliente_e_banco, gerador):
    cliente, gravar = cliente_e_banco
    gravar(device_id="outro-dispositivo")
    resposta = cliente.post(URL, json=SOLICITACAO)
    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "CAPTURA_NAO_ENCONTRADA"
    assert not gerador.chamadas


@pytest.mark.parametrize("alteracao", [
    {"deviceId": " "},
    {"observationId": 1},
    {"observationId": "x" * 121},
    {"cultura": "soja"},
    {"values": {"umidadeSolo": 100}},
    {"units": {"umidadeSolo": "%"}},
    {"source": ORIGEM},
    {"complements": {"umidadeSolo": {"simulado": True}}},
])
def test_entrada_invalida_ou_procedencia_enviada_pelo_navegador_e_rejeitada(
    cliente_e_banco, gerador, monkeypatch, alteracao
):
    cliente, gravar = cliente_e_banco
    gravar()
    monkeypatch.setattr(
        recomendacoes, "obter_fabrica_sessoes",
        lambda: pytest.fail("A entrada inválida não deve chegar ao banco."),
    )
    resposta = cliente.post(URL, json={**SOLICITACAO, **alteracao})
    assert resposta.status_code == 422
    assert not gerador.chamadas


def test_captura_com_indicadores_insuficientes_preserva_exclusoes(cliente_e_banco, gerador):
    cliente, gravar = cliente_e_banco
    gravar(values={"temperaturaAr": 32}, units={"temperaturaAr": "°C"}, complements={})
    resposta = cliente.post(URL, json=SOLICITACAO)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["estado"] == "SEM_EVIDENCIA_SUFICIENTE"
    assert corpo["recomendacoes"] == []
    assert any(item["motivo"] == "INDICADOR_AUSENTE" for item in corpo["exclusoes"])
    assert not gerador.chamadas


@pytest.mark.parametrize("alteracao", [
    {"values": {"umidadeSolo": 25, "umidadeAr": 80}},
    {"complements": {}},
    {"source": "ORIGEM_NAO_SUPORTADA"},
])
def test_captura_inconsistente_ou_de_outra_origem_nao_chama_gerador(
    cliente_e_banco, gerador, alteracao
):
    cliente, gravar = cliente_e_banco
    gravar(**alteracao)
    resposta = cliente.post(URL, json=SOLICITACAO)
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "CAPTURA_INVALIDA"
    assert not gerador.chamadas


@pytest.mark.parametrize(("erro", "estado", "codigo"), [
    (GeminiIndisponivel, "FALHA_GERADOR", "GEMINI_UNAVAILABLE"),
    (GeminiRespostaInvalida, "RESPOSTA_INVALIDA", "GEMINI_INVALID_RESPONSE"),
    (None, "RESPOSTA_INVALIDA", "GEMINI_INVALID_RESPONSE"),
    (ConteudoInsuficienteParaComposicao, "SEM_CONTEUDO_SUFICIENTE", None),
])
def test_falhas_normalizadas_preservam_selecao_sem_orientacao(cliente_e_banco, gerador, erro, estado, codigo):
    cliente, gravar = cliente_e_banco
    gravar()

    def responder(_):
        if erro is not None:
            raise erro("detalhe interno confidencial")
        return "resposta malformada"

    gerador.preparar_resposta = responder
    resposta = cliente.post(URL, json=SOLICITACAO)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["estado"] == estado and corpo["codigoErro"] == codigo
    assert corpo["exclusoes"]
    assert [item["id"] for item in corpo["recomendacoes"]] == ["REC027", "REC030"]
    assert all(item["orientacao"] is None for item in corpo["recomendacoes"])
    assert all(item["estadoApresentacao"] == "PRELIMINAR" for item in corpo["recomendacoes"])
    assert "detalhe interno confidencial" not in resposta.text
    assert len(gerador.chamadas) == 1


def test_telemetria_indisponivel_retorna_falha_de_consulta(cliente_e_banco, gerador, monkeypatch):
    cliente, _ = cliente_e_banco
    monkeypatch.setattr(recomendacoes, "obter_fabrica_sessoes", lambda: None)
    resposta = cliente.post(URL, json=SOLICITACAO)
    assert resposta.status_code == 503
    assert resposta.json()["erro"]["codigo"] == "TELEMETRIA_INDISPONIVEL"
    assert not gerador.chamadas


def test_dashboard_tem_formulario_e_nenhuma_chamada_durante_carregamento(cliente_e_banco, gerador):
    cliente, _ = cliente_e_banco
    resposta = cliente.get("/dashboard")
    assert resposta.status_code == 200
    for campo in ("compatForm", "seedSelect", "soilSelect", "compatResult"):
        assert f'id="{campo}"' in resposta.text
    assert 'id="captureSelect"' not in resposta.text
    assert 'id="recommendationForm"' not in resposta.text
    chamada = "api('/api/v1/agricultura/analise-unificada'"
    antes, depois = resposta.text.split("$('compatForm').addEventListener('submit'", 1)
    assert chamada not in antes
    assert depois.count(chamada) == 1
    assert "setInterval(refresh, 15000)" in resposta.text
    assert not gerador.chamadas
