"""Recuperação e geração de recomendações com um gerador substituível."""
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import ValidationError

from app.inteligencia_artificial.generativa.cliente_gemini import ErroGemini, GeminiRespostaInvalida
from app.inteligencia_artificial.generativa.fabrica import criar_provedor_gemini

from app.inteligencia_artificial.recomendacoes.esquemas import (
    CatalogoRecomendacoes,
    Condicao,
    CondicaoSensor,
    ContextoRecuperacao,
    Esquema,
    EstadoCuradoria,
    Identificador,
    Prioridade,
    Texto,
)
from app.inteligencia_artificial.recomendacoes.recuperacao import (
    Exclusao,
    LeituraDemonstrativa,
    RecomendacaoRecuperada,
    recuperar,
)


class IndicadorPermitido(Esquema):
    indicador: Texto
    valor: bool


class ReferenciaPermitida(Esquema):
    titulo: Texto
    instituicao: Texto
    localizador: Texto
    estado_curadoria: EstadoCuradoria


class ItemContextoGeracao(Esquema):
    id_recomendacao: Identificador
    tema: Texto
    culturas_aplicaveis: tuple[Texto, ...]
    condicoes: tuple[Condicao | CondicaoSensor, ...]
    orientacao: Texto
    justificativa: Texto
    prioridade: Prioridade
    estado_curadoria: EstadoCuradoria
    estado_apresentacao: Literal["PRELIMINAR", "REVISADA"]
    indicadores: tuple[IndicadorPermitido | LeituraDemonstrativa, ...]
    referencias: tuple[ReferenciaPermitida, ...]
    ressalvas: tuple[Texto, ...]


class ContextoGeracao(Esquema):
    recomendacoes: tuple[ItemContextoGeracao, ...]


class GeradorRecomendacoes(Protocol):
    """Recebe somente a projeção permitida e devolve a resposta em JSON."""

    async def gerar(self, contexto: ContextoGeracao) -> str: ...


class TextoGerado(Esquema):
    id_recomendacao: Identificador
    texto: str
    indices_referencias: tuple[int, ...]


class RespostaGerador(Esquema):
    recomendacoes: tuple[TextoGerado, ...]


@dataclass(frozen=True)
class ResultadoGeracao:
    estado: Literal[
        "SEM_EVIDENCIA_SUFICIENTE",
        "SEM_CONTEUDO_SUFICIENTE",
        "CONCLUIDA",
        "FALHA_GERADOR",
        "RESPOSTA_INVALIDA",
    ]
    mensagem: str
    recuperadas: tuple[ItemContextoGeracao, ...] = ()
    orientacoes: tuple[TextoGerado, ...] = ()
    exclusoes: tuple[Exclusao, ...] = ()
    codigo_erro: str | None = None


def _projetar(resultado: RecomendacaoRecuperada) -> ItemContextoGeracao:
    item = resultado.recomendacao
    return ItemContextoGeracao(
        id_recomendacao=item.id,
        tema=item.tema,
        culturas_aplicaveis=item.culturas_aplicaveis,
        condicoes=item.condicoes_aplicacao,
        orientacao=item.orientacao_tecnica,
        justificativa=item.justificativa,
        prioridade=item.criterio_prioridade.nivel,
        estado_curadoria=item.estado_curadoria,
        estado_apresentacao=resultado.estado_apresentacao,
        indicadores=tuple(
            dado if isinstance(dado, LeituraDemonstrativa) else
            IndicadorPermitido(indicador=dado.indicador, valor=dado.valor)
            for dado in resultado.evidencias_utilizadas
        ),
        referencias=tuple(
            ReferenciaPermitida(
                titulo=fonte.titulo,
                instituicao=fonte.instituicao,
                localizador=fonte.localizador,
                estado_curadoria=fonte.estado_curadoria,
            )
            for fonte in item.referencias
        ),
        ressalvas=item.restricoes_e_ressalvas + resultado.ressalvas_demonstracao,
    )


def _texto_permitido(texto: str, item: ItemContextoGeracao) -> bool:
    # A prova de conceito aceita duas composições fechadas do texto recuperado.
    prefixo = "Orientação preliminar. " if item.estado_apresentacao == "PRELIMINAR" else ""
    return texto in (
        f"{prefixo}{item.orientacao} {item.justificativa}",
        f"{prefixo}{item.justificativa} {item.orientacao}",
    )


def _validar_resposta(
    resposta: str, itens: tuple[ItemContextoGeracao, ...]
) -> tuple[TextoGerado, ...]:
    if not isinstance(resposta, str):
        raise ValueError("TIPO_INVALIDO")
    geradas = RespostaGerador.model_validate_json(resposta).recomendacoes
    por_id = {item.id_recomendacao: item for item in geradas}
    if len(por_id) != len(geradas) or por_id.keys() != {item.id_recomendacao for item in itens}:
        raise ValueError("IDS_INVALIDOS")

    ordenadas = tuple(por_id[item.id_recomendacao] for item in itens)
    for gerada, item in zip(ordenadas, itens, strict=True):
        indices = gerada.indices_referencias
        if len(set(indices)) != len(indices) or any(
            not 0 <= indice < len(item.referencias) for indice in indices
        ):
            raise ValueError("REFERENCIAS_INVALIDAS")
        if not _texto_permitido(gerada.texto, item):
            raise ValueError("TEXTO_FORA_DO_CATALOGO")
    return ordenadas


async def orquestrar(
    catalogo: CatalogoRecomendacoes,
    contexto: ContextoRecuperacao,
    gerador: GeradorRecomendacoes | None = None,
) -> ResultadoGeracao:
    recuperacao = recuperar(catalogo, contexto)
    if not recuperacao.recomendacoes:
        return ResultadoGeracao(
            estado="SEM_EVIDENCIA_SUFICIENTE",
            mensagem=(
                "Nenhuma recomendação foi recuperada. Não há evidência verificada suficiente "
                "nem dados Wokwi compatíveis para selecionar uma orientação aplicável. A orientação personalizada "
                "não foi gerada."
            ),
            exclusoes=recuperacao.exclusoes,
        )

    # O adaptador usa os schemas deste módulo. Componha-o somente após a seleção.
    from app.inteligencia_artificial.recomendacoes.gerador_gemini import (
        ConteudoInsuficienteParaComposicao,
        GeradorGeminiRecomendacoes,
    )

    itens = tuple(_projetar(item) for item in recuperacao.recomendacoes)
    try:
        if gerador is None:
            gerador = GeradorGeminiRecomendacoes(
                criar_provedor_gemini(), cultura_selecionada=contexto.cultura or "",
            )
        resposta = await gerador.gerar(ContextoGeracao(recomendacoes=itens))
    except ConteudoInsuficienteParaComposicao:
        return ResultadoGeracao(
            "SEM_CONTEUDO_SUFICIENTE", "O gerador não compôs uma orientação com o contexto recebido.",
            recuperadas=itens, exclusoes=recuperacao.exclusoes,
        )
    except GeminiRespostaInvalida as erro:
        return ResultadoGeracao(
            "RESPOSTA_INVALIDA", "O Gemini retornou uma resposta inválida.",
            recuperadas=itens, exclusoes=recuperacao.exclusoes, codigo_erro=erro.codigo,
        )
    except ErroGemini as erro:
        return ResultadoGeracao(
            "FALHA_GERADOR", "A geração com Gemini não pôde ser concluída.",
            recuperadas=itens, exclusoes=recuperacao.exclusoes, codigo_erro=erro.codigo,
        )
    except Exception:
        return ResultadoGeracao(
            "FALHA_GERADOR", "O gerador falhou.", recuperadas=itens,
            exclusoes=recuperacao.exclusoes, codigo_erro="GENERATION_INTERNAL_ERROR",
        )

    try:
        orientacoes = _validar_resposta(resposta, itens)
    except ValidationError:
        return ResultadoGeracao(
            "RESPOSTA_INVALIDA", "FORMATO_INVALIDO", recuperadas=itens,
            exclusoes=recuperacao.exclusoes,
        )
    except ValueError as erro:
        return ResultadoGeracao(
            "RESPOSTA_INVALIDA", str(erro), recuperadas=itens, exclusoes=recuperacao.exclusoes,
        )

    return ResultadoGeracao(
        "CONCLUIDA", "Texto composto a partir das recomendações recuperadas.",
        recuperadas=itens, orientacoes=orientacoes, exclusoes=recuperacao.exclusoes,
    )
