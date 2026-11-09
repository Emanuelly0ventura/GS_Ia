from datetime import datetime
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.inteligencia_artificial.aprendizado_maquina.caracteristicas import VARIAVEIS_MODELO

class LeituraParaModelo(BaseModel):
    """Contrato interno provisório; o adaptador externo fará o mapeamento futuro."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    id_observacao: str = Field(min_length=1, max_length=120)
    id_dispositivo: str | None = None
    registrado_em: datetime | None = None
    valores: dict[str, float | None]
    unidades: dict[str, str]
    qualidade: Literal["VALIDA", "INVALIDA", "NAO_AVALIADA"]
    origem: str = Field(min_length=1, max_length=80)

    @field_validator("valores", mode="before")
    @classmethod
    def validar_valores_numericos(cls, valor: object) -> object:
        if not isinstance(valor, dict):
            raise ValueError("valores deve ser um objeto com números ou null.")
        resultado: dict[str, float | None] = {}
        for nome, numero in valor.items():
            if nome not in VARIAVEIS_MODELO:
                raise ValueError(f"Variável não reconhecida pelo contrato interno: {nome}.")
            if numero is None:
                resultado[nome] = None
                continue
            if isinstance(numero, bool) or not isinstance(numero, (int, float)):
                raise ValueError(f"A variável {nome} deve ser numérica ou null.")
            if not math.isfinite(float(numero)):
                raise ValueError(f"A variável {nome} precisa ser um número finito.")
            resultado[nome] = float(numero)
        return resultado

    @field_validator("unidades")
    @classmethod
    def validar_unidades(cls, valor: dict[str, str]) -> dict[str, str]:
        if set(valor) - set(VARIAVEIS_MODELO):
            raise ValueError("unidades contém variáveis não reconhecidas pelo contrato interno.")
        if any(not isinstance(unidade, str) or not unidade.strip() for unidade in valor.values()):
            raise ValueError("Cada unidade informada deve ser uma string não vazia.")
        return {nome: unidade.strip() for nome, unidade in valor.items()}

    @field_validator("origem")
    @classmethod
    def validar_origem(cls, valor: str) -> str:
        origem = valor.strip()
        if not origem:
            raise ValueError("origem deve identificar a procedência dos dados.")
        return origem

class ResultadoAnomalia(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id_observacao: str
    classificada_como_anomalia: bool
    classificacao: Literal["ANOMALIA_ESTATISTICA", "NAO_ATIPICA_ESTIMADA"]
    pontuacao_anomalia: float
    variaveis_utilizadas: list[str]
    data_analise: datetime
    data_leitura: datetime | None
    origem_dados: str
    versao_modelo: str
    configuracao_modelo: dict[str, object]
    justificativa: str
