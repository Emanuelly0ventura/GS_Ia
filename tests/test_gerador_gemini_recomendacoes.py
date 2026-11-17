import asyncio
import json

import pytest
from pydantic import ValidationError

from app.inteligencia_artificial.generativa.cliente_gemini import (
    GeminiExpirou,
    GeminiIndisponivel,
    GeminiLimiteRequisicoes,
    GeminiNaoConfigurado,
    GeminiRespostaInvalida,
)
from app.inteligencia_artificial.recomendacoes.gerador_gemini import (
    ConteudoInsuficienteParaComposicao,
    GeradorGeminiRecomendacoes,
    RespostaGeminiRecomendacoes,
)
from app.inteligencia_artificial.recomendacoes.orquestracao import (
    ContextoGeracao,
    GeradorRecomendacoes,
    _projetar,
    _validar_resposta,
)
from app.inteligencia_artificial.recomendacoes.recuperacao import carregar_catalogo, recuperar
from tests.test_recomendacoes import observacao_declarada
from tests.test_recomendacoes_wokwi import consulta


class ClienteFalso:
    def __init__(self, retorno=None, erro=None):
        self.retorno = retorno
        self.erro = erro
        self.chamadas = []

    async def gerar(self, *, instrucao, dados, esquema):
        self.chamadas.append((instrucao, dados, esquema))
        if self.erro is not None:
            raise self.erro
        if self.retorno is not None:
            return self.retorno
        return esquema.model_validate_json(json.dumps({
            "estado": "COMPOR",
            "recomendacoes": [
                {
                    "id_recomendacao": item["id_recomendacao"],
                    "ordem": "JUSTIFICATIVA_PRIMEIRO",
                    "indices_referencias": [0],
                }
                for item in reversed(dados["recomendacoes"])
            ],
        }))


@pytest.fixture
def contexto_projetado(observacao_declarada):
    contexto = consulta("tomate", umidadeSolo=75, umidadeAr=80)
    contexto = contexto.model_copy(update={
        "id_talhao": "TALHAO-PRIVADO",
        "observacoes_humanas": (observacao_declarada,),
    })
    recuperadas = recuperar(carregar_catalogo(), contexto).recomendacoes
    return contexto, ContextoGeracao(recomendacoes=tuple(map(_projetar, recuperadas)))


def test_adaptador_envia_contexto_permitido_sem_credenciais(contexto_projetado, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    consulta_selecionada, contexto = contexto_projetado
    cliente = ClienteFalso()
    gerador: GeradorRecomendacoes = GeradorGeminiRecomendacoes(
        cliente, cultura_selecionada=consulta_selecionada.cultura,
    )
    json_saida = asyncio.run(gerador.gerar(contexto))
    instrucao, dados, esquema = cliente.chamadas[0]
    assert len(cliente.chamadas) == 1
    assert esquema is RespostaGeminiRecomendacoes
    for expressao in (
        "exclusivamente o contexto", "não são medições físicas verificadas",
        "temperatura do DHT22", "umidadeAr é um indicador independente",
        "Referências PENDENTE são candidatas", "prioridade e a curadoria",
        "diagnósticos", "SEM_CONTEUDO_SUFICIENTE",
    ):
        assert expressao in instrucao

    assert set(dados) == {"cultura_selecionada", "recomendacoes"}
    assert dados["cultura_selecionada"] == "tomate"
    solo, ar = dados["recomendacoes"]
    assert solo["culturas_aplicaveis"] == ["milho", "feijão", "tomate"]
    assert [solo["id_recomendacao"], ar["id_recomendacao"]] == ["REC027", "REC030"]
    assert set(solo) == {
        "id_recomendacao", "tema", "culturas_aplicaveis", "condicoes", "orientacao",
        "justificativa", "prioridade", "estado_curadoria", "estado_apresentacao",
        "indicadores", "referencias", "ressalvas",
    }
    assert solo["indicadores"] == [{
        "indicador": "umidadeSolo", "valor": 75, "unidade": "%",
        "origem": "DHT22_TEMPERATURA", "source": "WOKWI_HIVEMQ_NODE_RED",
        "simulado": True, "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA",
    }]
    assert ar["indicadores"][0]["origem"] == "DHT22_UMIDADE"
    assert ar["indicadores"][0]["simulado"] is True
    assert "metodo" not in ar["indicadores"][0]
    assert solo["prioridade"] == contexto.recomendacoes[0].prioridade
    assert solo["estado_apresentacao"] == "PRELIMINAR"
    assert solo["estado_curadoria"] == "PENDENTE"
    assert solo["ressalvas"]
    assert all(fonte["estado_curadoria"] == "PENDENTE" for fonte in solo["referencias"])
    payload = json.dumps(dados, ensure_ascii=False, allow_nan=False)
    for privado in (
        "TALHAO-PRIVADO", "produtor", "OBS-TESTE", "Detalhe privado de teste",
        "observador_declarado", "referencia_origem", "temperaturaFonteC", "api_key",
    ):
        assert privado not in payload

    textos = _validar_resposta(json_saida, contexto.recomendacoes)
    assert [item.id_recomendacao for item in textos] == ["REC027", "REC030"]
    assert textos[0].texto == f"Orientação preliminar. {solo['justificativa']} {solo['orientacao']}"
    assert textos[0].indices_referencias == (0,)


def test_contexto_vazio_nao_chama_cliente():
    cliente = ClienteFalso()
    gerador = GeradorGeminiRecomendacoes(cliente, cultura_selecionada="tomate")
    assert json.loads(asyncio.run(gerador.gerar(ContextoGeracao(recomendacoes=())))) == {
        "recomendacoes": []
    }
    assert not cliente.chamadas


@pytest.mark.parametrize("cultura", ["", "milho"])
def test_rejeita_cultura_ausente_ou_incompativel(contexto_projetado, cultura):
    _, contexto = contexto_projetado
    cliente = ClienteFalso()
    gerador = GeradorGeminiRecomendacoes(cliente, cultura_selecionada=cultura)
    with pytest.raises(ValueError):
        asyncio.run(gerador.gerar(contexto))
    assert not cliente.chamadas


@pytest.mark.parametrize("metadado", [
    {"texto": "texto livre"}, {"prioridade": "ALTA"}, {"estado_curadoria": "REVISADA"},
    {"indicadores": [{"valor": 42}]}, {"ordem": "DIAGNOSTICO"}, {"indices_referencias": ["0"]},
])
def test_schema_rejeita_campos_alheios_ou_tipos_invalidos(metadado):
    item = {"id_recomendacao": "REC027", "ordem": "ORIENTACAO_PRIMEIRO", "indices_referencias": []}
    with pytest.raises(ValidationError):
        RespostaGeminiRecomendacoes.model_validate_json(json.dumps({
            "estado": "COMPOR", "recomendacoes": [{**item, **metadado}],
        }))


@pytest.mark.parametrize(("ids", "indices"), [
    (("REC027", "REC999"), (0,)),
    (("REC027", "REC027"), (0,)),
    (("REC027",), (0,)),
    (("REC027", "REC030"), (1,)),
    (("REC027", "REC030"), (0, 0)),
    (("REC027", "REC030"), (-1,)),
])
def test_rejeita_ids_e_indices_fora_da_selecao(contexto_projetado, ids, indices):
    _, contexto = contexto_projetado
    resposta = RespostaGeminiRecomendacoes.model_validate_json(json.dumps({
        "estado": "COMPOR",
        "recomendacoes": [
            {"id_recomendacao": id_rec, "ordem": "ORIENTACAO_PRIMEIRO",
             "indices_referencias": indices if id_rec == "REC030" else [0]}
            for id_rec in ids
        ],
    }))
    gerador = GeradorGeminiRecomendacoes(ClienteFalso(retorno=resposta), cultura_selecionada="tomate")
    with pytest.raises(GeminiRespostaInvalida):
        asyncio.run(gerador.gerar(contexto))


def test_rejeita_retorno_de_tipo_incompativel(contexto_projetado):
    _, contexto = contexto_projetado
    gerador = GeradorGeminiRecomendacoes(ClienteFalso(retorno={}), cultura_selecionada="tomate")
    with pytest.raises(GeminiRespostaInvalida):
        asyncio.run(gerador.gerar(contexto))


def test_insuficiencia_explicita_nao_produz_orientacao(contexto_projetado):
    _, contexto = contexto_projetado
    resposta = RespostaGeminiRecomendacoes(estado="SEM_CONTEUDO_SUFICIENTE", recomendacoes=())
    gerador = GeradorGeminiRecomendacoes(ClienteFalso(retorno=resposta), cultura_selecionada="tomate")
    with pytest.raises(ConteudoInsuficienteParaComposicao):
        asyncio.run(gerador.gerar(contexto))


@pytest.mark.parametrize("tipo", [
    GeminiNaoConfigurado, GeminiExpirou, GeminiLimiteRequisicoes,
    GeminiIndisponivel, GeminiRespostaInvalida,
])
def test_preserva_excecoes_tipadas_sem_repetir_chamada(contexto_projetado, tipo):
    _, contexto = contexto_projetado
    erro = tipo("Erro simulado")
    cliente = ClienteFalso(erro=erro)
    gerador = GeradorGeminiRecomendacoes(cliente, cultura_selecionada="tomate")
    with pytest.raises(tipo) as capturado:
        asyncio.run(gerador.gerar(contexto))
    assert capturado.value is erro
    assert len(cliente.chamadas) == 1
