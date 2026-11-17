import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.inteligencia_artificial.recomendacoes.esquemas import (
    CatalogoRecomendacoes,
    ContextoRecuperacao,
    Indicador,
    ObservacaoHumana,
)
from app.inteligencia_artificial.recomendacoes import recuperacao
from app.inteligencia_artificial.recomendacoes.recuperacao import carregar_catalogo, recuperar


@pytest.fixture(scope="module")
def catalogo():
    return carregar_catalogo(Path(__file__).parent / "fixtures" / "recomendacoes_etapa11.json")


def contexto(cultura="milho", **indicadores):
    return ContextoRecuperacao(cultura=cultura, id_talhao="TALHAO-TESTE", indicadores=indicadores)


def ids(resultado):
    return [item.recomendacao.id for item in resultado.recomendacoes]


def test_catalogo_tem_os_25_ids_unicos(catalogo):
    assert sorted(item.id for item in catalogo.recomendacoes) == [
        f"REC{i:03d}" for i in range(1, 26)
    ]


@pytest.mark.parametrize("campo", [
    "id", "tema", "culturas_aplicaveis", "condicoes_aplicacao", "dados_exigidos",
    "orientacao_tecnica", "justificativa", "criterio_prioridade", "referencias",
    "restricoes_e_ressalvas", "acionavel", "estado_curadoria",
])
def test_rejeita_campo_obrigatorio_ausente(catalogo, campo):
    dados = catalogo.model_dump(mode="json")
    del dados["recomendacoes"][0][campo]
    with pytest.raises(ValidationError):
        CatalogoRecomendacoes.model_validate_json(json.dumps(dados))


@pytest.mark.parametrize("erro", ["duplicado", "quantidade", "condicao", "json"])
def test_rejeita_catalogo_invalido(catalogo, tmp_path, erro):
    dados = catalogo.model_dump(mode="json")
    itens = dados["recomendacoes"]
    if erro == "duplicado":
        itens[-1]["id"] = itens[0]["id"]
    elif erro == "quantidade":
        itens.clear()
    elif erro == "condicao":
        itens[0]["condicoes_aplicacao"][0]["indicador"] = "nao_declarado"
    caminho = tmp_path / "catalogo.json"
    caminho.write_text("{" if erro == "json" else json.dumps(dados), encoding="utf-8")
    with pytest.raises(ValidationError):
        carregar_catalogo(caminho)



@pytest.fixture
def evidencias_artificiais(monkeypatch):
    """Simula somente a fronteira interna para testar seleção; não comprova dados de campo."""
    def instalar(**indicadores):
        evidencias = tuple(
            recuperacao._EvidenciaVerificada(
                indicador=nome, valor=valor, id_talhao="TALHAO-TESTE",
                observado_em=datetime(2026, 1, 1, tzinfo=timezone.utc),
                referencia_origem="FIXTURE_SINTETICA", origem="SENSOR",
            )
            for nome, valor in indicadores.items()
        )
        monkeypatch.setattr(recuperacao, "_obter_evidencias_verificadas", lambda _: evidencias)
        return evidencias

    return instalar


@pytest.fixture
def observacao_declarada():
    return ObservacaoHumana(
        id_observacao="OBS-TESTE", indicador="murcha_observada", valor=True,
        id_talhao="TALHAO-TESTE", observado_em=datetime(2026, 1, 1, tzinfo=timezone.utc),
        observador_declarado="produtor", observacoes_complementares="Detalhe privado de teste",
    )


def motivos(resultado, id_recomendacao):
    return {(item.motivo, item.indicador) for item in resultado.exclusoes
            if item.id_recomendacao == id_recomendacao}


def test_observacao_humana_declarada_nao_e_evidencia(catalogo, observacao_declarada):
    assert observacao_declarada.origem == "INSPECAO_HUMANA"
    assert observacao_declarada.estado_verificacao == "NAO_VERIFICADA"
    assert observacao_declarada.autenticacao == "NAO_DISPONIVEL"
    assert observacao_declarada.observador_declarado == "produtor"
    consulta = ContextoRecuperacao(
        cultura="milho", id_talhao="TALHAO-TESTE", observacoes_humanas=(observacao_declarada,)
    )
    resultado = recuperar(catalogo, consulta)
    assert ids(resultado) == []
    assert motivos(resultado, "REC008") == {
        ("OBSERVACAO_HUMANA_NAO_VERIFICADA", "murcha_observada")
    }
    assert observacao_declarada.observacoes_complementares not in repr(resultado)


@pytest.mark.parametrize(("campo", "valor"), [
    ("origem", "REAL"), ("estado_verificacao", "VERIFICADA"), ("autenticacao", "AUTENTICADA"),
])
def test_observacao_humana_rejeita_rotulos_de_promocao(observacao_declarada, campo, valor):
    dados = observacao_declarada.model_dump()
    dados[campo] = valor
    with pytest.raises(ValidationError):
        ObservacaoHumana.model_validate(dados)


@pytest.mark.parametrize("campo", ["id_talhao", "observado_em"])
def test_exige_talhao_e_data_em_registros_de_evidencia(
    observacao_declarada, evidencias_artificiais, campo
):
    evidencia, = evidencias_artificiais(murcha_observada=True)
    for registro in (observacao_declarada, evidencia):
        dados = registro.model_dump()
        del dados[campo]
        with pytest.raises(ValidationError):
            type(registro).model_validate(dados)


def test_recusa_evidencia_de_outro_talhao_ou_sem_talhao_de_consulta(
    catalogo, evidencias_artificiais
):
    evidencias_artificiais(agua_empossada=True)
    for talhao in (None, "OUTRO-TALHAO"):
        resultado = recuperar(catalogo, ContextoRecuperacao(cultura="milho", id_talhao=talhao))
        assert ids(resultado) == []


@pytest.mark.parametrize(("origem", "motivo"), [
    ("REAL", "PROCEDENCIA_DESCONHECIDA"),
    ("DESCONHECIDO", "PROCEDENCIA_DESCONHECIDA"),
    ("SIMULADO", "INDICADOR_SIMULADO"),
])
def test_rotulo_de_entrada_nao_estabelece_procedencia(catalogo, origem, motivo):
    consulta = contexto(agua_empossada=Indicador(valor=True, origem=origem))
    resultado = recuperar(catalogo, consulta)
    assert ids(resultado) == []
    assert motivos(resultado, "REC001") == {(motivo, "agua_empossada")}
    assert resultado.indicadores_simulados == (("agua_empossada",) if origem == "SIMULADO" else ())


def test_contexto_rejeita_evidencias_injetadas_pelo_chamador():
    dados = contexto().model_dump()
    dados["evidencias_verificadas"] = ()
    with pytest.raises(ValidationError):
        ContextoRecuperacao.model_validate(dados)


@pytest.mark.parametrize(("cultura", "sinais", "esperado"), [
    ("Milho", {"agua_empossada": True}, "REC001"),
    ("Feijão", {"agua_empossada": True}, "REC011"),
    ("tomate", {"condensacao_observada": True, "cultivo_protegido": True}, "REC021"),
])
def test_recupera_preliminares_com_fixture_interna(
    catalogo, evidencias_artificiais, cultura, sinais, esperado
):
    evidencias = evidencias_artificiais(**sinais)
    resultado = recuperar(catalogo, contexto(cultura))
    assert ids(resultado) == [esperado]
    item, = resultado.recomendacoes
    assert item.estado_apresentacao == "PRELIMINAR"
    assert item.recomendacao.estado_curadoria == "PENDENTE"
    assert item.recomendacao.restricoes_e_ressalvas
    assert item.evidencias_utilizadas == evidencias
    assert all(fonte.estado_curadoria == "PENDENTE" and fonte.revisao is None
               for fonte in item.recomendacao.referencias)


def test_catalogo_inteiro_permanece_pendente(catalogo):
    assert all(item.estado_curadoria == "PENDENTE" for item in catalogo.recomendacoes)
    assert all(fonte.estado_curadoria == "PENDENTE" and fonte.revisao is None
               for item in catalogo.recomendacoes for fonte in item.referencias)


@pytest.mark.parametrize(("cultura", "motivo"), [
    (None, "CULTURA_AUSENTE"), ("alface", "CULTURA_INCOMPATIVEL"),
])
def test_exclui_cultura_ausente_ou_incompativel(catalogo, evidencias_artificiais, cultura, motivo):
    evidencias_artificiais(agua_empossada=True)
    resultado = recuperar(catalogo, contexto(cultura))
    assert ids(resultado) == []
    assert motivos(resultado, "REC001") == {(motivo, None)}


def test_condicao_falsa_e_dado_ausente_tem_motivos_distintos(catalogo, evidencias_artificiais):
    evidencias_artificiais(condensacao_observada=False)
    resultado = recuperar(catalogo, contexto("tomate"))
    assert ids(resultado) == []
    assert motivos(resultado, "REC021") == {
        ("CONDICAO_NAO_ATENDIDA", "condensacao_observada"),
        ("INDICADOR_AUSENTE", "cultivo_protegido"),
    }


def test_acionavel_exige_curadoria_registrada_e_evidencia_interna(catalogo, evidencias_artificiais):
    dados = catalogo.model_dump(mode="json")
    item = dados["recomendacoes"][0]
    item["acionavel"] = True
    com_pendencia = CatalogoRecomendacoes.model_validate_json(json.dumps(dados))
    evidencias_artificiais(agua_empossada=True)
    resultado = recuperar(com_pendencia, contexto())
    assert ids(resultado) == []
    assert motivos(resultado, "REC001") == {("CURADORIA_PENDENTE", None)}

    fonte = item["referencias"][0]
    fonte["estado_curadoria"] = "REVISADA"
    with pytest.raises(ValidationError):
        CatalogoRecomendacoes.model_validate_json(json.dumps(dados))

    fonte["revisao"] = {
        "responsavel": "Fixture de teste",
        "data": "2026-01-01",
        "fonte_consultada": "Fonte sintética de teste",
        "trecho_ou_evidencia": "Trecho sintético de teste",
    }
    item["estado_curadoria"] = "REVISADA"
    revisado = CatalogoRecomendacoes.model_validate_json(json.dumps(dados))
    assert recuperar(revisado, contexto()).recomendacoes[0].estado_apresentacao == "REVISADA"
    evidencias_artificiais()
    assert ids(recuperar(revisado, contexto(agua_empossada=Indicador(valor=True, origem="REAL")))) == []


def test_ordem_independe_do_catalogo(catalogo, evidencias_artificiais):
    evidencias_artificiais(
        solo_exposto_observado=True, murcha_observada=True,
        agua_empossada=True, textura_variavel_observada=True,
    )
    invertido = CatalogoRecomendacoes(recomendacoes=tuple(reversed(catalogo.recomendacoes)))
    resultado = recuperar(catalogo, contexto())
    assert ids(resultado) == ["REC001", "REC008", "REC003", "REC005"]
    assert resultado == recuperar(invertido, contexto())


def test_aceita_resultado_vazio(catalogo, evidencias_artificiais):
    evidencias_artificiais(sinal_sem_correspondencia=True)
    assert ids(recuperar(catalogo, contexto())) == []
