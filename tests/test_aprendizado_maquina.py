import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from app.inteligencia_artificial.aprendizado_maquina.avaliacao import avaliar_detector
from app.inteligencia_artificial.aprendizado_maquina.caracteristicas import VARIAVEIS_MODELO
from app.inteligencia_artificial.aprendizado_maquina.detector_anomalias import DetectorAnomalias
from app.inteligencia_artificial.aprendizado_maquina.esquemas import LeituraParaModelo
from app.inteligencia_artificial.aprendizado_maquina.preparacao import preparar_leituras

CAMINHO_FIXTURA = Path(__file__).parent / "fixtures" / "isolation_forest_rotulado.json"
DADOS = json.loads(CAMINHO_FIXTURA.read_text(encoding="utf-8"))
UNIDADES = DADOS["metadados"]["unidades"]

def ler(item):
    return LeituraParaModelo.model_validate(item)

def criar_leitura(identificador="teste", valores=None, qualidade="VALIDA", unidades=None, origem="SIMULADO_TESTE"):
    return LeituraParaModelo(
        idObservacao=identificador,
        valores=valores or {nome: 0.0 for nome in VARIAVEIS_MODELO},
        unidades=unidades or UNIDADES,
        qualidade=qualidade,
        origem=origem,
    )

def criar_detector():
    detector = DetectorAnomalias(numero_estimadores=80, contaminacao=0.05, semente_aleatoria=17, minimo_observacoes=32)
    detector.treinar([ler(item) for item in DADOS["treinamento"]])
    return detector

def test_preparacao_produz_matriz_numerica_e_rastreia_descartes():
    completa = criar_leitura()
    incompleta = criar_leitura("faltante", valores={nome: 0.0 for nome in VARIAVEIS_MODELO[:-1]})
    invalida = criar_leitura("qualidade", qualidade="INVALIDA")
    conjunto = preparar_leituras([completa, incompleta, invalida])
    assert conjunto.matriz.shape == (1, 4)
    assert np.isfinite(conjunto.matriz).all()
    assert len(conjunto.descartadas) == 2

def test_esquema_rejeita_texto_booleano_e_valor_nao_finito():
    valores = {nome: 0.0 for nome in VARIAVEIS_MODELO}
    valores[VARIAVEIS_MODELO[0]] = "não numérico"
    with pytest.raises(ValidationError):
        criar_leitura(valores=valores)
    valores[VARIAVEIS_MODELO[0]] = True
    with pytest.raises(ValidationError):
        criar_leitura(valores=valores)
    valores[VARIAVEIS_MODELO[0]] = float("nan")
    with pytest.raises(ValidationError):
        criar_leitura(valores=valores)

def test_esquema_rejeita_variavel_inesperada():
    valores = {nome: 0.0 for nome in VARIAVEIS_MODELO}
    valores["phSolo"] = 6.5
    with pytest.raises(ValidationError):
        criar_leitura(valores=valores)

def test_dados_insuficientes_impedem_treinamento():
    detector = DetectorAnomalias(minimo_observacoes=32)
    with pytest.raises(ValueError, match="Dados insuficientes"):
        detector.treinar([ler(item) for item in DADOS["treinamento"][:10]])

def test_unidades_incompativeis_nao_sao_convertidas_silenciosamente():
    primeira = criar_leitura()
    unidades = dict(UNIDADES)
    unidades[VARIAVEIS_MODELO[0]] = "outra_unidade"
    segunda = criar_leitura("unidade-divergente", unidades=unidades)
    with pytest.raises(ValueError, match="Unidades incompatíveis"):
        preparar_leituras([primeira, segunda])

def test_isolation_forest_real_classifica_caso_atipico():
    detector = criar_detector()
    from sklearn.ensemble import IsolationForest
    assert isinstance(detector._modelo.named_steps["isolation_forest"], IsolationForest)
    valores = {nome: 0.0 for nome in VARIAVEIS_MODELO}
    valores = {nome: 7.0 for nome in VARIAVEIS_MODELO}
    resultado = detector.predizer(criar_leitura("atipica", valores=valores))
    assert resultado.classificada_como_anomalia is True
    assert resultado.origem_dados == "SIMULADO_TESTE"
    assert "não uma probabilidade" in resultado.justificativa

def test_inferencia_rejeita_origem_ou_qualidade_invalidas():
    detector = criar_detector()
    with pytest.raises(ValueError, match="Dados insuficientes"):
        detector.predizer(criar_leitura(qualidade="NAO_AVALIADA"))

def test_persistencia_carrega_modelo_e_preserva_resultado(tmp_path):
    detector = criar_detector()
    caminho = detector.salvar(tmp_path / "modelo.joblib")
    carregado = DetectorAnomalias.carregar(caminho)
    leitura = criar_leitura("persistencia")
    assert carregado.versao_modelo == detector.versao_modelo
    assert carregado.predizer(leitura).classificada_como_anomalia == detector.predizer(leitura).classificada_como_anomalia

def test_carregamento_trata_arquivo_inexistente_e_corrompido(tmp_path):
    with pytest.raises(FileNotFoundError):
        DetectorAnomalias.carregar(tmp_path / "nao-existe.joblib")
    corrompido = tmp_path / "corrompido.joblib"
    corrompido.write_bytes(b"nao e um artefato joblib confiavel")
    with pytest.raises(ValueError, match="Não foi possível carregar"):
        DetectorAnomalias.carregar(corrompido)

def test_metricas_sao_calculadas_e_identificadas_como_sinteticas():
    detector = criar_detector()
    amostras = DADOS["avaliacao"]
    resultado = avaliar_detector(detector, [ler(item["leitura"]) for item in amostras], [item["rotuloAnomalia"] for item in amostras])
    assert resultado["quantidade_avaliada"] == len(amostras)
    assert len(resultado["matriz_confusao"]["valores"]) == 2
    assert 0.0 <= resultado["precisao"] <= 1.0
    assert 0.0 <= resultado["revocacao"] <= 1.0
    assert 0.0 <= resultado["f1"] <= 1.0

def test_pontuacao_nao_e_rotulada_como_probabilidade():
    detector = criar_detector()
    resultado = detector.predizer(criar_leitura())
    resposta = resultado.model_dump(by_alias=True)
    assert "pontuacaoAnomalia" in resposta
    assert "probabilidade" not in resposta
    assert resposta["versaoModelo"] == "isolation-forest-v1"


def test_treinamento_reproduzivel_com_semente_fixa():
    leituras = [ler(item) for item in DADOS["treinamento"]]
    primeiro_detector = DetectorAnomalias(numero_estimadores=40, semente_aleatoria=99)
    segundo_detector = DetectorAnomalias(numero_estimadores=40, semente_aleatoria=99)
    primeiro = primeiro_detector.treinar(leituras)
    segundo = segundo_detector.treinar(leituras)
    observacao = ler(DADOS["avaliacao"][0]["leitura"])
    resultado_primeiro = primeiro_detector.predizer(observacao)
    resultado_segundo = segundo_detector.predizer(observacao)
    assert primeiro["configuracao"] == segundo["configuracao"]
    assert primeiro["versao_scikit_learn"] == segundo["versao_scikit_learn"]
    assert resultado_primeiro.classificada_como_anomalia == resultado_segundo.classificada_como_anomalia
    assert resultado_primeiro.pontuacao_anomalia == pytest.approx(resultado_segundo.pontuacao_anomalia)
