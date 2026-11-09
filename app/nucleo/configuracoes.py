from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
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
    ml_numero_estimadores: int = Field(default=200, ge=10, le=1000)
    ml_contaminacao: float = Field(default=0.05, gt=0, le=0.5)
    ml_semente_aleatoria: int = 42
    ml_minimo_observacoes: int = Field(default=32, ge=2)
    ml_caminho_modelo: Path = Path("modelos_treinados/isolation_forest.joblib")
    ml_versao_modelo: str = "isolation-forest-v1"
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
