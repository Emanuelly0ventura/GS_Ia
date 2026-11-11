import numpy as np
import pytest
from pathlib import Path

from app.inteligencia_artificial.rag.embeddings import EmbeddingsIndisponiveis, SentenceTransformerLocal
from app.inteligencia_artificial.rag.esquemas import DocumentoConhecimento
from app.inteligencia_artificial.rag.indice_vetorial import IndiceIndisponivel, IndiceVetorialLocal
from app.inteligencia_artificial.rag.segmentacao import segmentar_documento


class CodificadorFalsoTeste:
    identificador_modelo = "modelo-falso-explicito-de-teste"
    revisao_modelo = "sha-teste-001"
    fingerprint_modelo = "a" * 64
    dimensao = 2
    configuracao_codificacao = {"prefixo_consulta": "", "prefixo_documento": ""}


def trechos_teste():
    documento = DocumentoConhecimento(
        identificador="fixture-rag-001",
        titulo="Fixture de teste, não é fonte científica",
        instituicao="Fixture de teste",
        referencia_origem="TESTE://fixture",
        conteudo=("Solo e umidade são termos agronômicos sintéticos de teste. " * 2)
        + "\n\n"
        + ("Receita culinária é texto irrelevante de teste. " * 2),
    )
    return segmentar_documento(documento, tamanho_maximo=120, sobreposicao=10)


def criar_indice(caminho, trechos=None):
    indice = IndiceVetorialLocal(caminho)
    vetor = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    indice.reconstruir(trechos or trechos_teste(), vetor, CodificadorFalsoTeste.identificador_modelo,
                      CodificadorFalsoTeste.revisao_modelo, CodificadorFalsoTeste.fingerprint_modelo)
    return indice


def test_faiss_indexa_persiste_e_recupera_trecho_com_fonte(tmp_path):
    indice = criar_indice(tmp_path)
    carregado = IndiceVetorialLocal(tmp_path)
    carregado.carregar(CodificadorFalsoTeste())
    [resultado] = carregado.buscar(np.array([1.0, 0.0]), limite=5, limiar_similaridade=0.8)
    trecho, score = resultado
    assert trecho.identificador_documento == "fixture-rag-001"
    assert trecho.instituicao == "Fixture de teste"
    assert trecho.referencia_origem == "TESTE://fixture"
    assert trecho.inicio_caractere >= 0 and trecho.fim_caractere > trecho.inicio_caractere
    assert score == pytest.approx(1.0)
    assert indice.quantidade_trechos == 2


def test_consulta_sem_correspondencia_retorna_lista_vazia(tmp_path):
    indice = criar_indice(tmp_path)
    assert indice.buscar(np.array([-1.0, 0.0]), limiar_similaridade=0.6) == []


def test_indice_ausente_e_reportado_claramente(tmp_path):
    indice = IndiceVetorialLocal(tmp_path)
    with pytest.raises(IndiceIndisponivel, match="ausente"):
        indice.carregar(CodificadorFalsoTeste())


def test_indice_corrompido_e_rejeitado_por_hash(tmp_path):
    criar_indice(tmp_path)
    (tmp_path / IndiceVetorialLocal.NOME_TRECHOS).write_text("conteúdo alterado", encoding="utf-8")
    with pytest.raises(IndiceIndisponivel, match="diverge do manifesto"):
        IndiceVetorialLocal(tmp_path).carregar(CodificadorFalsoTeste())


def test_indice_recusa_modelo_ou_revisao_incompativel(tmp_path):
    criar_indice(tmp_path)
    codificador = CodificadorFalsoTeste()
    codificador.identificador_modelo = "outro-modelo"
    with pytest.raises(IndiceIndisponivel, match="outro modelo"):
        IndiceVetorialLocal(tmp_path).carregar(codificador)
    codificador.identificador_modelo = "modelo-falso-explicito-de-teste"
    codificador.revisao_modelo = "outra-revisao"
    with pytest.raises(IndiceIndisponivel, match="revisão"):
        IndiceVetorialLocal(tmp_path).carregar(codificador)


def test_indice_recusa_pesos_alterados_com_mesmo_id_e_revisao(tmp_path):
    criar_indice(tmp_path)
    codificador = CodificadorFalsoTeste()
    codificador.fingerprint_modelo = "b" * 64
    with pytest.raises(IndiceIndisponivel, match="pesos do modelo"):
        IndiceVetorialLocal(tmp_path).carregar(codificador)


def test_indice_recusa_prefixos_de_codificacao_incompativeis(tmp_path):
    criar_indice(tmp_path)
    codificador = CodificadorFalsoTeste()
    codificador.configuracao_codificacao = {
        "prefixo_consulta": "query: ",
        "prefixo_documento": "passage: ",
    }
    with pytest.raises(IndiceIndisponivel, match="configuração de codificação"):
        IndiceVetorialLocal(tmp_path).carregar(codificador)


def test_modelo_de_embeddings_local_ausente_nao_faz_download(tmp_path):
    with pytest.raises(EmbeddingsIndisponiveis, match="está ausente"):
        SentenceTransformerLocal(tmp_path / "modelo-ausente", revisao_modelo="r1")


def test_adaptador_de_embeddings_valida_formato_e_normaliza_vetores(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace

    (tmp_path / "pesos.fixture").write_bytes(b"synthetic test weights")

    class SentenceTransformerFalsoDeTeste:
        def __init__(self, caminho, **opcoes):
            assert Path(caminho) == tmp_path
            assert opcoes["local_files_only"] is True
            assert opcoes["trust_remote_code"] is False

        def get_embedding_dimension(self):
            return 2

        def encode(self, textos, **_):
            chamadas.append(textos)
            return np.array([[3, 4] for _ in textos], dtype=np.float32)

    chamadas = []

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(
        SentenceTransformer=SentenceTransformerFalsoDeTeste,
    ))
    codificador = SentenceTransformerLocal(
        tmp_path,
        revisao_modelo="fixture-r1",
        prefixo_consulta="query: ",
        prefixo_documento="passage: ",
    )
    vetores = codificador.codificar_documentos(["texto de teste"])
    assert vetores.shape == (1, 2)
    assert np.linalg.norm(vetores[0]) == pytest.approx(1.0)
    assert codificador.codificar_consulta("consulta de teste").shape == (2,)
    assert chamadas == [["passage: texto de teste"], ["query: consulta de teste"]]
