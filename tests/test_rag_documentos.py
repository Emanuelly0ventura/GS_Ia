import json

import pytest

from app.inteligencia_artificial.rag.esquemas import DocumentoConhecimento
from app.inteligencia_artificial.rag.ingestao import ingerir_diretorio
from app.inteligencia_artificial.rag.segmentacao import segmentar_documento


def criar_documento(diretorio, nome, identificador="embrapa-demo"):
    (diretorio / f"{nome}.md").write_text(
        "Umidade do solo é um dado contextual.\n\nA decisão depende da cultura e da região.",
        encoding="utf-8",
    )
    (diretorio / f"{nome}.metadata.json").write_text(json.dumps({
        "identificador": identificador,
        "titulo": "Documento de teste, não é fonte científica",
        "instituicao": "Fixture de teste",
        "referencia_origem": "TESTE://fixture-não-científica",
        "url": "https://example.invalid/fixture",
    }), encoding="utf-8")


def test_ingerir_documento_local_preserva_metadados(tmp_path):
    criar_documento(tmp_path, "teste")
    [documento] = ingerir_diretorio(tmp_path)
    assert documento.identificador == "embrapa-demo"
    assert documento.titulo.startswith("Documento de teste")
    assert documento.instituicao == "Fixture de teste"
    assert str(documento.url) == "https://example.invalid/fixture"
    assert "Umidade do solo" in documento.conteudo


def test_rejeitar_documento_sem_sidecar_obrigatorio(tmp_path):
    (tmp_path / "sem_metadados.txt").write_text("Conteúdo", encoding="utf-8")
    with pytest.raises(ValueError, match="Metadados obrigatórios ausentes"):
        ingerir_diretorio(tmp_path)


def test_rejeitar_documento_sem_metadados_obrigatorios(tmp_path):
    (tmp_path / "incompleto.txt").write_text("Conteúdo", encoding="utf-8")
    (tmp_path / "incompleto.metadata.json").write_text(
        json.dumps({"identificador": "x", "titulo": "Sem instituição"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Documento ou metadados inválidos"):
        ingerir_diretorio(tmp_path)


def test_rejeitar_identificadores_documentais_duplicados(tmp_path):
    criar_documento(tmp_path, "primeiro", "duplicado")
    criar_documento(tmp_path, "segundo", "duplicado")
    with pytest.raises(ValueError, match="duplicado"):
        ingerir_diretorio(tmp_path)


def test_rejeitar_documento_acima_do_limite_de_bytes(tmp_path):
    criar_documento(tmp_path, "grande")
    with pytest.raises(ValueError, match="excede 20 bytes"):
        ingerir_diretorio(tmp_path, limite_documento_bytes=20)


def test_rejeitar_total_de_ingestao_acima_do_limite(tmp_path):
    criar_documento(tmp_path, "total")
    with pytest.raises(ValueError, match="limite total"):
        ingerir_diretorio(tmp_path, limite_total_bytes=50)


def test_rejeitar_quantidade_de_documentos_acima_do_limite(tmp_path):
    criar_documento(tmp_path, "um", "um")
    criar_documento(tmp_path, "dois", "dois")
    with pytest.raises(ValueError, match="limite de 1 documentos"):
        ingerir_diretorio(tmp_path, limite_documentos=1)


def test_rejeitar_sidecar_acima_do_limite(tmp_path):
    criar_documento(tmp_path, "sidecar")
    with pytest.raises(ValueError, match="Metadados.*excedem 10 bytes"):
        ingerir_diretorio(tmp_path, limite_metadados_bytes=10)


def test_rejeitar_conteudo_que_nao_seja_utf8(tmp_path):
    (tmp_path / "invalido.txt").write_bytes(b"\xff\xfe")
    (tmp_path / "invalido.metadata.json").write_text(json.dumps({
        "identificador": "invalido",
        "titulo": "Documento inválido",
        "instituicao": "Fixture",
        "referencia_origem": "TESTE://utf8",
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="Documento ou metadados inválidos"):
        ingerir_diretorio(tmp_path)


def test_segmentacao_preserva_metadados_posicoes_e_trecho_de_origem(tmp_path):
    criar_documento(tmp_path, "teste")
    [documento] = ingerir_diretorio(tmp_path)
    trechos = segmentar_documento(documento, tamanho_maximo=100, sobreposicao=20)
    assert len(trechos) >= 1
    for trecho in trechos:
        assert trecho.identificador_documento == documento.identificador
        assert trecho.titulo == documento.titulo
        assert trecho.instituicao == documento.instituicao
        assert trecho.referencia_origem == documento.referencia_origem
        assert trecho.texto == documento.conteudo[trecho.inicio_caractere:trecho.fim_caractere].strip()


def test_falhar_configuracao_de_chunking_invalida(tmp_path):
    criar_documento(tmp_path, "teste")
    [documento] = ingerir_diretorio(tmp_path)
    with pytest.raises(ValueError, match="sobreposicao"):
        segmentar_documento(documento, tamanho_maximo=100, sobreposicao=100)


def test_segmentacao_respeita_limite_total_de_trechos(tmp_path):
    criar_documento(tmp_path, "longo")
    caminho = tmp_path / "longo.md"
    caminho.write_text("palavra " * 1000, encoding="utf-8")
    [documento] = ingerir_diretorio(tmp_path)
    with pytest.raises(ValueError, match="limite de 2 trechos"):
        segmentar_documento(documento, tamanho_maximo=100, sobreposicao=10, limite_trechos=2)
