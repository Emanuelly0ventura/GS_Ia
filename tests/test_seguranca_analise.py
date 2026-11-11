from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.inteligencia_artificial.rag import fabrica
from app.nucleo.configuracoes import Configuracoes
from app.rotas import conhecimento


def _request(ip="127.0.0.1"):
    return SimpleNamespace(client=SimpleNamespace(host=ip))


def test_ambiente_producao_sem_chave_fica_fechado(monkeypatch):
    monkeypatch.setattr(conhecimento, "obter_configuracoes", lambda: Configuracoes(ambiente="producao"))
    with pytest.raises(HTTPException) as erro:
        conhecimento.proteger_rota_analise(_request(), None)
    assert erro.value.status_code == 503


def test_desenvolvimento_sem_chave_fica_fechado_por_padrao(monkeypatch):
    monkeypatch.setattr(conhecimento, "obter_configuracoes", lambda: Configuracoes())
    with pytest.raises(HTTPException) as erro:
        conhecimento.proteger_rota_analise(_request(), None)
    assert erro.value.status_code == 503


def test_chave_configurada_exige_credencial(monkeypatch):
    configuracoes = Configuracoes(ambiente="producao", rag_analise_chave_api=SecretStr("a" * 40))
    monkeypatch.setattr(conhecimento, "obter_configuracoes", lambda: configuracoes)
    with pytest.raises(HTTPException) as erro:
        conhecimento.proteger_rota_analise(_request(), None)
    assert erro.value.status_code == 401


def test_chave_invalida_retorna_403_sem_refletir_segredo(monkeypatch):
    segredo = "chave-super-secreta-de-teste-1234567890"
    monkeypatch.setattr(
        conhecimento,
        "obter_configuracoes",
        lambda: Configuracoes(ambiente="producao", rag_analise_chave_api=SecretStr(segredo)),
    )
    with pytest.raises(HTTPException) as erro:
        conhecimento.proteger_rota_analise(_request(), "invalida-" + segredo)
    assert erro.value.status_code == 403
    assert segredo not in str(erro.value.detail)


def test_chave_valida_permite_acesso(monkeypatch):
    segredo = "chave-super-secreta-de-teste-1234567890"
    configuracoes = Configuracoes(ambiente="producao", rag_analise_chave_api=SecretStr(segredo))
    monkeypatch.setattr(conhecimento, "obter_configuracoes", lambda: configuracoes)
    conhecimento.limitador_analise.limpar()
    conhecimento.proteger_rota_analise(_request(), segredo)


def test_rate_limit_retorna_429_e_retry_after(monkeypatch):
    configuracoes = Configuracoes(
        ambiente="desenvolvimento",
        rag_analise_permitir_sem_chave_local=True,
        rag_analise_rate_limit_requisicoes=1,
        rag_analise_rate_limit_janela_segundos=60,
    )
    monkeypatch.setattr(conhecimento, "obter_configuracoes", lambda: configuracoes)
    conhecimento.limitador_analise.limpar()
    conhecimento.proteger_rota_analise(_request("192.0.2.1"), None)
    with pytest.raises(HTTPException) as erro:
        conhecimento.proteger_rota_analise(_request("192.0.2.1"), None)
    assert erro.value.status_code == 429
    assert int(erro.value.headers["Retry-After"]) > 0


def test_cache_de_codificador_reutiliza_modelo(monkeypatch, tmp_path):
    chamadas = []

    class CodificadorTeste:
        def __init__(self, *args, **kwargs):
            chamadas.append((args, kwargs))

    monkeypatch.setattr(fabrica, "SentenceTransformerLocal", CodificadorTeste)
    fabrica.obter_codificador_embeddings.cache_clear()
    primeiro = fabrica.obter_codificador_embeddings(str(tmp_path), "rev-a", "modelo", "query: ", "passage: ")
    segundo = fabrica.obter_codificador_embeddings(str(tmp_path), "rev-a", "modelo", "query: ", "passage: ")
    assert primeiro is segundo
    assert len(chamadas) == 1
    fabrica.obter_codificador_embeddings.cache_clear()
