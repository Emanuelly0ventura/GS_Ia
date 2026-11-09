import pytest

import app.banco.conexao as conexao

def test_rejeita_driver_que_nao_e_postgresql():
    with pytest.raises(ValueError):
        conexao.criar_engine_leitura("sqlite:///arquivo.db")

def test_configura_engine_postgresql_com_transacoes_read_only(monkeypatch):
    chamada = {}
    marcador = object()

    def engine_falso(url, **opcoes):
        chamada["url"] = url
        chamada["opcoes"] = opcoes
        return marcador

    monkeypatch.setattr(conexao, "create_engine", engine_falso)
    resultado = conexao.criar_engine_leitura("postgresql://usuario:senha@localhost/banco")

    assert resultado is marcador
    assert chamada["url"].drivername == "postgresql+psycopg"
    assert chamada["opcoes"]["connect_args"] == {
        "options": "-c default_transaction_read_only=on"
    }
