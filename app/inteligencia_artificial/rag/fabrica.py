from functools import lru_cache
from importlib.util import find_spec
import json

from app.inteligencia_artificial.generativa.provedor_chat_completions import (
    ProvedorChatCompletions,
    ProvedorNaoConfigurado,
)
from app.inteligencia_artificial.rag.embeddings import EmbeddingsIndisponiveis, SentenceTransformerLocal
from app.inteligencia_artificial.rag.indice_vetorial import IndiceIndisponivel, IndiceVetorialLocal
from app.inteligencia_artificial.rag.servico import ServicoRAG
from app.nucleo.configuracoes import Configuracoes, obter_configuracoes


@lru_cache(maxsize=1)
def obter_servico_rag() -> ServicoRAG:
    configuracoes = obter_configuracoes()
    revisao = configuracoes.rag_revisao_embeddings
    if not revisao or not revisao.strip():
        raise EmbeddingsIndisponiveis("RAG_REVISAO_EMBEDDINGS precisa fixar a revisão local do modelo.")
    codificador = obter_codificador_embeddings(
        str(configuracoes.rag_caminho_embeddings.resolve()),
        revisao,
        configuracoes.rag_identificador_modelo_embeddings,
        configuracoes.rag_prefixo_consulta_embeddings,
        configuracoes.rag_prefixo_documento_embeddings,
    )
    indice = IndiceVetorialLocal(configuracoes.rag_diretorio_indice)
    indice.carregar(codificador)
    return ServicoRAG(
        codificador,
        indice,
        limiar_similaridade=configuracoes.rag_limiar_similaridade,
        limite_trechos=configuracoes.rag_limite_trechos,
        limite_contexto_bytes=configuracoes.rag_orcamento_contexto_bytes,
    )


@lru_cache(maxsize=1)
def obter_codificador_embeddings(
    caminho: str,
    revisao: str,
    identificador: str,
    prefixo_consulta: str,
    prefixo_documento: str,
) -> SentenceTransformerLocal:
    """Carrega uma vez os pesos locais; local_files_only impede downloads no status/consulta."""
    return SentenceTransformerLocal(
        caminho,
        revisao_modelo=revisao,
        identificador_modelo=identificador,
        prefixo_consulta=prefixo_consulta,
        prefixo_documento=prefixo_documento,
    )


def criar_provedor_generativo(
    configuracoes: Configuracoes | None = None,
) -> ProvedorChatCompletions:
    configuracoes = configuracoes or obter_configuracoes()
    if (configuracoes.provedor_ia or "").casefold() not in {"chat_completions", "openai_compatible"}:
        raise ProvedorNaoConfigurado("PROVEDOR_IA deve selecionar chat_completions ou openai_compatible.")
    chave = configuracoes.provedor_ia_api_key
    return ProvedorChatCompletions(
        url=configuracoes.provedor_ia_url,
        modelo=configuracoes.provedor_ia_modelo,
        chave_api=chave.get_secret_value() if chave else None,
        timeout_segundos=configuracoes.provedor_ia_timeout_segundos,
        limite_tokens_resposta=configuracoes.provedor_ia_limite_tokens_resposta,
        campo_limite_tokens=configuracoes.provedor_ia_campo_limite_tokens,
        limite_resposta_bytes=configuracoes.provedor_ia_limite_resposta_bytes,
        limite_contexto_bytes=configuracoes.rag_orcamento_contexto_bytes,
    )


def consultar_estado_rag(configuracoes: Configuracoes | None = None) -> dict[str, object]:
    configuracoes = configuracoes or obter_configuracoes()
    caminhos_indice = [
        configuracoes.rag_diretorio_indice / nome
        for nome in ("manifesto.json", "trechos.faiss", "trechos.jsonl")
    ]
    if configuracoes.rag_diretorio_documentos.is_dir():
        documentos = sorted(
            caminho for extensao in ("*.md", "*.txt")
            for caminho in configuracoes.rag_diretorio_documentos.rglob(extensao)
            if caminho.is_file()
        )
    else:
        documentos = []
    modelo_presente = configuracoes.rag_caminho_embeddings.is_dir()
    manifesto_path, indice_path, trechos_path = caminhos_indice
    manifesto_estado = "AUSENTE" if not manifesto_path.is_file() else "INVALIDO"
    indice_estado = "AUSENTE_OU_INCOMPLETO"
    modelo_estado = "AUSENTE" if not modelo_presente else "NAO_VALIDADO"
    compatibilidade_modelo_indice = "NAO_VALIDADA"
    manifesto: dict[str, object] | None = None
    if manifesto_path.is_file():
        try:
            if manifesto_path.stat().st_size > 1_000_000:
                raise ValueError("Manifesto acima do limite de tamanho.")
            manifesto_lido = json.loads(manifesto_path.read_text(encoding="utf-8"))
            validador_indice = object.__new__(IndiceVetorialLocal)
            validador_indice._validar_manifesto(manifesto_lido)
            manifesto = manifesto_lido
            manifesto_estado = "ESTRUTURALMENTE_VALIDO"
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, IndiceIndisponivel):
            manifesto_estado = "INVALIDO"

    artefatos_presentes = all(path.is_file() for path in caminhos_indice)
    if not artefatos_presentes:
        indice_estado = "AUSENTE_OU_INCOMPLETO"
    elif find_spec("faiss") is None:
        indice_estado = "DEPENDENCIA_FAISS_AUSENTE"
    elif manifesto_estado != "ESTRUTURALMENTE_VALIDO":
        indice_estado = "MANIFESTO_INVALIDO"
    if not modelo_presente:
        modelo_estado = "AUSENTE"
        if artefatos_presentes and manifesto_estado == "ESTRUTURALMENTE_VALIDO":
            indice_estado = "NAO_VALIDADO_MODELO_AUSENTE"
    elif not artefatos_presentes or manifesto_estado != "ESTRUTURALMENTE_VALIDO":
        # Evita carregar os pesos (centenas de MB) quando ainda não há índice verificável.
        modelo_estado = "PRESENTE_NAO_VALIDADO"
    elif find_spec("faiss") is None:
        modelo_estado = "PRESENTE_NAO_VALIDADO"
    elif find_spec("sentence_transformers") is None:
        modelo_estado = "DEPENDENCIA_AUSENTE"
        indice_estado = "NAO_VALIDADO_MODELO_INDISPONIVEL"
    elif not configuracoes.rag_revisao_embeddings or not configuracoes.rag_revisao_embeddings.strip():
        modelo_estado = "REVISAO_NAO_CONFIGURADA"
        indice_estado = "NAO_VALIDADO_REVISAO_AUSENTE"
    else:
        try:
            codificador = obter_codificador_embeddings(
                str(configuracoes.rag_caminho_embeddings.resolve()),
                configuracoes.rag_revisao_embeddings,
                configuracoes.rag_identificador_modelo_embeddings,
                configuracoes.rag_prefixo_consulta_embeddings,
                configuracoes.rag_prefixo_documento_embeddings,
            )
            modelo_estado = "DISPONIVEL"
            if artefatos_presentes and manifesto_estado == "ESTRUTURALMENTE_VALIDO":
                campos_compativeis = (
                    manifesto["identificador_modelo"] == codificador.identificador_modelo
                    and manifesto["revisao_modelo"] == codificador.revisao_modelo
                    and manifesto["fingerprint_modelo"] == codificador.fingerprint_modelo
                    and manifesto["dimensao_embeddings"] == codificador.dimensao
                    and manifesto["configuracao_codificacao"] == codificador.configuracao_codificacao
                )
                if not campos_compativeis:
                    modelo_estado = "INCOMPATIVEL_COM_INDICE"
                    compatibilidade_modelo_indice = "INCOMPATIVEL"
                    indice_estado = "INCOMPATIVEL_COM_MODELO"
                else:
                    compatibilidade_modelo_indice = "COMPATIVEL_COM_MANIFESTO"
                    try:
                        indice = IndiceVetorialLocal(configuracoes.rag_diretorio_indice)
                        indice.carregar(codificador)
                        modelo_estado = "COMPATIVEL_COM_INDICE"
                        compatibilidade_modelo_indice = "COMPATIVEL"
                        indice_estado = "DISPONIVEL_COMPATIVEL"
                    except IndiceIndisponivel:
                        indice_estado = "INCOMPATIVEL_OU_CORROMPIDO"
        except (EmbeddingsIndisponiveis, OSError, RuntimeError, ValueError):
            modelo_estado = "INDISPONIVEL_OU_INVALIDO"
            if artefatos_presentes:
                indice_estado = "NAO_VALIDADO_MODELO_INDISPONIVEL"

    provedor_configurado = bool(
        (configuracoes.provedor_ia or "").casefold() in {"chat_completions", "openai_compatible"}
        and (configuracoes.provedor_ia_modelo or "").strip()
        and (configuracoes.provedor_ia_url or "").strip()
        and configuracoes.provedor_ia_api_key
        and configuracoes.provedor_ia_api_key.get_secret_value().strip()
    )
    estados = {
        "documentos_locais": "PRESENTES" if documentos else "AUSENTES",
        "observacao_documentos": "Presença local não atesta autenticidade ou validade científica.",
        "modelo_embeddings": modelo_estado,
        "revisao_embeddings": "CONFIGURADA" if configuracoes.rag_revisao_embeddings else "AUSENTE",
        "dependencia_sentence_transformers": "DISPONIVEL" if find_spec("sentence_transformers") else "AUSENTE",
        "dependencia_faiss": "DISPONIVEL" if find_spec("faiss") else "AUSENTE",
        "manifesto": manifesto_estado,
        "indice_faiss": indice_estado,
        "provedor_generativo": "CONFIGURADO_NAO_TESTADO" if provedor_configurado else "NAO_CONFIGURADO",
        "teste_provedor_real": "NAO_EXECUTADO",
        "quantidade_arquivos_documentais": len(documentos),
        "fontes_oficiais_verificadas": "NAO_VERIFICADAS",
        "compatibilidade_modelo_indice": compatibilidade_modelo_indice,
    }
    componentes_tecnicos_prontos = all(estados[nome] == esperado for nome, esperado in (
        ("documentos_locais", "PRESENTES"),
        ("modelo_embeddings", "COMPATIVEL_COM_INDICE"),
        ("revisao_embeddings", "CONFIGURADA"),
        ("dependencia_sentence_transformers", "DISPONIVEL"),
        ("dependencia_faiss", "DISPONIVEL"),
        ("manifesto", "ESTRUTURALMENTE_VALIDO"),
        ("indice_faiss", "DISPONIVEL_COMPATIVEL"),
        ("provedor_generativo", "TESTADO"),
    ))
    # A checagem de autenticidade editorial exige processo humano; presença de arquivo não basta.
    pronto = componentes_tecnicos_prontos and estados["fontes_oficiais_verificadas"] == "VERIFICADAS"
    return {
        "estado": "PRONTO" if pronto else "CONFIGURACAO_INCOMPLETA",
        "documentos_cientificos_oficiais_verificados": False,
        "componentes": estados,
        "limite_similaridade": "A pontuação do índice serve à recuperação e não comprova relevância científica.",
    }
