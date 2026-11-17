from contextlib import asynccontextmanager
from html import escape

from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from pathlib import Path
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from app.nucleo.configuracoes import obter_configuracoes
from app.nucleo.limites_http import LimiteCorpoHttpMiddleware
from app.nucleo.logging import configurar_logging, obter_logger
from app.nucleo.excecoes import ErroAplicacao
from app.rotas.saude import roteador as roteador_saude
from app.rotas.anomalias import roteador as roteador_anomalias
from app.telemetria.rotas import roteador_telemetria, roteador_dashboard
from app.rotas.mobile_demo import roteador as roteador_mobile_demo
from app.compatibilidade.rotas import roteador as roteador_agricultura

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
        "API independente do AgroConnect com telemetria IoT, histórico de anomalias, "
        "catálogo agrícola e análise determinística de compatibilidade. As explicações "
        "Gemini são complementares e não substituem resultados oficiais."
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
app.include_router(roteador_telemetria)
app.include_router(roteador_dashboard)
app.include_router(roteador_mobile_demo)
app.include_router(roteador_agricultura)

@app.exception_handler(ErroAplicacao)
async def tratar_erro_aplicacao(_: Request, erro: ErroAplicacao) -> JSONResponse:
    return JSONResponse(status_code=erro.status_code, content={"erro": {"codigo": erro.codigo, "mensagem": erro.mensagem}})

@app.exception_handler(StarletteHTTPException)
async def tratar_erro_http(_: Request, erro: StarletteHTTPException) -> JSONResponse:
    mensagem = erro.detail if isinstance(erro.detail, str) else "A solicitação não pôde ser atendida."
    return JSONResponse(status_code=erro.status_code, content={"erro": {"codigo": "HTTP_ERROR", "mensagem": mensagem}}, headers=erro.headers)

@app.exception_handler(Exception)
async def tratar_erro_inesperado(_: Request, erro: Exception) -> JSONResponse:
    # Registra somente o tipo, sem mensagem, traceback ou causa externa.
    logger.error("Erro inesperado durante o processamento (%s)", type(erro).__name__)
    return JSONResponse(status_code=HTTP_500_INTERNAL_SERVER_ERROR, content={"erro": {"codigo": "ERRO_INTERNO", "mensagem": "Ocorreu um erro interno."}})

@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard_web():
    pagina = (Path(__file__).resolve().parent.parent / "dashboard" / "index.html").read_text(encoding="utf-8")
    origem_api = escape(configuracoes.dashboard_api_base_url, quote=True)
    return pagina.replace("__API_BASE_URL__", origem_api)
