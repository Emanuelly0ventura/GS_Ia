import hashlib
import json

import numpy as np

from app.inteligencia_artificial.rag import fabrica
from app.inteligencia_artificial.rag.esquemas import DocumentoConhecimento
from app.inteligencia_artificial.rag.indice_vetorial import IndiceVetorialLocal
from app.inteligencia_artificial.rag.segmentacao import segmentar_documento
from app.nucleo.configuracoes import Configuracoes


class CodificadorStatusTeste:
    identificador_modelo = "modelo-status-teste"
    revisao_modelo = "revisao-a"
    fingerprint_modelo = hashlib.sha256(b"modelo-status-teste").hexdigest()
    dimensao = 2
    configuracao_codificacao = {"prefixo_consulta": "query: ", "prefixo_documento": "passage: "}


def _config(tmp_path):
    documentos = tmp_path / "documentos"
    documentos.mkdir()
    indice = tmp_path / "indice"
    modelo = tmp_path / "modelo"
    modelo.mkdir()
    return Configuracoes(
        rag_diretorio_documentos=documentos,
        rag_diretorio_indice=indice,
        rag_caminho_embeddings=modelo,
        rag_identificador_modelo_embeddings=CodificadorStatusTeste.identificador_modelo,
        rag_revisao_embeddings=CodificadorStatusTeste.revisao_modelo,
        rag_prefixo_consulta_embeddings="query: ",
        rag_prefixo_documento_embeddings="passage: ",
    )


def _reconstruir_indice(diretorio, revisao="revisao-a", fingerprint=None):
    documento = DocumentoConhecimento(
        identificador="teste-status",
        titulo="Documento sintético para teste de estado",
        instituicao="Fixture de teste",
        referencia_origem="TESTE://status",
        conteudo="Conteúdo exclusivamente sintético de teste.",
    )
    trechos = segmentar_documento(documento)
    indice = IndiceVetorialLocal(diretorio)
    indice.reconstruir(
        trechos,
        np.asarray([[1.0, 0.0]], dtype=np.float32),
        CodificadorStatusTeste.identificador_modelo,
        revisao,
        fingerprint or CodificadorStatusTeste.fingerprint_modelo,
        CodificadorStatusTeste.configuracao_codificacao,
    )


def test_status_incompleto_distingue_arquivos_ausentes(tmp_path):
    configuracoes = Configuracoes(
        rag_diretorio_documentos=tmp_path / "documentos",
        rag_diretorio_indice=tmp_path / "indice",
        rag_caminho_embeddings=tmp_path / "modelo",
    )
    estado = fabrica.consultar_estado_rag(configuracoes)
    assert estado["estado"] == "CONFIGURACAO_INCOMPLETA"
    assert estado["componentes"]["manifesto"] == "AUSENTE"
    assert estado["componentes"]["indice_faiss"] == "AUSENTE_OU_INCOMPLETO"
    assert estado["componentes"]["modelo_embeddings"] == "AUSENTE"
    assert estado["componentes"]["fontes_oficiais_verificadas"] == "NAO_VERIFICADAS"
    assert estado["componentes"]["teste_provedor_real"] == "NAO_EXECUTADO"


def test_status_recusa_manifesto_invalido(tmp_path):
    configuracoes = _config(tmp_path)
    configuracoes.rag_diretorio_indice.mkdir()
    (configuracoes.rag_diretorio_indice / "manifesto.json").write_text(
        json.dumps({"versao_formato": 999}), encoding="utf-8"
    )
    estado = fabrica.consultar_estado_rag(configuracoes)
    assert estado["componentes"]["manifesto"] == "INVALIDO"
    assert estado["componentes"]["indice_faiss"] == "AUSENTE_OU_INCOMPLETO"
    assert estado["estado"] == "CONFIGURACAO_INCOMPLETA"


def test_status_valida_artefatos_e_incompatibilidade_de_revisao(tmp_path, monkeypatch):
    configuracoes = _config(tmp_path)
    configuracoes.rag_diretorio_indice.mkdir()
    _reconstruir_indice(configuracoes.rag_diretorio_indice)

    class CodificadorIncompativel(CodificadorStatusTeste):
        revisao_modelo = "revisao-b"
        fingerprint_modelo = hashlib.sha256(b"outro-modelo").hexdigest()

    monkeypatch.setattr(fabrica, "obter_codificador_embeddings", lambda *args: CodificadorIncompativel())
    estado = fabrica.consultar_estado_rag(configuracoes)
    assert estado["componentes"]["manifesto"] == "ESTRUTURALMENTE_VALIDO"
    assert estado["componentes"]["indice_faiss"] == "INCOMPATIVEL_COM_MODELO"
    assert estado["componentes"]["modelo_embeddings"] == "INCOMPATIVEL_COM_INDICE"
    assert estado["estado"] == "CONFIGURACAO_INCOMPLETA"


def test_status_nao_chama_provedor_e_nunca_atesta_fontes_automaticamente(tmp_path):
    configuracoes = _config(tmp_path)
    estado = fabrica.consultar_estado_rag(configuracoes)
    assert estado["componentes"]["provedor_generativo"] == "NAO_CONFIGURADO"
    assert estado["componentes"]["teste_provedor_real"] == "NAO_EXECUTADO"
    assert estado["documentos_cientificos_oficiais_verificados"] is False
    assert estado["estado"] != "PRONTO"
