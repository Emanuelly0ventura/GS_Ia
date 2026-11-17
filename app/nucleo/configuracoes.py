from functools import lru_cache
import math
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Configuracoes(BaseSettings):
    nome_aplicacao: str = "AgroConnect AI"
    ambiente: str = "desenvolvimento"
    nivel_log: str = "INFO"
    telemetry_database_url: str | None = None
    telemetry_device_timeout_seconds: int = Field(default=60, ge=10, le=86400)
    telemetry_soil_moisture_temp_min_c: float = 15.0
    telemetry_soil_moisture_temp_max_c: float = 35.0
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_timeout_segundos: float = Field(default=20, gt=0, le=120)
    api_limite_corpo_http_bytes: int = Field(default=65536, ge=1024, le=10_000_000)
    dashboard_api_base_url: str = ""
    ml_numero_estimadores: int = Field(default=200, ge=10, le=1000)
    ml_contaminacao: float = Field(default=0.05, gt=0, le=0.5)
    ml_semente_aleatoria: int = 42
    ml_minimo_observacoes: int = Field(default=32, ge=2)
    ml_caminho_modelo: Path = Path("modelos_treinados/isolation_forest.joblib")
    ml_versao_modelo: str = "isolation-forest-v3"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    @field_validator("nivel_log")
    @classmethod
    def validar_nivel_log(cls, valor: str) -> str:
        niveis = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalizado = valor.upper()
        if normalizado not in niveis:
            raise ValueError("NIVEL_LOG deve ser DEBUG, INFO, WARNING, ERROR ou CRITICAL")
        return normalizado

    @field_validator("dashboard_api_base_url")
    @classmethod
    def validar_url_api_dashboard(cls, valor: str) -> str:
        valor = valor.strip().rstrip("/")
        if not valor:
            return ""
        partes = urlsplit(valor)
        if (
            partes.scheme not in {"http", "https"}
            or not partes.hostname
            or partes.username is not None
            or partes.password is not None
            or partes.path not in {"", "/"}
            or partes.query
            or partes.fragment
        ):
            raise ValueError("DASHBOARD_API_BASE_URL deve conter somente a origem HTTP(S), sem credenciais ou caminho.")
        try:
            _ = partes.port
        except ValueError as erro:
            raise ValueError("DASHBOARD_API_BASE_URL contém uma porta inválida.") from erro
        return valor

    @model_validator(mode="after")
    def validar_configuracoes(self) -> "Configuracoes":
        limites_umidade_solo = (
            self.telemetry_soil_moisture_temp_min_c,
            self.telemetry_soil_moisture_temp_max_c,
        )
        if not all(math.isfinite(valor) for valor in limites_umidade_solo):
            raise ValueError("Os limites da conversão de umidade devem ser valores finitos.")
        if limites_umidade_solo[0] >= limites_umidade_solo[1]:
            raise ValueError("O limite inferior da conversão de umidade deve ser menor que o superior.")
        return self

@lru_cache
def obter_configuracoes() -> Configuracoes:
    return Configuracoes()
