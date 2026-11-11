from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.inteligencia_artificial.rag.esquemas import TrechoConhecimento


class AlegacaoFundamentada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: str = Field(min_length=1, max_length=3000)
    identificadores_fontes: list[str] = Field(min_length=1)


class RespostaGerada(BaseModel):
    """Estrutura exigida do modelo; alegações documentadas devem citar IDs."""

    model_config = ConfigDict(extra="forbid")

    resposta: str = Field(min_length=1, max_length=12000)
    fatos_documentados: list[AlegacaoFundamentada] = Field(default_factory=list)
    interpretacoes: list[str] = Field(default_factory=list)
    fontes_utilizadas: list[str] = Field(default_factory=list)
    evidencias_suficientes: bool
    limitacoes: list[str] = Field(default_factory=list)
    consultar_agronomo: bool = True


class FonteRecuperada(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)

    trecho: TrechoConhecimento
    similaridade_vetorial: float
    nota: str = "Similaridade vetorial não comprova relevância científica."


class RespostaAnaliseAgronomica(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)

    status: Literal["ANALISE_GERADA", "EVIDENCIA_INSUFICIENTE"]
    resposta: str
    fatos_documentados: list[AlegacaoFundamentada]
    interpretacoes: list[str]
    fontes_utilizadas: list[str]
    trechos_recuperados: list[FonteRecuperada]
    evidencias_suficientes: bool
    limitacoes: list[str]
    consultar_agronomo: bool


def validar_resposta_gerada(
    bruto: str,
    trechos_recuperados: list[tuple[TrechoConhecimento, float]],
) -> RespostaGerada:
    import json

    from pydantic import ValidationError

    try:
        resposta = RespostaGerada.model_validate_json(bruto)
    except (ValidationError, ValueError) as erro:
        raise ValueError("O provedor retornou resposta incompatível com o contrato.") from erro
    permitidos = {trecho.identificador_documento for trecho, _ in trechos_recuperados}
    citados = set(resposta.fontes_utilizadas)
    for fato in resposta.fatos_documentados:
        citados.update(fato.identificadores_fontes)
    inexistentes = citados - permitidos
    if inexistentes:
        raise ValueError("A resposta citou identificador de fonte não recuperado.")
    if not resposta.evidencias_suficientes and not resposta.consultar_agronomo:
        raise ValueError("A resposta com evidência insuficiente deve orientar revisão agronômica.")
    if resposta.evidencias_suficientes and not citados:
        raise ValueError("Resposta com evidência suficiente precisa citar fonte recuperada.")
    return resposta
