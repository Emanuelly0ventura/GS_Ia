from datetime import datetime
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

# O Node-RED envia os quatro sensores; umidadeSolo ainda carrega a temperatura
# bruta do DHT22 em °C e é convertida pelo backend antes da persistência.
VARIAVEIS_ENTRADA = {"temperaturaAr", "umidadeSolo", "umidadeAr", "luminosidade"}
UNIDADES_ENTRADA = {
    "temperaturaAr": "°C",
    "umidadeSolo": "°C",
    "umidadeAr": "%",
    "luminosidade": "ADC",
}
UNIDADES_CANONICAS = {
    "temperaturaAr": "°C",
    "umidadeSolo": "%",
    "umidadeAr": "%",
    "luminosidade": "ADC",
}


class MetadadosUmidadeSolo(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    origem: Literal["DHT22_TEMPERATURA"]
    metodo: Literal["CONVERSAO_LINEAR_DEMONSTRATIVA"]
    simulado: Literal[True]
    temperatura_fonte_c: float

    @field_validator("temperatura_fonte_c")
    @classmethod
    def temperatura_finita(cls, valor: float) -> float:
        if not math.isfinite(valor):
            raise ValueError("temperaturaFonteC deve ser finita.")
        return valor


class LeituraIoT(BaseModel):
    """Contrato Node-RED; umidadeSolo de entrada é temperatura bruta DHT22."""

    model_config = ConfigDict(extra="forbid")
    deviceId: str = Field(min_length=1, max_length=120)
    observationId: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=80)
    measuredAt: datetime
    values: dict[str, Any]
    units: dict[str, str]
    quality: str = "VALID"
    complements: dict[str, Any] = Field(default_factory=dict)

    @field_validator("measuredAt")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("measuredAt deve conter fuso horário.")
        return value

    @field_validator("quality")
    @classmethod
    def quality_ok(cls, value: str) -> str:
        if value != "VALID":
            raise ValueError("Somente quality=VALID pode ser ingerida.")
        return value

    @field_validator("values")
    @classmethod
    def valid_values(cls, value: dict[str, Any]) -> dict[str, Any]:
        unknown = set(value) - VARIAVEIS_ENTRADA
        missing = VARIAVEIS_ENTRADA - set(value)
        if unknown:
            raise ValueError("Variáveis de entrada não reconhecidas: " + ", ".join(sorted(unknown)))
        if missing:
            raise ValueError("Leitura incompleta; faltam: " + ", ".join(sorted(missing)))
        for name, number in value.items():
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(float(number)):
                raise ValueError(f"{name} precisa ser um número finito; valores ausentes e null não são substituídos.")
        limits = {
            "temperaturaAr": (-40, 85),
            "umidadeSolo": (-40, 80),
            "umidadeAr": (0, 100),
            "luminosidade": (0, 4095),
        }
        for name, (minimum, maximum) in limits.items():
            if not minimum <= float(value[name]) <= maximum:
                raise ValueError(f"{name} fora da faixa aceita: {minimum} a {maximum}.")
        return value

    @field_validator("units")
    @classmethod
    def valid_units(cls, value: dict[str, str]) -> dict[str, str]:
        missing = set(UNIDADES_ENTRADA) - set(value)
        unknown = set(value) - set(UNIDADES_ENTRADA)
        if missing:
            raise ValueError("Informe as unidades de entrada: " + ", ".join(sorted(missing)))
        if unknown:
            raise ValueError("Unidades de variáveis desconhecidas: " + ", ".join(sorted(unknown)))
        for name, expected in UNIDADES_ENTRADA.items():
            if value[name] != expected:
                raise ValueError(f"Unidade inválida para {name}; esperado {expected}.")
        return value

    @field_validator("complements")
    @classmethod
    def complements_vazios(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value:
            raise ValueError("O contrato atual não aceita complements; envie os quatro indicadores em values.")
        return value
