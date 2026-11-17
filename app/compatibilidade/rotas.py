import logging
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.compatibilidade.esquemas import (
    EntradaAnaliseCompatibilidade,
    ItemCatalogo,
    RespostaAnaliseCompatibilidade,
)
from app.inteligencia_artificial.generativa.orquestracao import ResultadoExplicacaoGenerativa, tentar_explicar_compatibilidade
from app.compatibilidade.servicos import (
    RegistroInativo,
    RegistroNaoEncontrado,
    ServicoAnaliseCompatibilidade,
    ServicoCatalogoAgricola,
)
from app.compatibilidade.modelos import AnaliseCompatibilidade
from app.telemetria.banco import obter_fabrica_sessoes

logger = logging.getLogger("agroconnect.compatibilidade")
roteador = APIRouter(prefix="/api/v1/agricultura", tags=["Catálogo e compatibilidade agrícola"])
_catalogo = ServicoCatalogoAgricola()
_analise = ServicoAnaliseCompatibilidade()


def obter_sessao() -> Generator[Session, None, None]:
    fabrica = obter_fabrica_sessoes()
    if fabrica is None:
        raise HTTPException(status_code=503, detail="Banco local não configurado.")
    with fabrica() as sessao:
        yield sessao


def _tratar_erro_banco(erro: SQLAlchemyError) -> HTTPException:
    logger.error("Falha de persistência no módulo agrícola (%s)", type(erro).__name__)
    return HTTPException(status_code=503, detail="Não foi possível consultar ou registrar a análise.")


@roteador.get("/sementes", response_model=list[ItemCatalogo], summary="Lista sementes ativas")
def listar_sementes(sessao: Session = Depends(obter_sessao)):
    try:
        return _catalogo.listar_sementes_ativas(sessao)
    except SQLAlchemyError as erro:
        raise _tratar_erro_banco(erro) from None


@roteador.get("/solos", response_model=list[ItemCatalogo], summary="Lista tipos de solo ativos")
def listar_solos(sessao: Session = Depends(obter_sessao)):
    try:
        return _catalogo.listar_solos_ativos(sessao)
    except SQLAlchemyError as erro:
        raise _tratar_erro_banco(erro) from None


@roteador.get(
    "/analises",
    response_model=list[RespostaAnaliseCompatibilidade],
    summary="Lista análises agrícolas recentes",
)
def listar_analises(
    limit: int = Query(20, ge=1, le=100),
    sessao: Session = Depends(obter_sessao),
):
    try:
        return list(
            sessao.scalars(
                select(AnaliseCompatibilidade)
                .options(
                    joinedload(AnaliseCompatibilidade.semente),
                    joinedload(AnaliseCompatibilidade.solo),
                )
                .order_by(desc(AnaliseCompatibilidade.analisado_em))
                .limit(limit)
            )
        )
    except SQLAlchemyError as erro:
        raise _tratar_erro_banco(erro) from None


@roteador.post(
    "/analises",
    response_model=RespostaAnaliseCompatibilidade,
    status_code=201,
    summary="Analisa e persiste uma combinação de semente e solo",
)
def analisar_compatibilidade(
    entrada: EntradaAnaliseCompatibilidade,
    sessao: Session = Depends(obter_sessao),
):
    try:
        analise = _analise.analisar(sessao, str(entrada.semente_id), str(entrada.solo_id))
        analise.estado_explicacao = "PENDENTE"
        sessao.commit()
    except RegistroNaoEncontrado as erro:
        sessao.rollback()
        raise HTTPException(status_code=404, detail=str(erro)) from None
    except RegistroInativo as erro:
        sessao.rollback()
        raise HTTPException(status_code=409, detail=str(erro)) from None
    except SQLAlchemyError as erro:
        sessao.rollback()
        raise _tratar_erro_banco(erro) from None

    resposta_deterministica = {
        "id": analise.id,
        "semente": {"id": analise.semente_id, "codigo": analise.semente_codigo, "nome": analise.semente_nome},
        "solo": {"id": analise.solo_id, "codigo": analise.solo_codigo, "nome": analise.solo_nome},
        "resultado": analise.resultado,
        "criterios": list(analise.criterios),
        "justificativa": analise.justificativa,
        "referenciaFonte": analise.referencia_fonte,
        "analisadoEm": analise.analisado_em,
    }

    if analise.compatibilidade_id is None or not analise.criterios:
        explicacao = ResultadoExplicacaoGenerativa("SEM_CRITERIOS")
    else:
        try:
            explicacao = tentar_explicar_compatibilidade(
                tipo_semente=analise.semente_nome,
                tipo_solo=analise.solo_nome,
                resultado_regra=analise.resultado,
                criterios=analise.criterios,
            )
        except Exception as erro:
            logger.error("Falha inesperada na explicação agrícola (%s)", type(erro).__name__)
            explicacao = ResultadoExplicacaoGenerativa("FALHA", codigo_erro="GENERATION_INTERNAL_ERROR")

    try:
        analise_persistida = sessao.get(type(analise), analise.id)
        if analise_persistida is None:
            raise RuntimeError("registro de análise ausente")
        analise_persistida.estado_explicacao = explicacao.estado
        analise_persistida.explicacao_gemini = explicacao.texto
        analise_persistida.codigo_erro_explicacao = explicacao.codigo_erro
        sessao.commit()
    except Exception as erro:
        sessao.rollback()
        logger.error("Falha ao persistir explicação agrícola (%s)", type(erro).__name__)
        explicacao = ResultadoExplicacaoGenerativa("FALHA", codigo_erro="EXPLANATION_PERSISTENCE_FAILED")

    return {
        **resposta_deterministica,
        "explicacaoGemini": explicacao.texto,
        "estadoExplicacao": explicacao.estado,
        "codigoErroExplicacao": explicacao.codigo_erro,
    }
