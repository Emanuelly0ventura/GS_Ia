from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.banco.conexao import verificar_conexao
from app.esquemas.saude import RespostaProntidao, RespostaSaude
from app.nucleo.configuracoes import obter_configuracoes
from app.nucleo.logging import obter_logger

roteador = APIRouter(tags=["Saúde"])
logger = obter_logger(__name__)

@roteador.get("/health", response_model=RespostaSaude, summary="Verifica a saúde da API")
def health() -> RespostaSaude:
    return RespostaSaude(status="ok", servico=obter_configuracoes().nome_aplicacao)

@roteador.get("/health/ready", response_model=RespostaProntidao, summary="Verifica a prontidão e o PostgreSQL")
def prontidao() -> Response:
    try:
        conectado = verificar_conexao()
    except (SQLAlchemyError, ValueError):
        logger.exception("Falha ao verificar a conexão PostgreSQL")
        conectado = False
    if not conectado:
        return JSONResponse(status_code=503, content={"status": "indisponivel", "banco": "nao_configurado_ou_indisponivel"})
    return JSONResponse(status_code=200, content={"status": "pronto", "banco": "conectado_somente_leitura"})
