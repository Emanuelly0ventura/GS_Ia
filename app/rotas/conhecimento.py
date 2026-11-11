import json
from functools import lru_cache
import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel
from starlette.requests import Request

from app.inteligencia_artificial.generativa.provedor_chat_completions import (
    ProvedorIndisponivel,
    ProvedorNaoConfigurado,
)
from app.inteligencia_artificial.rag.contexto import ContextoExcedeuOrcamento
from app.inteligencia_artificial.rag.embeddings import EmbeddingsIndisponiveis
from app.inteligencia_artificial.rag.fabrica import (
    consultar_estado_rag,
    criar_provedor_generativo,
    obter_servico_rag,
)
from app.inteligencia_artificial.rag.indice_vetorial import IndiceIndisponivel
from app.inteligencia_artificial.rag.respostas import FonteRecuperada, RespostaAnaliseAgronomica
from app.inteligencia_artificial.rag.servico import ServicoRAG
from app.inteligencia_artificial.aprendizado_maquina.esquemas import ResultadoAnomalia
from app.nucleo.configuracoes import obter_configuracoes
from app.nucleo.limitador_taxa import LimitadorTaxaMemoria

limitador_analise = LimitadorTaxaMemoria()


def proteger_rota_analise(request: Request, chave_api: str | None) -> None:
    configuracoes = obter_configuracoes()
    segredo_configurado = configuracoes.rag_analise_chave_api
    ambiente = configuracoes.ambiente.casefold().strip()
    ambientes_locais = {"development", "desenvolvimento", "test", "testing", "teste"}

    if segredo_configurado is None or not segredo_configurado.get_secret_value():
        if ambiente not in ambientes_locais or not configuracoes.rag_analise_permitir_sem_chave_local:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Análise generativa desabilitada: configure RAG_ANALISE_CHAVE_API; "
                    "a exceção local exige RAG_ANALISE_PERMITIR_SEM_CHAVE_LOCAL=true."
                ),
            )
    else:
        if not chave_api:
            raise HTTPException(status_code=401, detail="Credencial de análise ausente.")
        if not hmac.compare_digest(chave_api.encode("utf-8"), segredo_configurado.get_secret_value().encode("utf-8")):
            raise HTTPException(status_code=403, detail="Credencial de análise inválida.")

    cliente = request.client.host if request.client else "desconhecido"
    permitido, espera = limitador_analise.permitir(
        cliente,
        configuracoes.rag_analise_rate_limit_requisicoes,
        configuracoes.rag_analise_rate_limit_janela_segundos,
    )
    if not permitido:
        raise HTTPException(
            status_code=429,
            detail="Limite de requisições de análise excedido.",
            headers={"Retry-After": str(espera)},
        )


def excede_profundidade_json(corpo: bytes, limite: int) -> bool:
    """Conta arrays/objetos JSON sem considerar delimitadores dentro de strings."""
    profundidade = 0
    dentro_string = False
    escape = False
    for caractere in corpo:
        if dentro_string:
            if escape:
                escape = False
            elif caractere == ord("\\"):
                escape = True
            elif caractere == ord('"'):
                dentro_string = False
            continue
        if caractere == ord('"'):
            dentro_string = True
        elif caractere in (ord("{"), ord("[")):
            profundidade += 1
            if profundidade > limite:
                return True
        elif caractere in (ord("}"), ord("]")) and profundidade:
            profundidade -= 1
    return False


class RotaComLimiteProfundidadeJson(APIRoute):
    def get_route_handler(self):
        manipulador_original = super().get_route_handler()

        async def manipulador_com_limite(request: Request):
            if request.method == "POST":
                corpo = await request.body()
                limite = obter_configuracoes().api_json_profundidade_maxima
                if excede_profundidade_json(corpo, limite):
                    raise HTTPException(
                        status_code=422,
                        detail=f"A estrutura JSON excede a profundidade máxima de {limite}.",
                    )
            return await manipulador_original(request)

        return manipulador_com_limite


roteador = APIRouter(
    prefix="/api/v1",
    tags=["Conhecimento agronômico e RAG"],
    route_class=RotaComLimiteProfundidadeJson,
)


class ConsultaConhecimento(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")
    pergunta: str = Field(min_length=3, max_length=2000)

    @field_validator("pergunta")
    @classmethod
    def normalizar_pergunta(cls, valor: str) -> str:
        valor = valor.strip()
        if len(valor) < 3:
            raise ValueError("A pergunta precisa conter ao menos três caracteres.")
        return valor


class PedidoAnaliseAgronomica(ConsultaConhecimento):
    dados_agricolas: dict[str, Any] = Field(default_factory=dict, max_length=40)
    resultado_anomalia: ResultadoAnomalia | None = None

    @field_validator("dados_agricolas")
    @classmethod
    def limitar_contexto_json(cls, valor: dict[str, Any]) -> dict[str, Any]:
        try:
            serializado = json.dumps(valor, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as erro:
            raise ValueError("dadosAgricolas precisa ser JSON válido com números finitos.") from erro
        if len(serializado) > 20000:
            raise ValueError("dadosAgricolas excede o limite de 20.000 caracteres.")
        return valor


@lru_cache(maxsize=1)
def obter_servico_cacheado() -> ServicoRAG:
    return obter_servico_rag()


@roteador.get(
    "/conhecimento/status",
    summary="Consulta o estado local da base RAG",
    description="Informa dependências, fontes locais, modelo, índice e provedor. Presença de arquivo não valida conteúdo científico.",
)
def status_conhecimento() -> dict[str, object]:
    return consultar_estado_rag()


@roteador.post(
    "/conhecimento/buscar",
    response_model=list[FonteRecuperada],
    summary="Busca trechos documentais locais",
    description="Retorna metadados e posições. A similaridade é um filtro técnico e não prova relevância científica.",
)
def buscar_conhecimento(pedido: ConsultaConhecimento) -> list[FonteRecuperada]:
    try:
        servico = obter_servico_cacheado()
        encontrados = servico.buscar(pedido.pergunta)
    except EmbeddingsIndisponiveis as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro
    except IndiceIndisponivel as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro
    return [
        FonteRecuperada(trecho=trecho, similaridade_vetorial=score)
        for trecho, score in encontrados
    ]


@roteador.post(
    "/analises/agronomicas",
    response_model=RespostaAnaliseAgronomica,
    summary="Gera análise agronômica fundamentada em documentos recuperados",
    description=(
        "Recebe apenas o contexto enviado pela chamada, sem buscar dados de usuário ou sensores. "
        "O resultado opcional do Isolation Forest continua sendo estatístico, não diagnóstico."
    ),
)
async def analisar_agronomia(
    pedido: PedidoAnaliseAgronomica,
    request: Request,
    chave_api: str | None = Header(default=None, alias="X-API-Key"),
) -> RespostaAnaliseAgronomica:
    proteger_rota_analise(request, chave_api)
    try:
        servico = obter_servico_cacheado()
        provedor = criar_provedor_generativo()
        anomalia = (
            pedido.resultado_anomalia.model_dump(mode="json", by_alias=True)
            if pedido.resultado_anomalia else None
        )
        return await servico.analisar(
            pergunta=pedido.pergunta,
            dados_agricolas=pedido.dados_agricolas,
            provedor=provedor,
            resultado_anomalia=anomalia,
        )
    except EmbeddingsIndisponiveis as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro
    except IndiceIndisponivel as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro
    except ProvedorNaoConfigurado as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro
    except ContextoExcedeuOrcamento as erro:
        raise HTTPException(status_code=413, detail=str(erro)) from erro
    except ProvedorIndisponivel as erro:
        raise HTTPException(status_code=502, detail=str(erro)) from erro
    except ValueError as erro:
        raise HTTPException(status_code=502, detail=str(erro)) from erro
