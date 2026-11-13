from functools import lru_cache
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.nucleo.configuracoes import obter_configuracoes
from app.nucleo.logging import obter_logger

logger = obter_logger(__name__)

class BaseTelemetria(DeclarativeBase):
    pass

@lru_cache
def obter_engine_telemetria():
    url = obter_configuracoes().telemetry_database_url
    if not url:
        return None
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise ValueError("TELEMETRY_DATABASE_URL deve usar PostgreSQL/psycopg.")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return create_engine(url, pool_pre_ping=True)

@lru_cache
def obter_fabrica_sessoes():
    engine = obter_engine_telemetria()
    return sessionmaker(engine, expire_on_commit=False) if engine else None

def verificar_conexao_telemetria() -> bool:
    """Verifica o PostgreSQL próprio da IA sem exigir conexão no startup."""
    engine = obter_engine_telemetria()
    if engine is None:
        return False
    try:
        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Falha ao verificar a conexão do PostgreSQL local da IA")
        return False
    return True
