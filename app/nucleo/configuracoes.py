from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Configuracoes(BaseSettings):
    nome_aplicacao: str = "AgroConnect AI"
    ambiente: str = "desenvolvimento"
    nivel_log: str = "INFO"
    database_url: str | None = None
    telemetry_database_url: str | None = None
    telemetry_device_timeout_seconds: int = Field(default=60, ge=10, le=86400)
    provedor_ia: str | None = None
    provedor_ia_modelo: str | None = None
    provedor_ia_url: str | None = None
    provedor_ia_api_key: SecretStr | None = None
    provedor_ia_timeout_segundos: float = Field(default=30, gt=0, le=120)
    provedor_ia_limite_tokens_resposta: int = Field(default=2048, ge=1, le=32768)
    provedor_ia_campo_limite_tokens: Literal["max_completion_tokens", "max_tokens"] = "max_completion_tokens"
    provedor_ia_limite_resposta_bytes: int = Field(default=1_000_000, ge=1024, le=20_000_000)
    rag_analise_chave_api: SecretStr | None = None
    rag_analise_permitir_sem_chave_local: bool = False
    rag_analise_rate_limit_requisicoes: int = Field(default=30, ge=1, le=10000)
    rag_analise_rate_limit_janela_segundos: int = Field(default=60, ge=1, le=3600)
    api_limite_corpo_http_bytes: int = Field(default=65536, ge=1024, le=10_000_000)
    ml_numero_estimadores: int = Field(default=200, ge=10, le=1000)
    ml_contaminacao: float = Field(default=0.05, gt=0, le=0.5)
    ml_semente_aleatoria: int = 42
    ml_minimo_observacoes: int = Field(default=32, ge=2)
    ml_caminho_modelo: Path = Path("modelos_treinados/isolation_forest.joblib")
    ml_versao_modelo: str = "isolation-forest-v2"
    rag_diretorio_documentos: Path = Path("base_conhecimento/documentos")
    rag_diretorio_indice: Path = Path("base_conhecimento/indice")
    rag_caminho_embeddings: Path = Path("modelos_embeddings/multilingual-e5-small")
    rag_identificador_modelo_embeddings: str = "intfloat/multilingual-e5-small"
    rag_revisao_embeddings: str | None = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
    rag_prefixo_consulta_embeddings: str = "query: "
    rag_prefixo_documento_embeddings: str = "passage: "
    rag_tamanho_trecho: int = Field(default=1200, ge=100, le=10000)
    rag_sobreposicao_trechos: int = Field(default=160, ge=0, le=5000)
    rag_limiar_similaridade: float = Field(default=0.85, ge=-1, le=1)
    rag_limite_trechos: int = Field(default=5, ge=1, le=20)
    rag_orcamento_contexto_bytes: int = Field(default=100_000, ge=2048, le=2_000_000)
    api_json_profundidade_maxima: int = Field(default=32, ge=1, le=128)
    rag_ingestao_limite_documento_bytes: int = Field(default=5_000_000, ge=1024, le=50_000_000)
    rag_ingestao_limite_documentos: int = Field(default=100, ge=1, le=10000)
    rag_ingestao_limite_total_bytes: int = Field(default=50_000_000, ge=1024, le=500_000_000)
    rag_ingestao_limite_metadados_bytes: int = Field(default=65536, ge=256, le=1_000_000)
    rag_ingestao_limite_trechos: int = Field(default=20000, ge=1, le=1_000_000)
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    @field_validator("nivel_log")
    @classmethod
    def validar_nivel_log(cls, valor: str) -> str:
        niveis = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalizado = valor.upper()
        if normalizado not in niveis:
            raise ValueError("NIVEL_LOG deve ser DEBUG, INFO, WARNING, ERROR ou CRITICAL")
        return normalizado

    @model_validator(mode="after")
    def validar_chunking_rag(self) -> "Configuracoes":
        if self.rag_sobreposicao_trechos >= self.rag_tamanho_trecho:
            raise ValueError("RAG_SOBREPOSICAO_TRECHOS deve ser menor que RAG_TAMANHO_TRECHO.")
        if self.rag_ingestao_limite_documento_bytes > self.rag_ingestao_limite_total_bytes:
            raise ValueError("O limite por documento não pode exceder o limite total da ingestão.")
        chave = self.rag_analise_chave_api
        if chave and chave.get_secret_value() and len(chave.get_secret_value()) < 32:
            raise ValueError("RAG_ANALISE_CHAVE_API deve conter ao menos 32 caracteres.")
        return self

@lru_cache
def obter_configuracoes() -> Configuracoes:
    return Configuracoes()
