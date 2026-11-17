import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from app.inteligencia_artificial.generativa.cliente_gemini import (
    ErroGemini,
    GeminiNaoConfigurado,
)
from app.inteligencia_artificial.generativa.esquemas import (
    EntradaExplicacaoAnomalia,
    EntradaExplicacaoCompatibilidade,
    ExplicacaoGeminiRejeitada,
)
from app.inteligencia_artificial.generativa.fabrica import criar_provedor_gemini
from app.inteligencia_artificial.generativa.servicos import (
    ServicoExplicacaoAnomalia,
    ServicoExplicacaoCompatibilidade,
)
from app.nucleo.configuracoes import Configuracoes, obter_configuracoes

logger = logging.getLogger("agroconnect.generativa.orquestracao")
EstadoExplicacao = Literal["NAO_CONFIGURADO", "SEM_CRITERIOS", "CONCLUIDA", "FALHA"]


@dataclass(frozen=True)
class ResultadoExplicacaoGenerativa:
    estado: EstadoExplicacao
    texto: str | None = None
    codigo_erro: str | None = None


def _configurado(configuracoes: Configuracoes) -> bool:
    chave = configuracoes.gemini_api_key
    return bool(
        chave
        and chave.get_secret_value().strip()
        and configuracoes.gemini_model.strip()
    )


def _executar(chamada, configuracoes: Configuracoes, provedor=None) -> ResultadoExplicacaoGenerativa:
    if not _configurado(configuracoes):
        return ResultadoExplicacaoGenerativa("NAO_CONFIGURADO")
    try:
        cliente = provedor or criar_provedor_gemini(configuracoes)
        texto = asyncio.run(chamada(cliente))
        return ResultadoExplicacaoGenerativa("CONCLUIDA", texto=texto)
    except GeminiNaoConfigurado:
        return ResultadoExplicacaoGenerativa("NAO_CONFIGURADO", codigo_erro="GEMINI_NOT_CONFIGURED")
    except ErroGemini as erro:
        return ResultadoExplicacaoGenerativa("FALHA", codigo_erro=erro.codigo)
    except ExplicacaoGeminiRejeitada:
        return ResultadoExplicacaoGenerativa("FALHA", codigo_erro="GEMINI_EXPLANATION_REJECTED")
    except Exception as erro:
        logger.error("Falha interna ao compor explicação (%s)", type(erro).__name__)
        return ResultadoExplicacaoGenerativa("FALHA", codigo_erro="GENERATION_INTERNAL_ERROR")


def tentar_explicar_anomalia(
    resultado,
    indicadores: dict[str, float],
    unidades: dict[str, str],
    dados_complementares: dict[str, object],
    configuracoes: Configuracoes | None = None,
    provedor=None,
) -> ResultadoExplicacaoGenerativa:
    configuracoes = configuracoes or obter_configuracoes()

    async def chamar(cliente) -> str:
        entrada = EntradaExplicacaoAnomalia(
            resultado=resultado,
            indicadores=indicadores,
            unidades=unidades,
            dados_complementares=dados_complementares,
        )
        saida = await ServicoExplicacaoAnomalia(cliente).explicar(entrada)
        return saida.explicacao

    return _executar(chamar, configuracoes, provedor)


def tentar_explicar_compatibilidade(
    tipo_semente: str,
    tipo_solo: str,
    resultado_regra: str,
    criterios: list[str],
    configuracoes: Configuracoes | None = None,
    provedor=None,
) -> ResultadoExplicacaoGenerativa:
    if not criterios:
        return ResultadoExplicacaoGenerativa("SEM_CRITERIOS")
    configuracoes = configuracoes or obter_configuracoes()

    async def chamar(cliente) -> str:
        entrada = EntradaExplicacaoCompatibilidade(
            tipo_semente=tipo_semente,
            tipo_solo=tipo_solo,
            resultado_regra=resultado_regra,
            criterios_aplicados=criterios,
        )
        saida = await ServicoExplicacaoCompatibilidade(cliente).explicar(entrada)
        return saida.explicacao

    return _executar(chamar, configuracoes, provedor)