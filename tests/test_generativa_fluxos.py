from datetime import UTC, datetime
from types import SimpleNamespace

from app.inteligencia_artificial.aprendizado_maquina.caracteristicas import UNIDADES_MODELO, VARIAVEIS_MODELO
from app.inteligencia_artificial.aprendizado_maquina.esquemas import ResultadoAnomalia
from app.inteligencia_artificial.generativa.cliente_gemini import GeminiLimiteRequisicoes
from app.inteligencia_artificial.generativa.esquemas import TextoExplicativo
from app.inteligencia_artificial.generativa.orquestracao import (
    tentar_explicar_anomalia,
    tentar_explicar_compatibilidade,
)
from app.nucleo.configuracoes import Configuracoes


class ProvedorSimulado:
    def __init__(self, texto=None, erro=None):
        self.texto = texto
        self.erro = erro
        self.chamadas = 0

    async def gerar(self, *, instrucao, dados, esquema):
        self.chamadas += 1
        if self.erro:
            raise self.erro
        return esquema.model_validate({"explicacao": self.texto})


def configuracao_com_chave():
    return Configuracoes(_env_file=None, gemini_api_key="chave-ficticia-de-teste", gemini_model="modelo-teste")


def resultado_anomalia():
    return ResultadoAnomalia(
        id_observacao="obs-fluxo-test",
        classificada_como_anomalia=False,
        classificacao="NAO_ATIPICA_ESTIMADA",
        pontuacao_anomalia=0.12,
        variaveis_utilizadas=list(VARIAVEIS_MODELO),
        data_analise=datetime.now(UTC),
        data_leitura=None,
        origem_dados="FIXTURE_TESTE",
        versao_modelo="isolation-forest-v3",
        configuracao_modelo={},
        justificativa="Resultado oficial do fixture.",
    )


def test_sem_chave_nao_cria_cliente_nem_chama_gemini():
    provedor = ProvedorSimulado("texto válido")
    resultado = tentar_explicar_compatibilidade(
        "Milho", "Argiloso", "COMPATIVEL", ["critério de teste"],
        configuracoes=Configuracoes(_env_file=None, gemini_api_key=None),
        provedor=provedor,
    )
    assert resultado.estado == "NAO_CONFIGURADO"
    assert provedor.chamadas == 0


def test_compatibilidade_sem_criterios_pula_chamada_mesmo_configurada():
    provedor = ProvedorSimulado("texto válido")
    resultado = tentar_explicar_compatibilidade(
        "Milho", "Argiloso", "DADOS_INSUFICIENTES", [],
        configuracoes=configuracao_com_chave(), provedor=provedor,
    )
    assert resultado.estado == "SEM_CRITERIOS"
    assert provedor.chamadas == 0


def test_fluxo_anomalia_executa_explicacao_complementar_sem_alterar_resultado():
    provedor = ProvedorSimulado("Temperatura, umidade e luminosidade são leituras dos sensores.")
    resultado_oficial = resultado_anomalia()
    snapshot = resultado_oficial.model_dump(mode="json")
    saida = tentar_explicar_anomalia(
        resultado_oficial,
        indicadores={"temperaturaAr": 25.0, "umidadeSolo": 50.0, "umidadeAr": 62.0, "luminosidade": 1800.0},
        unidades=dict(UNIDADES_MODELO),
        dados_complementares={"umidadeSolo": {"simulado": True}},
        configuracoes=configuracao_com_chave(),
        provedor=provedor,
    )
    assert saida.estado == "CONCLUIDA"
    assert saida.texto.startswith("Temperatura")
    assert provedor.chamadas == 1
    assert resultado_oficial.model_dump(mode="json") == snapshot


def test_limite_gemini_vira_falha_opcional_sem_erro_para_analise():
    provedor = ProvedorSimulado(erro=GeminiLimiteRequisicoes("detalhe privado"))
    saida = tentar_explicar_anomalia(
        resultado_anomalia(),
        indicadores={"temperaturaAr": 25.0, "umidadeSolo": 50.0, "umidadeAr": 62.0, "luminosidade": 1800.0},
        unidades=dict(UNIDADES_MODELO),
        dados_complementares={},
        configuracoes=configuracao_com_chave(),
        provedor=provedor,
    )
    assert saida.estado == "FALHA"
    assert saida.codigo_erro == "GEMINI_RATE_LIMITED"
    assert saida.texto is None