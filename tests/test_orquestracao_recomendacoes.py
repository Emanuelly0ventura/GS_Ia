"""Exercita a orquestração com um simulador local e as fixtures da Etapa 1.1."""

import asyncio
import json
import socket
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.inteligencia_artificial.generativa.cliente_gemini import ProvedorGemini
from app.inteligencia_artificial.recomendacoes import orquestracao
from app.inteligencia_artificial.recomendacoes.esquemas import (
    AVISO_UMIDADE_SOLO,
    CapturaDemonstrativa,
    ContextoRecuperacao,
    Indicador,
)
from app.inteligencia_artificial.recomendacoes.orquestracao import ContextoGeracao, orquestrar
from app.inteligencia_artificial.recomendacoes.recuperacao import carregar_catalogo, recuperar
from tests.test_generativa_gemini import FakeClient, FakeHttpError, FakeModels
from tests.test_recomendacoes import catalogo, evidencias_artificiais, observacao_declarada


class GeradorSimulado:
    def __init__(self, preparar_resposta=lambda itens: json.dumps({"recomendacoes": itens})):
        self.chamadas = []
        self.preparar_resposta = preparar_resposta

    async def gerar(self, contexto: ContextoGeracao):
        self.chamadas.append(contexto)
        itens = [
            {
                "id_recomendacao": item.id_recomendacao,
                "texto": f"Orientação preliminar. {item.orientacao} {item.justificativa}",
                "indices_referencias": [0],
            }
            for item in contexto.recomendacoes
        ]
        return self.preparar_resposta(itens)


def consultar(catalogo, gerador, **dados):
    contexto = ContextoRecuperacao(cultura="milho", id_talhao="TALHAO-TESTE", **dados)
    return asyncio.run(orquestrar(catalogo, contexto, gerador))


def test_recuperacao_vazia_impede_geracao(catalogo, observacao_declarada):
    gerador = GeradorSimulado()
    resultado = consultar(
        catalogo, gerador, observacoes_humanas=(observacao_declarada,),
        indicadores={"agua_empossada": Indicador(valor=True, origem="REAL")},
    )
    assert resultado.estado == "SEM_EVIDENCIA_SUFICIENTE"
    assert "Nenhuma recomendação foi recuperada" in resultado.mensagem
    assert "evidência verificada suficiente" in resultado.mensagem
    assert "personalizada não foi gerada" in resultado.mensagem
    assert resultado.recuperadas == resultado.orientacoes == ()
    assert gerador.chamadas == []
    assert any(item.motivo == "OBSERVACAO_HUMANA_NAO_VERIFICADA" for item in resultado.exclusoes)


def test_uma_recomendacao_preliminar_preserva_metadados(catalogo, evidencias_artificiais):
    evidencias_artificiais(agua_empossada=True)
    gerador = GeradorSimulado()
    resultado = consultar(catalogo, gerador)
    assert resultado.estado == "CONCLUIDA"
    assert len(gerador.chamadas) == 1
    item, = resultado.recuperadas
    gerada, = resultado.orientacoes
    assert gerada.id_recomendacao == item.id_recomendacao == "REC001"
    assert item.estado_apresentacao == "PRELIMINAR"
    assert item.estado_curadoria == "PENDENTE"
    assert item.prioridade == catalogo.recomendacoes[0].criterio_prioridade.nivel
    assert item.referencias[0].estado_curadoria == "PENDENTE"
    assert gerada.texto.startswith("Orientação preliminar. ")


def test_envia_apenas_resultados_recuperados_e_preserva_ordem(catalogo, evidencias_artificiais):
    evidencias_artificiais(agua_empossada=True, textura_variavel_observada=True, murcha_observada=True)
    gerador = GeradorSimulado(lambda itens: json.dumps({"recomendacoes": itens[::-1]}))
    resultado = consultar(catalogo, gerador)
    esperado = ["REC001", "REC008", "REC003"]
    assert len(gerador.chamadas) == 1
    assert [item.id_recomendacao for item in gerador.chamadas[0].recomendacoes] == esperado
    assert [item.id_recomendacao for item in resultado.orientacoes] == esperado


@pytest.mark.parametrize(("campo", "valor", "diagnostico"), [
    ("estado_curadoria", "REVISADA", "FORMATO_INVALIDO"),
    ("estado_apresentacao", "REVISADA", "FORMATO_INVALIDO"),
    ("prioridade", "BAIXA", "FORMATO_INVALIDO"),
    ("evidencias", [{"indicador": "umidade", "valor": True}], "FORMATO_INVALIDO"),
    ("indices_referencias", [99], "REFERENCIAS_INVALIDAS"),
    ("indices_referencias", [0, 0], "REFERENCIAS_INVALIDAS"),
    ("indices_referencias", ["Fonte inventada"], "FORMATO_INVALIDO"),
    ("id_recomendacao", "REC999", "IDS_INVALIDOS"),
    ("id_recomendacao", "REC003", "IDS_INVALIDOS"),
    ("texto", "Orientação validada e aprovada por especialista.", "TEXTO_FORA_DO_CATALOGO"),
    ("texto", "Orientação preliminar. Aplique imediatamente.", "TEXTO_FORA_DO_CATALOGO"),
    ("texto", "O sensor mediu uma umidade de 50%.", "TEXTO_FORA_DO_CATALOGO"),
    ("texto", 42, "FORMATO_INVALIDO"),
])
def test_rejeita_inconsistencias_sem_alterar_recuperacao(
    catalogo, evidencias_artificiais, campo, valor, diagnostico
):
    evidencias_artificiais(agua_empossada=True)
    contexto = ContextoRecuperacao(cultura="milho", id_talhao="TALHAO-TESTE")
    antes = recuperar(catalogo, contexto)
    gerador = GeradorSimulado(lambda itens: json.dumps({"recomendacoes": [{**itens[0], campo: valor}]}))
    resultado = consultar(catalogo, gerador)
    assert resultado.estado == "RESPOSTA_INVALIDA"
    assert resultado.mensagem == diagnostico
    assert resultado.orientacoes == ()
    assert resultado.recuperadas[0].estado_apresentacao == "PRELIMINAR"
    assert recuperar(catalogo, contexto) == antes


@pytest.mark.parametrize(("resposta", "diagnostico"), [
    (None, "TIPO_INVALIDO"),
    ({"recomendacoes": []}, "TIPO_INVALIDO"),
    ('{"recomendacoes": [', "FORMATO_INVALIDO"),
    ('{"recomendacoes": [{"id_recomendacao": "REC001"}]}', "FORMATO_INVALIDO"),
    ('{"recomendacoes": []}', "IDS_INVALIDOS"),
])
def test_rejeita_resposta_incompleta_ou_tipo_incorreto(
    catalogo, evidencias_artificiais, resposta, diagnostico
):
    evidencias_artificiais(agua_empossada=True)
    resultado = consultar(catalogo, GeradorSimulado(lambda _: resposta))
    assert resultado.estado == "RESPOSTA_INVALIDA"
    assert resultado.mensagem == diagnostico
    assert resultado.orientacoes == ()


@pytest.mark.parametrize("duplicar", [False, True])
def test_resposta_com_multiplos_itens_e_rejeitada_por_inteiro(
    catalogo, evidencias_artificiais, duplicar
):
    evidencias_artificiais(agua_empossada=True, murcha_observada=True)

    def resposta(itens):
        segundo = itens[0] if duplicar else {**itens[1], "indices_referencias": [99]}
        return json.dumps({"recomendacoes": [itens[0], segundo]})

    resultado = consultar(catalogo, GeradorSimulado(resposta))
    assert resultado.estado == "RESPOSTA_INVALIDA"
    assert resultado.orientacoes == ()
    assert [item.id_recomendacao for item in resultado.recuperadas] == ["REC001", "REC008"]


def test_contexto_tem_projecao_explicita_sem_dados_pessoais(
    catalogo, evidencias_artificiais, observacao_declarada
):
    evidencia, = evidencias_artificiais(agua_empossada=True)
    gerador = GeradorSimulado()
    resultado = consultar(catalogo, gerador, observacoes_humanas=(observacao_declarada,))
    assert resultado.estado == "CONCLUIDA"
    consulta, = gerador.chamadas
    dados = consulta.model_dump(mode="json")
    assert set(dados) == {"recomendacoes"}
    item, = dados["recomendacoes"]
    assert set(item) == {
        "id_recomendacao", "tema", "culturas_aplicaveis", "condicoes", "orientacao",
        "justificativa", "prioridade", "estado_curadoria", "estado_apresentacao",
        "indicadores", "referencias", "ressalvas",
    }
    assert item["indicadores"] == [{"indicador": "agua_empossada", "valor": True}]
    assert set(item["referencias"][0]) == {"titulo", "instituicao", "localizador", "estado_curadoria"}
    payload = consulta.model_dump_json()
    for dado_privado in (
        observacao_declarada.observador_declarado,
        observacao_declarada.observacoes_complementares,
        observacao_declarada.id_observacao,
        evidencia.referencia_origem,
        evidencia.id_talhao,
        "referencia_origem",
        "observado_em",
    ):
        assert dado_privado not in payload


def test_falha_do_gerador_preserva_selecao_sem_expor_excecao(catalogo, evidencias_artificiais):
    evidencias_artificiais(agua_empossada=True)

    def falhar(_):
        raise RuntimeError("segredo de teste")

    contexto = ContextoRecuperacao(cultura="milho", id_talhao="TALHAO-TESTE")
    antes = recuperar(catalogo, contexto)
    gerador = GeradorSimulado(falhar)
    resultado = consultar(catalogo, gerador)
    assert len(gerador.chamadas) == 1
    assert resultado.estado == "FALHA_GERADOR"
    assert "segredo de teste" not in repr(resultado)
    assert resultado.orientacoes == ()
    assert resultado.recuperadas == gerador.chamadas[0].recomendacoes
    assert recuperar(catalogo, contexto) == antes


def test_simulador_independe_de_rede_credenciais_e_cliente_real(
    catalogo, evidencias_artificiais, monkeypatch
):
    def proibido(*args, **kwargs):
        pytest.fail("O fluxo isolado tentou usar rede ou instanciar o cliente real.")

    async def executar():
        # No Windows, o loop pode abrir um socket local durante a inicialização.
        with monkeypatch.context() as bloqueio:
            bloqueio.setattr(ProvedorGemini, "__init__", proibido)
            bloqueio.setattr(socket.socket, "connect", proibido)
            bloqueio.setattr(socket.socket, "connect_ex", proibido)
            bloqueio.setattr(socket, "getaddrinfo", proibido)
            for nome in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                bloqueio.delenv(nome, raising=False)

            evidencias_artificiais(agua_empossada=True)
            gerador = GeradorSimulado()
            contexto = ContextoRecuperacao(cultura="milho", id_talhao="TALHAO-TESTE")
            resultado = await orquestrar(catalogo, contexto, gerador)
            assert resultado.estado == "CONCLUIDA"
            assert len(gerador.chamadas) == 1

    asyncio.run(executar())


@pytest.fixture
def consulta_wokwi():
    return ContextoRecuperacao(
        cultura="tomate",
        captura_wokwi=CapturaDemonstrativa(
            source="WOKWI_HIVEMQ_NODE_RED",
            values={"umidadeSolo": 100, "umidadeAr": 80},
            units={"umidadeSolo": "%", "umidadeAr": "%"},
            metadados_umidade_solo={
                "origem": "DHT22_TEMPERATURA",
                "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA",
                "simulado": True,
                "temperaturaFonteC": 35,
            },
        ),
    )


def test_fluxo_padrao_envia_cultura_e_preserva_selecao(consulta_wokwi, monkeypatch):
    catalogo_ativo = carregar_catalogo()
    anteriores = recuperar(catalogo_ativo, consulta_wokwi).recomendacoes
    resposta = json.dumps({
        "estado": "COMPOR",
        "recomendacoes": [
            {"id_recomendacao": item.recomendacao.id, "ordem": "ORIENTACAO_PRIMEIRO",
             "indices_referencias": [0]}
            for item in reversed(anteriores)
        ],
    })
    sdk = FakeModels(SimpleNamespace(text=resposta))
    chamadas_fabrica = []

    def criar_provedor_falso():
        chamadas_fabrica.append(True)
        return ProvedorGemini("chave-ficticia", "modelo-teste", cliente=FakeClient(sdk))

    monkeypatch.setattr(orquestracao, "criar_provedor_gemini", criar_provedor_falso)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    resultado = asyncio.run(orquestrar(catalogo_ativo, consulta_wokwi))

    assert chamadas_fabrica == [True]
    chamada, = sdk.calls
    dados = json.loads(chamada["contents"])
    assert dados["cultura_selecionada"] == "tomate"
    assert resultado.estado == "CONCLUIDA"
    assert resultado.codigo_erro is None
    assert [item.id_recomendacao for item in resultado.orientacoes] == ["REC027", "REC030"]
    assert [item.id_recomendacao for item in resultado.recuperadas] == ["REC027", "REC030"]
    for item, anterior, enviado in zip(resultado.recuperadas, anteriores, dados["recomendacoes"], strict=True):
        assert item.prioridade == anterior.recomendacao.criterio_prioridade.nivel == enviado["prioridade"]
        assert item.indicadores == anterior.evidencias_utilizadas
        assert enviado["indicadores"] == [
            sinal.model_dump(mode="json", exclude_none=True) for sinal in item.indicadores
        ]
        assert item.estado_apresentacao == "PRELIMINAR"
        assert item.estado_curadoria == "PENDENTE"
        assert enviado["estado_apresentacao"] == "PRELIMINAR"
        assert enviado["estado_curadoria"] == "PENDENTE"
        assert len(item.referencias) == len(anterior.recomendacao.referencias)
        for fonte, original in zip(item.referencias, anterior.recomendacao.referencias, strict=True):
            assert fonte.localizador == original.localizador
            assert fonte.estado_curadoria == original.estado_curadoria == "PENDENTE"
        assert enviado["referencias"] == [fonte.model_dump(mode="json") for fonte in item.referencias]
        assert list(item.ressalvas) == enviado["ressalvas"]
    assert AVISO_UMIDADE_SOLO in resultado.recuperadas[0].ressalvas
    assert resultado.orientacoes[0].texto.startswith("Orientação preliminar. ")


@pytest.mark.parametrize("caso", ["sem_captura", "faltam_indicadores", "cultura_incompativel"])
def test_fluxo_padrao_bloqueia_fabrica_sem_selecao(consulta_wokwi, monkeypatch, caso):
    monkeypatch.setattr(
        orquestracao, "criar_provedor_gemini",
        lambda: pytest.fail("A recuperação vazia não deve construir o provedor."),
    )
    if caso == "sem_captura":
        consulta = ContextoRecuperacao(cultura="tomate")
    elif caso == "faltam_indicadores":
        consulta = ContextoRecuperacao(
            cultura="tomate", captura_wokwi=CapturaDemonstrativa(
                source="WOKWI_HIVEMQ_NODE_RED", values={"temperaturaAr": 32},
                units={"temperaturaAr": "°C"},
            ),
        )
    else:
        consulta = consulta_wokwi.model_copy(update={"cultura": "alface"})

    resultado = asyncio.run(orquestrar(carregar_catalogo(), consulta))
    assert resultado.estado == "SEM_EVIDENCIA_SUFICIENTE"
    assert resultado.codigo_erro is None
    assert resultado.recuperadas == resultado.orientacoes == ()
    assert resultado.exclusoes


@pytest.mark.parametrize("campo", ["values", "units"])
def test_captura_invalida_na_recuperacao_nao_chega_ao_provedor(consulta_wokwi, monkeypatch, campo):
    monkeypatch.setattr(
        orquestracao, "criar_provedor_gemini",
        lambda: pytest.fail("A captura inválida não deve construir o provedor."),
    )
    captura = consulta_wokwi.captura_wokwi
    if campo == "values":
        captura.values["umidadeSolo"] = 25
    else:
        captura.units["umidadeSolo"] = "°C"
    gerador = GeradorSimulado()
    with pytest.raises(ValidationError):
        asyncio.run(orquestrar(carregar_catalogo(), consulta_wokwi))
    with pytest.raises(ValidationError):
        asyncio.run(orquestrar(carregar_catalogo(), consulta_wokwi, gerador))
    assert not gerador.chamadas


@pytest.mark.parametrize(("caso", "estado", "codigo", "chamadas"), [
    ("sem_chave", "FALHA_GERADOR", "GEMINI_NOT_CONFIGURED", 0),
    ("timeout", "FALHA_GERADOR", "GEMINI_TIMEOUT", 1),
    ("429", "FALHA_GERADOR", "GEMINI_RATE_LIMITED", 1),
    ("503", "FALHA_GERADOR", "GEMINI_UNAVAILABLE", 1),
    ("invalida", "RESPOSTA_INVALIDA", "GEMINI_INVALID_RESPONSE", 1),
    ("insuficiencia", "SEM_CONTEUDO_SUFICIENTE", None, 1),
    ("inesperado", "FALHA_GERADOR", "GENERATION_INTERNAL_ERROR", 1),
])
def test_fluxo_padrao_controla_falhas_sem_expor_detalhes(
    consulta_wokwi, monkeypatch, caso, estado, codigo, chamadas
):
    segredo = "detalhe-interno-confidencial"

    class ProvedorInesperado:
        async def gerar(self, **kwargs):
            sdk.calls.append(kwargs)
            raise RuntimeError(segredo)

    erro = FakeHttpError(int(caso), segredo) if caso in {"429", "503"} else None
    texto = '{"estado":"SEM_CONTEUDO_SUFICIENTE","recomendacoes":[]}' if caso == "insuficiencia" else segredo
    sdk = FakeModels(
        response=SimpleNamespace(text=texto), error=erro,
        delay=0.1 if caso == "timeout" else 0,
    )
    provedor = (
        ProvedorInesperado() if caso == "inesperado" else ProvedorGemini(
            None if caso == "sem_chave" else "chave-ficticia", "modelo-teste",
            timeout_segundos=0.01, cliente=FakeClient(sdk),
        )
    )
    monkeypatch.setattr(orquestracao, "criar_provedor_gemini", lambda: provedor)
    catalogo_ativo = carregar_catalogo()
    antes = recuperar(catalogo_ativo, consulta_wokwi)
    resultado = asyncio.run(orquestrar(catalogo_ativo, consulta_wokwi))

    assert resultado.estado == estado
    assert resultado.codigo_erro == codigo
    assert len(sdk.calls) == chamadas
    assert resultado.orientacoes == ()
    assert [item.id_recomendacao for item in resultado.recuperadas] == ["REC027", "REC030"]
    assert resultado.exclusoes == antes.exclusoes
    assert recuperar(catalogo_ativo, consulta_wokwi) == antes
    assert segredo not in repr(resultado)
    assert "chave-ficticia" not in repr(resultado)
