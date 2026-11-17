from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

ResultadoRegra = Literal["COMPATIVEL", "INCOMPATIVEL", "DADOS_INSUFICIENTES"]


class ContratoApi(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class ItemCatalogo(ContratoApi):
    id: UUID
    codigo: str
    nome: str


class EntradaAnaliseCompatibilidade(ContratoApi):
    semente_id: UUID
    solo_id: UUID


class SementeSelecionada(ContratoApi):
    id: UUID
    codigo: str
    nome: str


class SoloSelecionado(ContratoApi):
    id: UUID
    codigo: str
    nome: str


class RespostaAnaliseCompatibilidade(ContratoApi):
    id: UUID
    semente: SementeSelecionada
    solo: SoloSelecionado
    resultado: ResultadoRegra
    criterios: list[str] = Field(default_factory=list)
    justificativa: str | None = None
    referencia_fonte: str | None = None
    analisado_em: datetime
    explicacao_gemini: str | None = None
    estado_explicacao: Literal["PENDENTE", "NAO_CONFIGURADO", "SEM_CRITERIOS", "CONCLUIDA", "FALHA"]
    codigo_erro_explicacao: str | None = None