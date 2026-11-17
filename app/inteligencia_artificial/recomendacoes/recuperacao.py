from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime

from app.inteligencia_artificial.recomendacoes.esquemas import (
    AVISO_UMIDADE_SOLO,
    ORIGENS_SENSOR,
    CapturaDemonstrativa,
    CatalogoRecomendacoes,
    CondicaoSensor,
    ContextoRecuperacao,
    Esquema,
    IndicadorSensor,
    OrigemSensor,
    Recomendacao,
    Texto,
)

CAMINHO_CATALOGO = Path(__file__).resolve().parents[3] / "base_conhecimento" / "recomendacoes.json"
ORDEM_PRIORIDADE = {"ALTA": 0, "MEDIA": 1, "BAIXA": 2}
MotivoExclusao = Literal[
    "CULTURA_AUSENTE",
    "CULTURA_INCOMPATIVEL",
    "INDICADOR_AUSENTE",
    "INDICADOR_SIMULADO",
    "PROCEDENCIA_DESCONHECIDA",
    "OBSERVACAO_HUMANA_NAO_VERIFICADA",
    "CONDICAO_NAO_ATENDIDA",
    "CURADORIA_PENDENTE",
    "CONTEXTO_WOKWI_AUSENTE",
]


class _EvidenciaVerificada(Esquema):
    """Registro interno de uma fonte confiável, fora do schema de entrada."""

    indicador: Texto
    valor: bool
    id_talhao: Texto
    observado_em: AwareDatetime
    referencia_origem: Texto
    origem: Literal["SENSOR", "INSPECAO_HUMANA"]


class LeituraDemonstrativa(Esquema):
    indicador: IndicadorSensor
    valor: float
    unidade: Texto
    origem: OrigemSensor
    source: Literal["WOKWI_HIVEMQ_NODE_RED"]
    simulado: Literal[True] = True
    metodo: Literal["CONVERSAO_LINEAR_DEMONSTRATIVA"] | None = None


@dataclass(frozen=True)
class RecomendacaoRecuperada:
    recomendacao: Recomendacao
    estado_apresentacao: Literal["PRELIMINAR", "REVISADA"]
    evidencias_utilizadas: tuple[_EvidenciaVerificada | LeituraDemonstrativa, ...]
    ressalvas_demonstracao: tuple[str, ...] = ()


@dataclass(frozen=True)
class Exclusao:
    id_recomendacao: str
    motivo: MotivoExclusao
    indicador: str | None = None


@dataclass(frozen=True)
class ResultadoRecuperacao:
    recomendacoes: tuple[RecomendacaoRecuperada, ...]
    indicadores_simulados: tuple[str, ...]
    exclusoes: tuple[Exclusao, ...]


def carregar_catalogo(caminho: Path = CAMINHO_CATALOGO) -> CatalogoRecomendacoes:
    return CatalogoRecomendacoes.model_validate_json(caminho.read_text(encoding="utf-8"))


def _obter_evidencias_verificadas(id_talhao: str) -> tuple[_EvidenciaVerificada, ...]:
    """Fronteira interna reservada a um produtor confiável. Ainda não há produtor."""
    return ()


def _motivo_sem_evidencia(
    nome: str, contexto: ContextoRecuperacao, observacoes_declaradas: set[str]
) -> MotivoExclusao:
    if nome in observacoes_declaradas:
        return "OBSERVACAO_HUMANA_NAO_VERIFICADA"
    indicador = contexto.indicadores.get(nome)
    if indicador is None:
        return "INDICADOR_AUSENTE"
    if indicador.origem == "SIMULADO":
        return "INDICADOR_SIMULADO"
    return "PROCEDENCIA_DESCONHECIDA"


def recuperar(
    catalogo: CatalogoRecomendacoes,
    contexto: ContextoRecuperacao,
) -> ResultadoRecuperacao:
    cultura = contexto.cultura.casefold() if contexto.cultura else None
    captura = contexto.captura_wokwi
    if captura is not None:
        # O contexto aceita dicionários; revalide seu conteúdo antes de usá-lo.
        captura = CapturaDemonstrativa.model_validate(captura.model_dump())
    leituras = {
        nome: LeituraDemonstrativa(
            indicador=nome,
            valor=valor,
            unidade=captura.units[nome],
            origem=ORIGENS_SENSOR[nome],
            source=captura.source,
            metodo=captura.metadados_umidade_solo.metodo if nome == "umidadeSolo" else None,
        )
        for nome, valor in captura.values.items()
    } if captura is not None else {}
    verificadas = {}
    if contexto.id_talhao is not None:
        for evidencia in _obter_evidencias_verificadas(contexto.id_talhao):
            if evidencia.id_talhao != contexto.id_talhao:
                continue
            if evidencia.indicador in verificadas:
                raise ValueError("A fonte interna retornou evidências ambíguas para o mesmo indicador.")
            verificadas[evidencia.indicador] = evidencia

    declaradas = {
        observacao.indicador
        for observacao in contexto.observacoes_humanas
        if observacao.id_talhao == contexto.id_talhao
    }
    simulados_legados = {
        nome for nome, indicador in contexto.indicadores.items()
        if indicador.origem == "SIMULADO"
    }
    simulados = tuple(sorted(simulados_legados.union(leituras)))
    selecionadas = []
    exclusoes = []
    for item in sorted(catalogo.recomendacoes, key=lambda entrada: entrada.id):
        if cultura is None:
            exclusoes.append(Exclusao(item.id, "CULTURA_AUSENTE"))
            continue
        if item.culturas_aplicaveis and cultura not in {
            nome.casefold() for nome in item.culturas_aplicaveis
        }:
            exclusoes.append(Exclusao(item.id, "CULTURA_INCOMPATIVEL"))
            continue

        if isinstance(item.condicoes_aplicacao[0], CondicaoSensor):
            if captura is None:
                exclusoes.append(Exclusao(item.id, "CONTEXTO_WOKWI_AUSENTE"))
                continue
            motivos_demo = [
                Exclusao(item.id, "INDICADOR_AUSENTE", nome)
                for nome in item.dados_exigidos if nome not in leituras
            ]
            motivos_demo.extend(
                Exclusao(item.id, "CONDICAO_NAO_ATENDIDA", condicao.indicador)
                for condicao in item.condicoes_aplicacao
                if condicao.indicador in leituras
                and not condicao.corresponde(leituras[condicao.indicador].valor)
            )
            if motivos_demo:
                exclusoes.extend(motivos_demo)
                continue
            ressalvas = ("Cenário acadêmico com dados do Wokwi, sem medição física em campo.",)
            if "umidadeSolo" in item.dados_exigidos:
                ressalvas += (AVISO_UMIDADE_SOLO,)
            selecionadas.append(RecomendacaoRecuperada(
                recomendacao=item,
                estado_apresentacao="PRELIMINAR",
                evidencias_utilizadas=tuple(leituras[nome] for nome in item.dados_exigidos),
                ressalvas_demonstracao=ressalvas,
            ))
            continue

        motivos = [
            Exclusao(item.id, _motivo_sem_evidencia(nome, contexto, declaradas), nome)
            for nome in item.dados_exigidos
            if nome not in verificadas
        ]
        motivos.extend(
            Exclusao(item.id, "CONDICAO_NAO_ATENDIDA", condicao.indicador)
            for condicao in item.condicoes_aplicacao
            if condicao.indicador in verificadas
            and verificadas[condicao.indicador].valor != condicao.valor_esperado
        )
        pendente = item.estado_curadoria == "PENDENTE"
        if item.acionavel and pendente:
            motivos.append(Exclusao(item.id, "CURADORIA_PENDENTE"))
        if motivos:
            exclusoes.extend(motivos)
            continue

        selecionadas.append(RecomendacaoRecuperada(
            recomendacao=item,
            estado_apresentacao="PRELIMINAR" if pendente else "REVISADA",
            evidencias_utilizadas=tuple(verificadas[nome] for nome in item.dados_exigidos),
        ))

    return ResultadoRecuperacao(
        recomendacoes=tuple(sorted(selecionadas, key=lambda resultado: (
            ORDEM_PRIORIDADE[resultado.recomendacao.criterio_prioridade.nivel],
            resultado.recomendacao.id,
        ))),
        indicadores_simulados=simulados,
        exclusoes=tuple(exclusoes),
    )
