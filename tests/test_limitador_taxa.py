from app.nucleo.limitador_taxa import LimitadorTaxaMemoria


def test_limitador_tem_janela_por_cliente_e_expira():
    limitador = LimitadorTaxaMemoria()
    assert limitador.permitir("cliente-a", 1, 60, agora=10) == (True, 0)
    assert limitador.permitir("cliente-a", 1, 60, agora=11)[0] is False
    assert limitador.permitir("cliente-b", 1, 60, agora=11) == (True, 0)
    assert limitador.permitir("cliente-a", 1, 60, agora=60) == (True, 0)


def test_limitador_limpar_remove_estado():
    limitador = LimitadorTaxaMemoria()
    limitador.permitir("cliente-a", 1, 60, agora=10)
    limitador.limpar()
    assert limitador.permitir("cliente-a", 1, 60, agora=11) == (True, 0)
