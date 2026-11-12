from datetime import datetime, timezone
import math
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.inteligencia_artificial.aprendizado_maquina.caracteristicas import VARIAVEIS_MODELO

UNIDADES_OFICIAIS = {"temperaturaAr": "°C", "umidadeAr": "%", "luminosidade": "ADC"}
UNIDADES_COMPLEMENTARES = {"temperaturaBmp": "°C", "pressao": "hPa", "altitude": "m"}

class LeituraIoT(BaseModel):
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
    def require_timezone(cls, value):
        if value.tzinfo is None: raise ValueError("measuredAt deve conter fuso horário.")
        return value

    @field_validator("quality")
    @classmethod
    def quality_ok(cls, value):
        if value != "VALID": raise ValueError("Somente quality=VALID pode ser ingerida para análise.")
        return value

    @field_validator("values")
    @classmethod
    def finite_values(cls, value):
        unknown=set(value)-set(VARIAVEIS_MODELO)-set(UNIDADES_COMPLEMENTARES)
        if unknown: raise ValueError("Variáveis não reconhecidas: " + ", ".join(sorted(unknown)))
        for name, number in value.items():
            if isinstance(number, bool) or not isinstance(number,(int,float)) or not math.isfinite(float(number)):
                raise ValueError(f"{name} precisa ser um número finito; null e valores ausentes não são zero.")
        limites={"temperaturaAr":(-40,80), "umidadeAr":(0,100), "luminosidade":(0,4095)}
        for name,(minimum,maximum) in limites.items():
            if name in value and not minimum <= float(value[name]) <= maximum:
                raise ValueError(f"{name} fora da faixa aceita pelo sensor/configuração: {minimum} a {maximum}.")
        required=set(VARIAVEIS_MODELO)
        if not required.issubset(value): raise ValueError("Leitura incompleta; informe as três variáveis oficiais.")
        return value

    @field_validator("units")
    @classmethod
    def units_ok(cls, value):
        if not set(VARIAVEIS_MODELO).issubset(value): raise ValueError("Informe as unidades das três variáveis.")
        for name, unit in UNIDADES_OFICIAIS.items():
            if value.get(name) != unit: raise ValueError(f"Unidade inválida para {name}; esperado {unit}.")
        if set(value)-set(VARIAVEIS_MODELO)-set(UNIDADES_COMPLEMENTARES): raise ValueError("Unidade de variável desconhecida.")
        for name, unit in UNIDADES_COMPLEMENTARES.items():
            if name in value and value[name] != unit: raise ValueError(f"Unidade inválida para {name}; esperado {unit}.")
        return value

    @field_validator("complements")
    @classmethod
    def finite_complements(cls, value):
        if set(value)-set(UNIDADES_COMPLEMENTARES): raise ValueError("Complemento BMP180 não reconhecido.")
        for name, number in value.items():
            if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(float(number)):
                raise ValueError(f"Complemento {name} precisa ser um número finito.")
        return value
