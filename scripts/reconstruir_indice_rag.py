import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.inteligencia_artificial.rag.embeddings import EmbeddingsIndisponiveis, SentenceTransformerLocal
from app.inteligencia_artificial.rag.ingestao import ingerir_diretorio
from app.inteligencia_artificial.rag.indice_vetorial import IndiceIndisponivel, IndiceVetorialLocal
from app.inteligencia_artificial.rag.segmentacao import segmentar_documento
from app.nucleo.configuracoes import obter_configuracoes


def main() -> None:
    configuracoes = obter_configuracoes()
    if not configuracoes.rag_diretorio_documentos.is_dir():
        raise SystemExit(
            "Diretório local de documentos ausente. Crie-o e forneça documentos técnicos com metadados; "
            "nenhum conteúdo científico demonstrativo será criado."
        )
    try:
        documentos = ingerir_diretorio(
            configuracoes.rag_diretorio_documentos,
            limite_documento_bytes=configuracoes.rag_ingestao_limite_documento_bytes,
            limite_documentos=configuracoes.rag_ingestao_limite_documentos,
            limite_total_bytes=configuracoes.rag_ingestao_limite_total_bytes,
            limite_metadados_bytes=configuracoes.rag_ingestao_limite_metadados_bytes,
        )
    except (OSError, ValueError) as erro:
        raise SystemExit(f"Ingestão recusada: {erro}") from erro
    if not documentos:
        raise SystemExit(
            "Base documental vazia: forneça documentos técnicos autorizados com metadados. "
            "Nenhum conteúdo científico demonstrativo será criado."
        )
    revisao = configuracoes.rag_revisao_embeddings
    if not revisao or not revisao.strip():
        raise SystemExit("Configure RAG_REVISAO_EMBEDDINGS com a revisão local fixa do modelo.")
    try:
        codificador = SentenceTransformerLocal(
            configuracoes.rag_caminho_embeddings,
            revisao_modelo=revisao,
            identificador_modelo=configuracoes.rag_identificador_modelo_embeddings,
            prefixo_consulta=configuracoes.rag_prefixo_consulta_embeddings,
            prefixo_documento=configuracoes.rag_prefixo_documento_embeddings,
        )
    except EmbeddingsIndisponiveis as erro:
        raise SystemExit(str(erro)) from erro

    trechos = []
    for documento in documentos:
        restantes = configuracoes.rag_ingestao_limite_trechos - len(trechos)
        if restantes <= 0:
            raise SystemExit(
                f"A ingestão excede o limite de {configuracoes.rag_ingestao_limite_trechos} trechos."
            )
        try:
            documento_trechos = segmentar_documento(
                documento,
                tamanho_maximo=configuracoes.rag_tamanho_trecho,
                sobreposicao=configuracoes.rag_sobreposicao_trechos,
                limite_trechos=restantes,
            )
        except ValueError as erro:
            raise SystemExit(f"Segmentação recusada: {erro}") from erro
        trechos.extend(documento_trechos)
    if not trechos:
        raise SystemExit("Nenhum trecho válido foi gerado a partir dos documentos locais.")
    vetores = codificador.codificar_documentos([trecho.texto for trecho in trechos])
    try:
        indice = IndiceVetorialLocal(configuracoes.rag_diretorio_indice)
        indice.reconstruir(
            trechos=trechos,
            vetores=vetores,
            identificador_modelo=codificador.identificador_modelo,
            revisao_modelo=codificador.revisao_modelo,
            fingerprint_modelo=codificador.fingerprint_modelo,
            configuracao_codificacao=codificador.configuracao_codificacao,
        )
    except IndiceIndisponivel as erro:
        raise SystemExit(str(erro)) from erro
    print(json.dumps({
        "documentos_locais_ingestados": len(documentos),
        "trechos_indexados": len(trechos),
        "caminho_indice": str(configuracoes.rag_diretorio_indice),
        "modelo_embeddings_local": codificador.identificador_modelo,
        "revisao_embeddings": codificador.revisao_modelo,
        "fingerprint_embeddings": codificador.fingerprint_modelo,
        "fontes_cientificas_oficiais_verificadas": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
