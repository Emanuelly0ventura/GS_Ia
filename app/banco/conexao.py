from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from app.nucleo.configuracoes import obter_configuracoes

def criar_engine_leitura(url_configurada: str) -> Engine:
    """Cria engine com transações read-only; a conta do banco também deve ser read-only."""
    url = make_url(url_configurada)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise ValueError("DATABASE_URL deve usar PostgreSQL com o driver psycopg")
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": "-c default_transaction_read_only=on"},
    )

@lru_cache
def obter_engine() -> Engine | None:
    url = obter_configuracoes().database_url
    return criar_engine_leitura(url) if url else None

def verificar_conexao() -> bool:
    engine = obter_engine()
    if engine is None:
        return False
    with engine.connect() as conexao:
        conexao.execute(text("SELECT 1"))
    return True
