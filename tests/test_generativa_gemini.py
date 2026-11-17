import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.inteligencia_artificial.aprendizado_maquina.caracteristicas import UNIDADES_MODELO, VARIAVEIS_MODELO
from app.inteligencia_artificial.aprendizado_maquina.esquemas import ResultadoAnomalia
from app.inteligencia_artificial.generativa.cliente_gemini import (
    GeminiExpirou,
    GeminiIndisponivel,
    GeminiLimiteRequisicoes,
    GeminiNaoConfigurado,
    GeminiRespostaInvalida,
    ProvedorGemini,
)
from app.inteligencia_artificial.generativa.esquemas import (
    EntradaExplicacaoAnomalia,
    EntradaExplicacaoCompatibilidade,
    ExplicacaoGeminiRejeitada,
    TextoExplicativo,
)
from app.inteligencia_artificial.generativa.servicos import (
    ServicoExplicacaoAnomalia,
    ServicoExplicacaoCompatibilidade,
)
from app.nucleo.configuracoes import Configuracoes
from app.inteligencia_artificial.generativa.fabrica import criar_provedor_gemini
from app.principal import tratar_erro_inesperado


def executar(corrotina):
    return asyncio.run(corrotina)


def resultado_anomalia(anomalia=True):
    return ResultadoAnomalia(
        id_observacao="obs-123",
        classificada_como_anomalia=anomalia,
        classificacao="ANOMALIA_ESTATISTICA" if anomalia else "NAO_ATIPICA_ESTIMADA",
        pontuacao_anomalia=0.715942,
        variaveis_utilizadas=list(VARIAVEIS_MODELO),
        data_analise=datetime.now(UTC),
        data_leitura=None,
        origem_dados="WOKWI",
        versao_modelo="isolation-forest-v3",
        configuracao_modelo={},
        justificativa="Resultado determinístico do detector.",
    )


def entrada_anomalia(anomalia=True):
    return EntradaExplicacaoAnomalia(
        resultado=resultado_anomalia(anomalia),
        indicadores={
            "temperaturaAr": 27.1,
            "umidadeSolo": 48.0,
            "umidadeAr": 62.0,
            "luminosidade": 1800.0,
        },
        unidades=dict(UNIDADES_MODELO),
        dados_complementares={"umidadeSoloSimulada": True},
    )


class FakeModels:
    def __init__(self, response=None, error=None, delay=0):
        self.response, self.error, self.delay = response, error, delay
        self.calls = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.response


class FakeHttpError(RuntimeError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code


class FakeClient:
    def __init__(self, models):
        self.aio = SimpleNamespace(models=models)


def test_provedor_valida_resposta_json():
    async def cenario():
        models = FakeModels(SimpleNamespace(text='{"explicacao":"Os indicadores descrevem leituras ambientais."}'))
        provider = ProvedorGemini("fake-key", "modelo-teste", cliente=FakeClient(models))
        result = await provider.gerar(instrucao="Explique os dados.", dados={"valor": 1}, esquema=TextoExplicativo)
        assert result.explicacao.startswith("Os indicadores")
        assert models.calls[0]["config"]["response_mime_type"] == "application/json"
    executar(cenario())


def test_anomalia_preserva_resultado_e_nao_envia_decisao_ao_gemini():
    async def cenario():
        models = FakeModels(SimpleNamespace(text='{"explicacao":"Os indicadores representam leituras de sensores."}'))
        service = ServicoExplicacaoAnomalia(ProvedorGemini("k", "m", cliente=FakeClient(models)))
        entrada = entrada_anomalia()
        original = entrada.model_dump(mode="json")
        saida = await service.explicar(entrada)
        assert saida.resultado.model_dump(mode="json") == original["resultado"]
        assert saida.indicadores == original["indicadores"]
        assert saida.unidades == original["unidades"]
        assert saida.dados_complementares == original["dados_complementares"]
        enviados = models.calls[0]["contents"]
        assert "pontuacao_anomalia" not in enviados
        assert "classificacao" not in enviados
        assert "0.715942" not in enviados
    executar(cenario())


def test_anomalia_rejeita_texto_normal_anomala_e_medicao_inventada():
    async def cenario():
        casos = (
            (entrada_anomalia(True), "A captura está normal."),
            (entrada_anomalia(False), "A captura está anômala."),
            (entrada_anomalia(True), "A temperatura observada foi 99 °C."),
        )
        for entrada, texto in casos:
            models = FakeModels(SimpleNamespace(text=json.dumps({"explicacao": texto})))
            service = ServicoExplicacaoAnomalia(ProvedorGemini("k", "m", cliente=FakeClient(models)))
            with pytest.raises(ExplicacaoGeminiRejeitada):
                await service.explicar(entrada)
    executar(cenario())


def test_entrada_anomalia_valida_quatro_indicadores_unidades_e_score():
    dados = entrada_anomalia().model_dump(mode="python")
    dados["indicadores"].pop("luminosidade")
    with pytest.raises(ValidationError):
        EntradaExplicacaoAnomalia.model_validate(dados)
    dados = entrada_anomalia().model_dump(mode="python")
    dados["unidades"]["umidadeSolo"] = "°C"
    with pytest.raises(ValidationError):
        EntradaExplicacaoAnomalia.model_validate(dados)


def test_compatibilidade_separa_e_preserva_resultado_deterministico():
    async def cenario():
        models = FakeModels(SimpleNamespace(text='{"explicacao":"Os critérios descrevem condições registradas no catálogo."}'))
        service = ServicoExplicacaoCompatibilidade(ProvedorGemini("k", "m", cliente=FakeClient(models)))
        entrada = EntradaExplicacaoCompatibilidade(
            tipo_semente="Milho", tipo_solo="Argiloso", resultado_regra="COMPATIVEL",
            criterios_aplicados=["Faixa de pH cadastrada"],
        )
        saida = await service.explicar(entrada)
        assert saida.resultado_regra == "COMPATIVEL"
        assert saida.criterios_aplicados == entrada.criterios_aplicados
        enviados = models.calls[0]["contents"]
        assert "resultado_regra" not in enviados
        assert "COMPATIVEL" not in enviados
    executar(cenario())


def test_compatibilidade_rejeita_contradicao_positiva_e_dados_insuficientes():
    async def cenario():
        for resultado, texto in (
            ("COMPATIVEL", "A combinação é incompatível."),
            ("DADOS_INSUFICIENTES", "A combinação é compatível."),
        ):
            models = FakeModels(SimpleNamespace(text=json.dumps({"explicacao": texto})))
            service = ServicoExplicacaoCompatibilidade(ProvedorGemini("k", "m", cliente=FakeClient(models)))
            entrada = EntradaExplicacaoCompatibilidade(
                tipo_semente="Milho", tipo_solo="Argiloso", resultado_regra=resultado,
                criterios_aplicados=["Critério cadastrado"],
            )
            with pytest.raises(ExplicacaoGeminiRejeitada):
                await service.explicar(entrada)
    executar(cenario())


def test_sem_chave_nao_chama_provedor():
    async def cenario():
        models = FakeModels(SimpleNamespace(text="{}"))
        with pytest.raises(GeminiNaoConfigurado):
            await ProvedorGemini(None, "modelo", cliente=FakeClient(models)).gerar(
                instrucao="x", dados={}, esquema=TextoExplicativo
            )
        assert not models.calls
    executar(cenario())


def test_429_timeout_e_http_generico_tem_erros_distintos_e_sanitizados():
    async def cenario():
        casos = (
            (FakeHttpError(429, "Authorization: Bearer segredo"), GeminiLimiteRequisicoes),
            (FakeHttpError(503, "Authorization: Bearer segredo"), GeminiIndisponivel),
        )
        for erro, esperado in casos:
            provider = ProvedorGemini("chave-secreta", "m", cliente=FakeClient(FakeModels(error=erro)))
            with pytest.raises(esperado) as capturado:
                await provider.gerar(instrucao="não registrar", dados={}, esquema=TextoExplicativo)
            assert capturado.value.__cause__ is None
            assert capturado.value.__suppress_context__
            assert "segredo" not in str(capturado.value)
            assert "chave-secreta" not in str(capturado.value)
        provider = ProvedorGemini("chave-secreta", "m", timeout_segundos=0.01,
                                  cliente=FakeClient(FakeModels(delay=0.1)))
        with pytest.raises(GeminiExpirou):
            await provider.gerar(instrucao="x", dados={}, esquema=TextoExplicativo)
    executar(cenario())


def test_resposta_invalida_sem_detalhe_bruto():
    async def cenario():
        for bruto in (None, "não-json", '{"campo":"segredo da resposta"}'):
            provider = ProvedorGemini("k", "m", cliente=FakeClient(FakeModels(SimpleNamespace(text=bruto))))
            with pytest.raises(GeminiRespostaInvalida) as capturado:
                await provider.gerar(instrucao="x", dados={}, esquema=TextoExplicativo)
            assert capturado.value.__cause__ is None
            assert "segredo da resposta" not in str(capturado.value)
    executar(cenario())


def test_fabrica_configura_provedor_sem_chamada_externa():
    provider = criar_provedor_gemini(Configuracoes(gemini_api_key="chave-teste", gemini_model="modelo-teste"))
    assert isinstance(provider, ProvedorGemini)


def test_erro_inesperado_nao_vaza_segredo_em_resposta_ou_log(caplog):
    segredo = "Authorization: Bearer token-super-secreto"
    resposta = executar(tratar_erro_inesperado(None, RuntimeError(segredo)))
    assert resposta.status_code == 500
    assert segredo not in resposta.body.decode("utf-8")
    assert segredo not in caplog.text
    assert "RuntimeError" in caplog.text