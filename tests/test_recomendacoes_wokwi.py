import asyncio
import json

import pytest
from pydantic import ValidationError

from app.inteligencia_artificial.recomendacoes import esquemas
from app.inteligencia_artificial.recomendacoes.esquemas import (
    AVISO_UMIDADE_SOLO,
    CapturaDemonstrativa,
    CatalogoRecomendacoes,
    CondicaoSensor,
    ContextoRecuperacao,
    Indicador,
)
from app.inteligencia_artificial.recomendacoes.orquestracao import orquestrar
from app.inteligencia_artificial.recomendacoes.recuperacao import carregar_catalogo, recuperar
from app.nucleo.configuracoes import Configuracoes
from app.telemetria.esquemas import LeituraIoT, UNIDADES_CANONICAS, UNIDADES_ENTRADA
from app.telemetria.rotas import adaptar_para_indicadores
from tests.test_orquestracao_recomendacoes import GeradorSimulado


@pytest.fixture
def catalogo_demo():
    return carregar_catalogo()


def consulta(cultura, **valores):
    metadados = None
    if "umidadeSolo" in valores:
        metadados = {
            "simulado": True,
            "origem": "DHT22_TEMPERATURA",
            "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA",
            "temperaturaFonteC": 15 + valores["umidadeSolo"] / 5,
        }
    return ContextoRecuperacao(
        cultura=cultura,
        captura_wokwi=CapturaDemonstrativa(
            source="WOKWI_HIVEMQ_NODE_RED", values=valores,
            units={nome: UNIDADES_CANONICAS[nome] for nome in valores},
            metadados_umidade_solo=metadados,
        ),
    )


def ids(resultado):
    return [item.recomendacao.id for item in resultado.recomendacoes]


def test_catalogo_ativo_tem_quatro_indicadores_tres_culturas_e_curadoria_pendente(catalogo_demo):
    itens = catalogo_demo.recomendacoes
    assert len(itens) == len({item.id for item in itens}) == 7
    assert {cultura for item in itens for cultura in item.culturas_aplicaveis} == {
        "milho", "feijão", "tomate"
    }
    assert {nome for item in itens for nome in item.dados_exigidos} == set(UNIDADES_CANONICAS)
    for item in itens:
        assert item.estado_curadoria == "PENDENTE" and not item.acionavel
        assert all(fonte.estado_curadoria == "PENDENTE" for fonte in item.referencias)
        assert all(isinstance(condicao, CondicaoSensor) for condicao in item.condicoes_aplicacao)


@pytest.mark.parametrize(("campo", "valor"), [
    ("culturas_aplicaveis", ["alface"]),
    ("dados_exigidos", ["umidadeSolo", "solo_exposto"]),
    ("condicoes_aplicacao", [
        {"indicador": "solo_exposto", "operador": "MAIOR_OU_IGUAL", "limite_demonstrativo": 25}
    ]),
    ("acionavel", True),
])
def test_catalogo_demo_rejeita_condicoes_fora_do_escopo(catalogo_demo, campo, valor):
    dados = catalogo_demo.model_dump(mode="json")
    dados["recomendacoes"][0][campo] = valor
    with pytest.raises(ValidationError):
        CatalogoRecomendacoes.model_validate_json(json.dumps(dados))


@pytest.mark.parametrize(("cultura", "valores", "esperados"), [
    ("milho", {"temperaturaAr": 32, "umidadeSolo": 25}, ["REC028", "REC026"]),
    ("milho", {"temperaturaAr": 32}, []),
    ("milho", {"temperaturaAr": 31.9, "umidadeSolo": 25}, ["REC026"]),
    ("feijão", {"temperaturaAr": 32, "umidadeSolo": 75}, ["REC027", "REC029"]),
    ("tomate", {"temperaturaAr": 32, "umidadeAr": 80, "luminosidade": 800}, [
        "REC031", "REC030", "REC032"
    ]),
    ("tomate", {"temperaturaAr": 32, "umidadeAr": 79.9, "luminosidade": 801}, []),
    ("tomate", {"umidadeSolo": 25}, []),
    ("alface", {"temperaturaAr": 32, "umidadeSolo": 25}, []),
])
def test_selecao_demo_exige_cultura_e_condicoes(catalogo_demo, cultura, valores, esperados):
    assert ids(recuperar(catalogo_demo, consulta(cultura, **valores))) == esperados


def test_indicador_simulado_avulso_nao_habilita_demonstracao(catalogo_demo):
    contexto = ContextoRecuperacao(
        cultura="milho", indicadores={"umidadeSolo": Indicador(valor=True, origem="SIMULADO")}
    )
    resultado = recuperar(catalogo_demo, contexto)
    assert not resultado.recomendacoes
    assert any(item.motivo == "CONTEXTO_WOKWI_AUSENTE" for item in resultado.exclusoes)


@pytest.mark.parametrize("alteracao", [
    {"source": "DESCONHECIDO"},
    {"metadados_umidade_solo": None},
    {"metadados_umidade_solo": {
        "origem": "DHT22_UMIDADE", "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA",
        "simulado": True, "temperaturaFonteC": 20,
    }},
    {"metadados_umidade_solo": {
        "origem": "DHT22_TEMPERATURA", "metodo": "OUTRO",
        "simulado": True, "temperaturaFonteC": 20,
    }},
    {"metadados_umidade_solo": {
        "origem": "DHT22_TEMPERATURA", "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA",
        "simulado": 1, "temperaturaFonteC": 20,
    }},
    {"units": {"umidadeSolo": "°C"}},
    {"values": {"umidadeSolo": True}},
    {"values": {"umidadeSolo": float("nan")}},
    {"values": {"umidadeSolo": 101}},
])
def test_rejeita_captura_sem_procedencia_ou_valores_adequados(alteracao):
    dados = consulta("milho", umidadeSolo=25).captura_wokwi.model_dump()
    with pytest.raises(ValidationError):
        CapturaDemonstrativa.model_validate({**dados, **alteracao})


@pytest.mark.parametrize(("temperatura_dht", "percentual"), [(15, 0), (25, 50), (35, 100)])
def test_captura_canonica_reaproveita_conversao_existente_e_canais_independentes(
    catalogo_demo, temperatura_dht, percentual
):
    payload = LeituraIoT.model_validate({
        "deviceId": "fixture-iot", "observationId": "fixture-demo", "measuredAt": "2026-01-01T00:00:00Z",
        "source": "WOKWI_HIVEMQ_NODE_RED", "units": UNIDADES_ENTRADA,
        "values": {"temperaturaAr": 32, "umidadeAr": 80, "umidadeSolo": temperatura_dht,
                   "luminosidade": 800},
    })
    valores, unidades, complementos = adaptar_para_indicadores(payload)
    assert valores == {"temperaturaAr": 32, "umidadeAr": 80, "umidadeSolo": percentual,
                       "luminosidade": 800}
    assert complementos["umidadeSolo"]["temperaturaFonteC"] == temperatura_dht
    contexto = ContextoRecuperacao(cultura="tomate", captura_wokwi=CapturaDemonstrativa(
        source=payload.source, values=valores, units=unidades,
        metadados_umidade_solo=complementos["umidadeSolo"],
    ))
    gerador = GeradorSimulado()
    resultado = asyncio.run(orquestrar(catalogo_demo, contexto, gerador))
    assert resultado.estado == "CONCLUIDA"
    esperados = ["REC031", "REC030", "REC032"]
    if percentual == 100:
        esperados.insert(1, "REC027")
    assert [item.id_recomendacao for item in resultado.orientacoes] == esperados
    recebidos = gerador.chamadas[0].recomendacoes
    leituras = {sinal.indicador: sinal for item in recebidos for sinal in item.indicadores}
    origens = {"temperaturaAr": "BMP180_TEMPERATURA", "umidadeAr": "DHT22_UMIDADE",
               "umidadeSolo": "DHT22_TEMPERATURA", "luminosidade": "LDR"}
    for nome, sinal in leituras.items():
        assert sinal.origem == origens[nome] and sinal.simulado
        assert sinal.source == payload.source and sinal.valor == valores[nome]
    if percentual == 100:
        assert leituras["umidadeSolo"].metodo == "CONVERSAO_LINEAR_DEMONSTRATIVA"
        assert AVISO_UMIDADE_SOLO in recebidos[1].ressalvas
    assert all(item.estado_apresentacao == "PRELIMINAR" for item in recebidos)
    assert all(item.estado_curadoria == "PENDENTE" for item in recebidos)
    por_id = {item.id: item for item in catalogo_demo.recomendacoes}
    assert all(item.prioridade == por_id[item.id_recomendacao].criterio_prioridade.nivel
               for item in recebidos)


def test_orquestracao_demo_vazia_nao_chama_gerador(catalogo_demo):
    gerador = GeradorSimulado()
    resultado = asyncio.run(orquestrar(
        catalogo_demo, consulta("milho", temperaturaAr=32), gerador
    ))
    assert resultado.estado == "SEM_EVIDENCIA_SUFICIENTE"
    assert not gerador.chamadas
    assert not resultado.orientacoes


@pytest.mark.parametrize(("valores", "legados", "esperados"), [
    (
        {"temperaturaAr": 32, "umidadeAr": 80, "umidadeSolo": 25, "luminosidade": 800},
        {},
        ("luminosidade", "temperaturaAr", "umidadeAr", "umidadeSolo"),
    ),
    (
        {"umidadeAr": 60, "temperaturaAr": 28},
        {},
        ("temperaturaAr", "umidadeAr"),
    ),
    ({}, {"z": "SIMULADO", "a": "SIMULADO", "b": "DESCONHECIDO"}, ("a", "z")),
    (
        {"umidadeSolo": 25, "luminosidade": 800},
        {"umidadeSolo": "SIMULADO", "temperaturaAr": "SIMULADO"},
        ("luminosidade", "temperaturaAr", "umidadeSolo"),
    ),
    ({}, {"umidadeAr": "REAL"}, ()),
])
def test_contabiliza_indicadores_simulados_dos_dois_formatos(
    catalogo_demo, valores, legados, esperados
):
    captura = consulta("milho", **valores).captura_wokwi if valores else None
    indicadores = {nome: Indicador(valor=True, origem=origem) for nome, origem in legados.items()}
    contexto = ContextoRecuperacao(cultura="milho", captura_wokwi=captura, indicadores=indicadores)
    assert recuperar(catalogo_demo, contexto).indicadores_simulados == esperados


@pytest.mark.parametrize(("temperatura", "percentual"), [
    (15, 0), (25, 50), (35, 100), (22.3, 36.5), (10, 0), (40, 100),
])
@pytest.mark.parametrize("umidade_ar", [0, 100])
def test_conversao_consistente_independe_da_umidade_do_ar(temperatura, percentual, umidade_ar):
    dados = consulta("milho", umidadeSolo=percentual, umidadeAr=umidade_ar).captura_wokwi.model_dump()
    dados["metadados_umidade_solo"]["temperatura_fonte_c"] = temperatura
    captura = CapturaDemonstrativa.model_validate(dados)
    assert captura.values == {"umidadeSolo": percentual, "umidadeAr": umidade_ar}


@pytest.mark.parametrize(("temperatura", "percentual"), [(35, 25), (15, 50), (25, 100)])
def test_rejeita_percentual_incompativel_com_temperatura(temperatura, percentual):
    dados = consulta("milho", umidadeSolo=percentual).captura_wokwi.model_dump()
    dados["metadados_umidade_solo"]["temperatura_fonte_c"] = temperatura
    with pytest.raises(ValidationError, match="percentual de umidadeSolo não corresponde"):
        CapturaDemonstrativa.model_validate(dados)


@pytest.mark.parametrize("valor", [-1, 101, "25", float("inf"), float("-inf"), float("nan")])
def test_rejeita_percentual_fora_da_faixa_ou_invalido(valor):
    dados = consulta("milho", umidadeSolo=25).captura_wokwi.model_dump()
    dados["values"]["umidadeSolo"] = valor
    with pytest.raises(ValidationError):
        CapturaDemonstrativa.model_validate(dados)


@pytest.mark.parametrize("temperatura", [-41, 81, "inválida", float("inf"), float("nan")])
def test_rejeita_temperatura_de_origem_fora_da_faixa_ou_invalida(temperatura):
    dados = consulta("milho", umidadeSolo=25).captura_wokwi.model_dump()
    dados["metadados_umidade_solo"]["temperatura_fonte_c"] = temperatura
    with pytest.raises(ValidationError):
        CapturaDemonstrativa.model_validate(dados)


def test_captura_sem_umidade_do_solo_dispensa_metadados():
    captura = consulta("milho", umidadeAr=50, temperaturaAr=25).captura_wokwi
    assert captura.metadados_umidade_solo is None
    assert "umidadeSolo" not in captura.values


def test_validacao_usa_os_mesmos_limites_configurados_na_telemetria(monkeypatch):
    dados = consulta("milho", umidadeSolo=50).captura_wokwi.model_dump()
    dados["metadados_umidade_solo"]["temperatura_fonte_c"] = 30
    monkeypatch.setattr(
        esquemas, "obter_configuracoes", lambda: Configuracoes(
            telemetry_soil_moisture_temp_min_c=20,
            telemetry_soil_moisture_temp_max_c=40,
        ),
    )
    assert CapturaDemonstrativa.model_validate(dados).values["umidadeSolo"] == 50
