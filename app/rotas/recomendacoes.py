from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.esquemas.recomendacoes import (
    ExclusaoRecomendacao,
    IndicadorRecomendacao,
    RecomendacaoPublica,
    ReferenciaRecomendacao,
    RespostaRecomendacoes,
    SolicitacaoRecomendacoes,
)
from app.inteligencia_artificial.recomendacoes.esquemas import (
    CapturaDemonstrativa,
    CatalogoRecomendacoes,
    ContextoRecuperacao,
)
from app.inteligencia_artificial.recomendacoes.orquestracao import (
    GeradorRecomendacoes,
    ResultadoGeracao,
    orquestrar,
)
from app.inteligencia_artificial.recomendacoes.recuperacao import LeituraDemonstrativa, carregar_catalogo
from app.nucleo.excecoes import ErroAplicacao
from app.telemetria.banco import obter_fabrica_sessoes
from app.telemetria.modelos import Leitura

roteador = APIRouter(prefix="/api/v1/recomendacoes", tags=["Recomendações acadêmicas"])

MENSAGENS_PUBLICAS = {
    "CONCLUIDA": "Orientação preliminar composta para a captura selecionada.",
    "SEM_EVIDENCIA_SUFICIENTE": "A captura não contém evidências suficientes para uma recomendação aplicável.",
    "SEM_CONTEUDO_SUFICIENTE": "O gerador não encontrou conteúdo suficiente para compor a orientação.",
    "FALHA_GERADOR": "Não foi possível gerar a orientação neste momento.",
    "RESPOSTA_INVALIDA": "A resposta do gerador foi rejeitada pela validação.",
}
CODIGOS_GERADOR = {
    "GEMINI_NOT_CONFIGURED", "GEMINI_TIMEOUT", "GEMINI_RATE_LIMITED",
    "GEMINI_UNAVAILABLE", "GEMINI_ERROR", "GENERATION_INTERNAL_ERROR",
}


def obter_contexto(solicitacao: SolicitacaoRecomendacoes) -> ContextoRecuperacao:
    try:
        fabrica = obter_fabrica_sessoes()
        if fabrica is None:
            raise ErroAplicacao("TELEMETRIA_INDISPONIVEL", "Banco de telemetria não configurado.", 503)
        with fabrica() as sessao:
            leitura = sessao.scalar(select(Leitura).where(
                Leitura.device_id == solicitacao.deviceId,
                Leitura.observation_id == solicitacao.observationId,
            ))
    except (SQLAlchemyError, ValueError):
        raise ErroAplicacao("TELEMETRIA_INDISPONIVEL", "Não foi possível consultar a captura.", 503) from None

    if leitura is None:
        raise ErroAplicacao("CAPTURA_NAO_ENCONTRADA", "A captura selecionada não foi encontrada.", 404)
    if leitura.quality != "VALID" or not isinstance(leitura.complements, dict):
        raise ErroAplicacao("CAPTURA_INVALIDA", "A captura armazenada não é adequada para análise.", 422)
    try:
        captura = CapturaDemonstrativa(
            source=leitura.source,
            values=leitura.values,
            units=leitura.units,
            metadados_umidade_solo=leitura.complements.get("umidadeSolo"),
        )
    except ValidationError:
        raise ErroAplicacao(
            "CAPTURA_INVALIDA", "Os valores ou a procedência da captura armazenada são inválidos.", 422
        ) from None
    return ContextoRecuperacao(cultura=solicitacao.cultura, captura_wokwi=captura)


def obter_catalogo() -> CatalogoRecomendacoes:
    try:
        return carregar_catalogo()
    except (OSError, ValueError):
        raise ErroAplicacao("CATALOGO_INDISPONIVEL", "Catálogo de recomendações indisponível.", 503) from None


def obter_gerador() -> GeradorRecomendacoes | None:
    """Permite substituir o gerador nos testes; a orquestração seleciona o padrão."""
    return None


def _resposta_publica(
    solicitacao: SolicitacaoRecomendacoes, resultado: ResultadoGeracao,
) -> RespostaRecomendacoes:
    geradas = {}
    codigo = None
    if resultado.estado == "CONCLUIDA":
        geradas = {item.id_recomendacao: item for item in resultado.orientacoes}
    elif resultado.estado == "RESPOSTA_INVALIDA":
        codigo = "GEMINI_INVALID_RESPONSE"
    elif resultado.estado == "FALHA_GERADOR":
        codigo = resultado.codigo_erro if resultado.codigo_erro in CODIGOS_GERADOR else "GENERATION_INTERNAL_ERROR"

    itens = []
    for item in resultado.recuperadas:
        gerada = geradas.get(item.id_recomendacao)
        citadas = set(gerada.indices_referencias) if gerada is not None else set()
        itens.append(RecomendacaoPublica(
            id=item.id_recomendacao,
            tema=item.tema,
            orientacao=gerada.texto if gerada is not None else None,
            justificativa=item.justificativa,
            prioridade=item.prioridade,
            indicadores=[
                IndicadorRecomendacao(
                    indicador=sinal.indicador, valor=sinal.valor, unidade=sinal.unidade,
                    origem=sinal.origem, simulado=sinal.simulado, metodo=sinal.metodo,
                ) if isinstance(sinal, LeituraDemonstrativa) else
                IndicadorRecomendacao(indicador=sinal.indicador, valor=sinal.valor)
                for sinal in item.indicadores
            ],
            referencias=[
                ReferenciaRecomendacao(
                    titulo=fonte.titulo, instituicao=fonte.instituicao,
                    localizador=fonte.localizador, estadoCuradoria=fonte.estado_curadoria,
                    citada=indice in citadas,
                )
                for indice, fonte in enumerate(item.referencias)
            ],
            ressalvas=list(item.ressalvas),
            estadoCuradoria=item.estado_curadoria,
            estadoApresentacao=item.estado_apresentacao,
        ))

    return RespostaRecomendacoes(
        deviceId=solicitacao.deviceId,
        observationId=solicitacao.observationId,
        cultura=solicitacao.cultura,
        estado=resultado.estado,
        mensagem=MENSAGENS_PUBLICAS[resultado.estado],
        codigoErro=codigo,
        recomendacoes=itens,
        exclusoes=[
            ExclusaoRecomendacao(
                idRecomendacao=exclusao.id_recomendacao,
                motivo=exclusao.motivo, indicador=exclusao.indicador,
            )
            for exclusao in resultado.exclusoes
        ],
    )


@roteador.post("", response_model=RespostaRecomendacoes)
async def solicitar_recomendacoes(
    solicitacao: SolicitacaoRecomendacoes,
    gerador: Annotated[GeradorRecomendacoes | None, Depends(obter_gerador)],
) -> RespostaRecomendacoes:
    contexto = await run_in_threadpool(obter_contexto, solicitacao)
    catalogo = await run_in_threadpool(obter_catalogo)
    resultado = await orquestrar(catalogo, contexto, gerador)
    return _resposta_publica(solicitacao, resultado)
