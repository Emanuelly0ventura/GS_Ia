"""Valida codificação e ranking local com o modelo pré-treinado configurado.

Os quatro textos abaixo são fixtures sintéticas para smoke test técnico. Não
representam fontes científicas, evidências agronômicas ou calibração de campo.
"""

import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.inteligencia_artificial.rag.embeddings import EmbeddingsIndisponiveis, SentenceTransformerLocal
from app.inteligencia_artificial.rag.esquemas import DocumentoConhecimento
from app.inteligencia_artificial.rag.indice_vetorial import IndiceIndisponivel, IndiceVetorialLocal
from app.inteligencia_artificial.rag.segmentacao import segmentar_documento
from app.nucleo.configuracoes import obter_configuracoes


def main() -> None:
    configuracoes = obter_configuracoes()
    revisao = configuracoes.rag_revisao_embeddings
    if not revisao or not revisao.strip():
        raise SystemExit("Configure a revisão imutável do modelo em RAG_REVISAO_EMBEDDINGS.")
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

    exemplos = [
        (
            "fixture-agua-milho",
            "Texto de teste sobre água no milho",
            "O déficit hídrico durante o florescimento e o enchimento de grãos pode reduzir a produtividade do milho. O monitoramento da umidade do solo e o manejo da irrigação ajudam a reduzir o estresse hídrico.",
        ),
        (
            "fixture-ferrugem-soja",
            "Texto de teste sobre ferrugem da soja",
            "A ferrugem asiática da soja é causada pelo fungo Phakopsora pachyrhizi. A identificação de lesões nas folhas e o monitoramento das condições de umidade são importantes para o manejo da doença.",
        ),
        (
            "fixture-abelhas",
            "Texto de teste sobre colmeias",
            "A manutenção de colmeias depende de disponibilidade de néctar, inspeção sanitária e condições adequadas para as abelhas.",
        ),
        (
            "fixture-energia",
            "Texto de teste sobre energia solar",
            "Painéis solares convertem radiação solar em energia elétrica por meio de células fotovoltaicas.",
        ),
    ]
    trechos = []
    for identificador, titulo, conteudo in exemplos:
        documento = DocumentoConhecimento(
            identificador=identificador,
            titulo=titulo,
            instituicao="Fixture sintética de validação local; não é fonte científica",
            referencia_origem="Texto sintético criado exclusivamente para teste de ranking",
            conteudo=conteudo,
        )
        trechos.extend(segmentar_documento(documento, tamanho_maximo=500, sobreposicao=0))

    vetores = codificador.codificar_documentos([trecho.texto for trecho in trechos])
    consultas = [
        ("Como reduzir o déficit hídrico e o estresse por falta de água no milho?", "fixture-agua-milho"),
        ("Como reconhecer e manejar a ferrugem asiática da soja?", "fixture-ferrugem-soja"),
        ("Qual é a escalação do próximo jogo da seleção brasileira de futebol?", None),
    ]
    resultados = []
    try:
        with tempfile.TemporaryDirectory(prefix=".tmp-f4-embeddings-reais-", dir=RAIZ) as temporario:
            indice = IndiceVetorialLocal(temporario)
            indice.reconstruir(
                trechos=trechos,
                vetores=vetores,
                identificador_modelo=codificador.identificador_modelo,
                revisao_modelo=codificador.revisao_modelo,
                fingerprint_modelo=codificador.fingerprint_modelo,
                configuracao_codificacao=codificador.configuracao_codificacao,
            )
            indice.carregar(codificador)
            for pergunta, esperado in consultas:
                recuperados = indice.buscar(
                    codificador.codificar_consulta(pergunta),
                    limite=configuracoes.rag_limite_trechos,
                    limiar_similaridade=configuracoes.rag_limiar_similaridade,
                )
                ids = [trecho.identificador_documento for trecho, _ in recuperados]
                ranking_completo = indice.buscar(
                    codificador.codificar_consulta(pergunta),
                    limite=configuracoes.rag_limite_trechos,
                    limiar_similaridade=-1.0,
                )
                resultados.append(
                    {
                        "consulta": pergunta,
                        "documento_esperado": esperado,
                        "ranking": [
                            {"id": trecho.identificador_documento, "score": round(float(score), 4)}
                            for trecho, score in ranking_completo
                        ],
                        "retidos_no_limiar": ids,
                    }
                )
                if esperado is None and ids:
                    raise AssertionError("A consulta irrelevante reteve documentos no limiar configurado.")
                if esperado is not None and (not ranking_completo or ranking_completo[0][0].identificador_documento != esperado):
                    raise AssertionError(f"O documento esperado não ficou em primeiro lugar: {pergunta}")
                if esperado is not None and esperado not in ids:
                    raise AssertionError(f"O documento esperado foi removido pelo limiar: {pergunta}")
    except (AssertionError, IndiceIndisponivel) as erro:
        raise SystemExit(str(erro)) from erro

    print(json.dumps({
        "modelo": codificador.identificador_modelo,
        "revisao": codificador.revisao_modelo,
        "dimensao": codificador.dimensao,
        "fingerprint_sha256": codificador.fingerprint_modelo,
        "configuracao_codificacao": codificador.configuracao_codificacao,
        "limiar": configuracoes.rag_limiar_similaridade,
        "natureza_dados": "fixtures sintéticas; não são documentos ou fontes científicas",
        "resultados": resultados,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
