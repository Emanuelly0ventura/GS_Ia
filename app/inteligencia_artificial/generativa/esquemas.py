import json
import math
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.inteligencia_artificial.aprendizado_maquina.caracteristicas import (
    UNIDADES_MODELO,
    VARIAVEIS_MODELO,
)
from app.inteligencia_artificial.aprendizado_maquina.esquemas import ResultadoAnomalia


class ExplicacaoGeminiRejeitada(ValueError):
    """Texto gerado que tenta emitir uma decisão ou incluir dado numérico não confiável."""


class EntradaExplicacaoAnomalia(BaseModel):
    """Dados determinísticos de entrada; score e classificação nunca são gerados pelo Gemini."""

    model_config = ConfigDict(extra="forbid")

    resultado: ResultadoAnomalia
    indicadores: dict[str, float]
    unidades: dict[str, str]
    dados_complementares: dict[str, object] = Field(default_factory=dict, max_length=40)

    @field_validator("indicadores", mode="before")
    @classmethod
    def validar_indicadores(cls, valor: object) -> dict[str, float]:
        if not isinstance(valor, dict) or set(valor) != set(VARIAVEIS_MODELO):
            raise ValueError("A explicação exige exatamente os quatro indicadores canônicos.")
        resultado: dict[str, float] = {}
        for nome in VARIAVEIS_MODELO:
            numero = valor[nome]
            if isinstance(numero, bool) or not isinstance(numero, (int, float)):
                raise ValueError(f"O indicador {nome} precisa ser numérico.")
            if not math.isfinite(float(numero)):
                raise ValueError(f"O indicador {nome} precisa ser finito.")
            resultado[nome] = float(numero)
        return resultado

    @field_validator("unidades", mode="before")
    @classmethod
    def validar_unidades(cls, valor: object) -> dict[str, str]:
        if not isinstance(valor, dict) or set(valor) != set(VARIAVEIS_MODELO):
            raise ValueError("A explicação exige unidades para os quatro indicadores canônicos.")
        normalizadas = {nome: str(valor[nome]).strip() for nome in VARIAVEIS_MODELO}
        if normalizadas != UNIDADES_MODELO:
            raise ValueError("As unidades devem corresponder ao contrato oficial das features.")
        return normalizadas

    @field_validator("dados_complementares")
    @classmethod
    def validar_dados_complementares(cls, valor: dict[str, object]) -> dict[str, object]:
        try:
            serializado = json.dumps(valor, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):
            raise ValueError("Dados complementares precisam ser JSON finito.") from None
        if len(serializado.encode("utf-8")) > 12000:
            raise ValueError("Dados complementares excedem o limite permitido.")
        return valor

    @model_validator(mode="after")
    def validar_resultado_do_detector(self) -> "EntradaExplicacaoAnomalia":
        if not math.isfinite(self.resultado.pontuacao_anomalia):
            raise ValueError("O score fornecido pelo detector precisa ser finito.")
        if self.resultado.variaveis_utilizadas != list(VARIAVEIS_MODELO):
            raise ValueError("O resultado deve identificar as quatro features na ordem canônica.")
        if set(self.resultado.variaveis_utilizadas) != set(self.indicadores):
            raise ValueError("Indicadores e variáveis do resultado precisam coincidir.")
        if self.resultado.classificada_como_anomalia != (
            self.resultado.classificacao == "ANOMALIA_ESTATISTICA"
        ):
            raise ValueError("Classificação e flag do resultado determinístico estão inconsistentes.")
        return self


class SaidaExplicacaoAnomalia(BaseModel):
    """A decisão e os valores são determinísticos; o Gemini só preenche explicacao."""

    model_config = ConfigDict(extra="forbid")

    resultado: ResultadoAnomalia
    indicadores: dict[str, float]
    unidades: dict[str, str]
    dados_complementares: dict[str, object]
    explicacao: str = Field(min_length=1, max_length=4000)


class EntradaExplicacaoCompatibilidade(BaseModel):
    """Resultado e critérios vindos do catálogo/regras, nunca decididos pelo Gemini."""

    model_config = ConfigDict(extra="forbid")

    tipo_semente: str = Field(min_length=1, max_length=120)
    tipo_solo: str = Field(min_length=1, max_length=120)
    resultado_regra: str = Field(min_length=1, max_length=80)
    criterios_aplicados: list[str] = Field(min_length=1, max_length=30)

    @field_validator("tipo_semente", "tipo_solo", "resultado_regra")
    @classmethod
    def normalizar_texto(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O campo não pode ficar vazio.")
        return valor

    @field_validator("criterios_aplicados")
    @classmethod
    def validar_criterios(cls, criterios: list[str]) -> list[str]:
        normalizados = [criterio.strip() for criterio in criterios]
        if any(not criterio for criterio in normalizados):
            raise ValueError("Cada critério aplicado deve conter texto.")
        try:
            tamanho = len(json.dumps(normalizados, ensure_ascii=False, allow_nan=False).encode("utf-8"))
        except (TypeError, ValueError):
            raise ValueError("Os critérios precisam ser textos JSON válidos.") from None
        if tamanho > 12000:
            raise ValueError("Os critérios excedem o limite permitido.")
        return normalizados


class SaidaExplicacaoCompatibilidade(BaseModel):
    """Resultado e critérios determinísticos preservados fora do texto do Gemini."""

    model_config = ConfigDict(extra="forbid")

    tipo_semente: str
    tipo_solo: str
    resultado_regra: str
    criterios_aplicados: list[str]
    explicacao: str = Field(min_length=1, max_length=4000)


class TextoExplicativo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explicacao: str = Field(min_length=1, max_length=4000)


def validar_texto_neutro(texto: str, dominio: Literal["anomalia", "compatibilidade"]) -> None:
    """Rejeita decisão, classificação e números em texto generativo suplementar."""
    normalizado = unicodedata.normalize("NFKD", texto).casefold()
    normalizado = "".join(c for c in normalizado if not unicodedata.combining(c))
    if re.search(r"\d", texto):
        raise ExplicacaoGeminiRejeitada(
            "A explicação gerada foi rejeitada por conter valores numéricos; use os campos determinísticos."
        )

    padroes_decisao = {
        "anomalia": (
            r"\bnormal(?:es)?\b", r"\banomal\w*\b", r"\batipic\w*\b",
            r"\bclassificad\w*\b", r"\bclassificacao\b", r"\bpontuacao\b",
            r"\bscore\b", r"\bprobabilidade\b", r"\brisco\b", r"\bdiagnostico\b",
        ),
        "compatibilidade": (
            r"\bcompativ\w*\b", r"\bincompativ\w*\b", r"\binsuficient\w*\b",
            r"\bdecis\w*\b", r"\bresultado\b", r"\brecomend\w*\b",
            r"\badequad\w*\b", r"\bindicad\w*\b", r"\baprovad\w*\b",
            r"\binapto\b", r"\binapta\b", r"\bpode ser plantad\w*\b",
        ),
    }[dominio]
    if any(re.search(padrao, normalizado) for padrao in padroes_decisao):
        raise ExplicacaoGeminiRejeitada(
            "A explicação gerada foi rejeitada por tentar expressar uma decisão determinística."
        )
