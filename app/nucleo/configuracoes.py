from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Configuracoes(BaseSettings):
    nome_aplicacao: str = "AgroConnect AI"
    ambiente: str = "desenvolvimento"
    nivel_log: str = "INFO"
    database_url: str | None = None
    provedor_ia: str | None = None
    provedor_ia_modelo: str | None = None
    provedor_ia_url: str | None = None
    provedor_ia_api_key: SecretStr | None = None
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    @field_validator("nivel_log")
    @classmethod
    def validar_nivel_log(cls, valor: str) -> str:
        niveis = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalizado = valor.upper()
        if normalizado not in niveis:
            raise ValueError("NIVEL_LOG deve ser DEBUG, INFO, WARNING, ERROR ou CRITICAL")
        return normalizado

@lru_cache
def obter_configuracoes() -> Configuracoes:
    return Configuracoes()
