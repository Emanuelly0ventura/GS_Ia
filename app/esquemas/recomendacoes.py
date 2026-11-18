from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.inteligencia_artificial.recomendacoes.esquemas import EstadoCuradoria, Prioridade
from app.inteligencia_artificial.recomendacoes.recuperacao import MotivoExclusao

Cultura = Literal["milho", "feijão", "tomate"]
IdCaptura = Annotated[str, StringConstraints(min_length=1, max_length=120)]
EstadoRecomendacoes = Literal[
    "CONCLUIDA",
    "SEM_EVIDENCIA_SUFICIENTE",
    "SEM_CONTEUDO_SUFICIENTE",
    "FALHA_GERADOR",
    "RESPOSTA_INVALIDA",
]


class SolicitacaoRecomendacoes(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    deviceId: IdCaptura
    observationId: IdCaptura
    cultura: Cultura

    @field_validator("deviceId", "observationId")
    @classmethod
    def validar_identificador(cls, valor: str) -> str:
        if not valor.strip() or not valor.isprintable():
            raise ValueError("Informe um identificador de captura válido.")
        return valor


class IndicadorRecomendacao(BaseModel):
    indicador: str
    valor: float | bool
    unidade: str | None = None
    origem: str | None = None
    simulado: bool | None = None
    metodo: str | None = None


class ReferenciaRecomendacao(BaseModel):
    titulo: str
    instituicao: str
    localizador: str
    estadoCuradoria: EstadoCuradoria
    citada: bool


class RecomendacaoPublica(BaseModel):
    id: str
    tema: str
    orientacao: str | None
    justificativa: str
    prioridade: Prioridade
    indicadores: list[IndicadorRecomendacao]
    referencias: list[ReferenciaRecomendacao]
    ressalvas: list[str]
    estadoCuradoria: EstadoCuradoria
    estadoApresentacao: Literal["PRELIMINAR", "REVISADA"]


class ExclusaoRecomendacao(BaseModel):
    idRecomendacao: str
    motivo: MotivoExclusao
    indicador: str | None


class RespostaRecomendacoes(BaseModel):
    deviceId: str
    observationId: str
    cultura: Cultura
    estado: EstadoRecomendacoes
    codigoErro: str | None
    mensagem: str
    recomendacoes: list[RecomendacaoPublica]
    exclusoes: list[ExclusaoRecomendacao]
