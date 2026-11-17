from datetime import date
from math import isclose
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.nucleo.configuracoes import obter_configuracoes
from app.telemetria.conversoes import converter_temperatura_dht22_em_umidade_solo
from app.telemetria.esquemas import MetadadosUmidadeSolo, UNIDADES_CANONICAS

IndicadorSensor = Literal["temperaturaAr", "umidadeAr", "umidadeSolo", "luminosidade"]
OrigemSensor = Literal["BMP180_TEMPERATURA", "DHT22_UMIDADE", "DHT22_TEMPERATURA", "LDR"]
ORIGENS_SENSOR: dict[IndicadorSensor, OrigemSensor] = {
    "temperaturaAr": "BMP180_TEMPERATURA",
    "umidadeAr": "DHT22_UMIDADE",
    "umidadeSolo": "DHT22_TEMPERATURA",
    "luminosidade": "LDR",
}
FAIXAS_SENSOR = {
    "temperaturaAr": (-40, 85),
    "umidadeAr": (0, 100),
    "umidadeSolo": (0, 100),
    "luminosidade": (0, 4095),
}
AVISO_UMIDADE_SOLO = (
    "Como o simulador Wokwi não possui um sensor específico de umidade do solo, utilizamos a "
    "leitura de temperatura do sensor DHT22 para gerar um valor demonstrativo de umidade do solo, "
    "por meio de uma conversão linear. A leitura de umidade do ar do próprio DHT22 permanece "
    "independente e é utilizada normalmente na análise ambiental. Dessa forma, aproveitamos todos "
    "os dados gerados pelos sensores, sem adicionar leituras artificiais ou duplicar informações."
)

Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identificador = Annotated[str, StringConstraints(pattern=r"^REC[0-9]{3}$")]
Prioridade = Literal["BAIXA", "MEDIA", "ALTA"]
EstadoCuradoria = Literal["PENDENTE", "REVISADA"]


class Esquema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RegistroRevisao(Esquema):
    responsavel: Texto
    data: date
    fonte_consultada: Texto
    trecho_ou_evidencia: Texto


class ReferenciaTecnica(Esquema):
    titulo: Texto
    instituicao: Texto
    localizador: Texto
    estado_curadoria: EstadoCuradoria
    revisao: RegistroRevisao | None = None

    @model_validator(mode="after")
    def exigir_registro_de_revisao(self) -> "ReferenciaTecnica":
        if (self.estado_curadoria == "REVISADA") != (self.revisao is not None):
            raise ValueError("Apenas referências revisadas devem ter um registro de revisão.")
        return self


class Condicao(Esquema):
    indicador: Texto
    valor_esperado: bool


class CondicaoSensor(Esquema):
    indicador: IndicadorSensor
    operador: Literal["MENOR_OU_IGUAL", "MAIOR_OU_IGUAL"]
    limite_demonstrativo: float = Field(allow_inf_nan=False)

    @model_validator(mode="after")
    def validar_limite(self) -> "CondicaoSensor":
        minimo, maximo = FAIXAS_SENSOR[self.indicador]
        if not minimo <= self.limite_demonstrativo <= maximo:
            raise ValueError("O limiar está fora da faixa do indicador.")
        return self

    def corresponde(self, valor: float) -> bool:
        if self.operador == "MENOR_OU_IGUAL":
            return valor <= self.limite_demonstrativo
        return valor >= self.limite_demonstrativo


class CriterioPrioridade(Esquema):
    nivel: Prioridade
    criterio: Texto


class Recomendacao(Esquema):
    id: Identificador
    tema: Texto
    culturas_aplicaveis: tuple[Texto, ...]
    condicoes_aplicacao: tuple[Condicao | CondicaoSensor, ...] = Field(min_length=1)
    dados_exigidos: tuple[Texto, ...] = Field(min_length=1)
    orientacao_tecnica: Texto
    justificativa: Texto
    criterio_prioridade: CriterioPrioridade
    referencias: tuple[ReferenciaTecnica, ...] = Field(min_length=1)
    restricoes_e_ressalvas: tuple[Texto, ...] = Field(min_length=1)
    acionavel: bool
    estado_curadoria: EstadoCuradoria

    @model_validator(mode="after")
    def validar_indicadores(self) -> "Recomendacao":
        indicadores = [condicao.indicador for condicao in self.condicoes_aplicacao]
        if len(set(indicadores)) != len(indicadores):
            raise ValueError("Cada indicador pode ter apenas uma condição por recomendação.")
        if len(set(self.dados_exigidos)) != len(self.dados_exigidos):
            raise ValueError("Os dados exigidos devem ser únicos.")
        if not set(indicadores).issubset(self.dados_exigidos):
            raise ValueError("Todo indicador das condições deve constar nos dados exigidos.")
        if any(isinstance(condicao, CondicaoSensor) for condicao in self.condicoes_aplicacao):
            if not all(isinstance(condicao, CondicaoSensor) for condicao in self.condicoes_aplicacao):
                raise ValueError("Uma entrada de demonstração exige apenas condições de sensor.")
            if set(self.dados_exigidos) - ORIGENS_SENSOR.keys():
                raise ValueError("Uma entrada de demonstração exige apenas indicadores canônicos.")
            if not self.culturas_aplicaveis or set(self.culturas_aplicaveis) - {"milho", "feijão", "tomate"}:
                raise ValueError("A demonstração admite milho, feijão e tomate.")
            if self.acionavel:
                raise ValueError("As orientações de demonstração são preliminares e não acionáveis.")
        if self.estado_curadoria == "REVISADA" and any(
            fonte.estado_curadoria != "REVISADA" for fonte in self.referencias
        ):
            raise ValueError("Uma recomendação revisada exige que todas as referências sejam revisadas.")
        return self


class CatalogoRecomendacoes(Esquema):
    recomendacoes: tuple[Recomendacao, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validar_ids(self) -> "CatalogoRecomendacoes":
        if len({item.id for item in self.recomendacoes}) != len(self.recomendacoes):
            raise ValueError("O catálogo deve conter IDs únicos.")
        return self


class Indicador(Esquema):
    """Declaração de entrada. O rótulo legado REAL não comprova procedência."""

    valor: bool
    origem: Literal["REAL", "SIMULADO", "DESCONHECIDO"]


class ObservacaoHumana(Esquema):
    id_observacao: Texto
    indicador: Texto
    valor: bool
    id_talhao: Texto
    observado_em: AwareDatetime
    observador_declarado: Texto
    observacoes_complementares: Texto | None = None
    origem: Literal["INSPECAO_HUMANA"] = "INSPECAO_HUMANA"
    estado_verificacao: Literal["NAO_VERIFICADA"] = "NAO_VERIFICADA"
    autenticacao: Literal["NAO_DISPONIVEL"] = "NAO_DISPONIVEL"


class CapturaDemonstrativa(Esquema):
    """Valores já normalizados pela telemetria, em um contexto explicitamente Wokwi."""

    source: Literal["WOKWI_HIVEMQ_NODE_RED"]
    values: dict[IndicadorSensor, Annotated[float, Field(allow_inf_nan=False)]] = Field(min_length=1)
    units: dict[IndicadorSensor, str]
    metadados_umidade_solo: MetadadosUmidadeSolo | None = None

    @field_validator("values", mode="before")
    @classmethod
    def validar_numeros(cls, valores):
        if isinstance(valores, dict) and any(
            type(valor) not in (int, float) for valor in valores.values()
        ):
            raise ValueError("Os indicadores devem ser números finitos.")
        return valores

    @field_validator("metadados_umidade_solo", mode="before")
    @classmethod
    def validar_marcador_simulado(cls, metadados):
        if isinstance(metadados, dict) and metadados.get("simulado") is not True:
            raise ValueError("O marcador de simulação deve ser o booleano true.")
        return metadados

    @model_validator(mode="after")
    def validar_captura(self) -> "CapturaDemonstrativa":
        if self.units != {nome: UNIDADES_CANONICAS[nome] for nome in self.values}:
            raise ValueError("Os valores devem estar nas unidades canônicas da telemetria.")
        for nome, valor in self.values.items():
            minimo, maximo = FAIXAS_SENSOR[nome]
            if not minimo <= valor <= maximo:
                raise ValueError(f"{nome} está fora da faixa canônica.")
        solo = self.metadados_umidade_solo
        if ("umidadeSolo" in self.values) != (solo is not None):
            raise ValueError("Os metadados da conversão são obrigatórios exatamente quando há umidadeSolo.")
        if solo is not None and (
            solo.simulado is not True
            or solo.origem != "DHT22_TEMPERATURA"
            or solo.metodo != "CONVERSAO_LINEAR_DEMONSTRATIVA"
            or not -40 <= solo.temperatura_fonte_c <= 80
        ):
            raise ValueError("Metadados do DHT22 incompatíveis com a conversão demonstrativa.")
        if solo is not None:
            configuracoes = obter_configuracoes()
            esperado = converter_temperatura_dht22_em_umidade_solo(
                solo.temperatura_fonte_c,
                limite_inferior_c=configuracoes.telemetry_soil_moisture_temp_min_c,
                limite_superior_c=configuracoes.telemetry_soil_moisture_temp_max_c,
            )
            if not isclose(self.values["umidadeSolo"], esperado, rel_tol=0, abs_tol=1e-9):
                raise ValueError("O percentual de umidadeSolo não corresponde à temperatura de origem.")
        return self


class ContextoRecuperacao(Esquema):
    cultura: Texto | None = None
    captura_wokwi: CapturaDemonstrativa | None = None
    id_talhao: Texto | None = None
    indicadores: dict[Texto, Indicador] = Field(default_factory=dict)
    observacoes_humanas: tuple[ObservacaoHumana, ...] = ()
