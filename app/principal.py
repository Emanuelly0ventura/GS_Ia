from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from app.nucleo.configuracoes import obter_configuracoes
from app.nucleo.limites_http import LimiteCorpoHttpMiddleware
from app.nucleo.logging import configurar_logging, obter_logger
from app.nucleo.excecoes import ErroAplicacao
from app.rotas.saude import roteador as roteador_saude
from app.rotas.anomalias import roteador as roteador_anomalias
from app.rotas.conhecimento import roteador as roteador_conhecimento

configurar_logging()
logger = obter_logger(__name__)
configuracoes = obter_configuracoes()

@asynccontextmanager
async def ciclo_vida(_: FastAPI):
    logger.info("Aplicação iniciada", extra={"ambiente": configuracoes.ambiente})
    yield
    logger.info("Aplicação encerrada")

app = FastAPI(
    title="AgroConnect AI",
    description=(
        "API independente de análise do AgroConnect. Nesta fase, disponibiliza "
        "health checks, demonstração estatística de anomalias e análise documental RAG local. "
        "A aplicação não consulta dados de negócio nem substitui os contratos do Backend C#."
    ),
    version="0.1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=ciclo_vida,
)
app.add_middleware(
    LimiteCorpoHttpMiddleware,
    limite_bytes=configuracoes.api_limite_corpo_http_bytes,
)
app.include_router(roteador_saude)
app.include_router(roteador_anomalias)
app.include_router(roteador_conhecimento)

@app.exception_handler(ErroAplicacao)
async def tratar_erro_aplicacao(_: Request, erro: ErroAplicacao) -> JSONResponse:
    return JSONResponse(status_code=erro.status_code, content={"erro": {"codigo": erro.codigo, "mensagem": erro.mensagem}})

@app.exception_handler(StarletteHTTPException)
async def tratar_erro_http(_: Request, erro: StarletteHTTPException) -> JSONResponse:
    mensagem = erro.detail if isinstance(erro.detail, str) else "A solicitação não pôde ser atendida."
    return JSONResponse(status_code=erro.status_code, content={"erro": {"codigo": "HTTP_ERROR", "mensagem": mensagem}}, headers=erro.headers)

@app.exception_handler(Exception)
async def tratar_erro_inesperado(_: Request, erro: Exception) -> JSONResponse:
    logger.exception("Erro inesperado durante o processamento", exc_info=erro)
    return JSONResponse(status_code=HTTP_500_INTERNAL_SERVER_ERROR, content={"erro": {"codigo": "ERRO_INTERNO", "mensagem": "Ocorreu um erro interno."}})
