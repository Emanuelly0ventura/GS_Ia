"""Exercita a orquestração com um simulador local e as fixtures da Etapa 1.1."""

import asyncio
import json
import socket

import pytest

from app.inteligencia_artificial.generativa.cliente_gemini import ProvedorGemini
from app.inteligencia_artificial.recomendacoes.esquemas import ContextoRecuperacao, Indicador
from app.inteligencia_artificial.recomendacoes.orquestracao import ContextoGeracao, orquestrar
from app.inteligencia_artificial.recomendacoes.recuperacao import recuperar
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
