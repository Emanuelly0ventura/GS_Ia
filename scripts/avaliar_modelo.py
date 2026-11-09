import argparse
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.inteligencia_artificial.aprendizado_maquina.avaliacao import avaliar_detector
from app.inteligencia_artificial.aprendizado_maquina.detector_anomalias import DetectorAnomalias
from app.inteligencia_artificial.aprendizado_maquina.esquemas import LeituraParaModelo
from app.nucleo.configuracoes import obter_configuracoes

FIXTURA_PADRAO = RAIZ / "tests" / "fixtures" / "isolation_forest_rotulado.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia Isolation Forest em dados rotulados sintéticos.")
    parser.add_argument("--dados", type=Path, default=FIXTURA_PADRAO)
    argumentos = parser.parse_args()
    dados = json.loads(argumentos.dados.read_text(encoding="utf-8"))
    if dados.get("metadados", {}).get("origem") != "SIMULADO_TESTE":
        raise SystemExit("Este avaliador de demonstração aceita somente conjuntos SIMULADO_TESTE.")
    configuracoes = obter_configuracoes()
    detector = DetectorAnomalias(
        numero_estimadores=configuracoes.ml_numero_estimadores,
        contaminacao=configuracoes.ml_contaminacao,
        semente_aleatoria=configuracoes.ml_semente_aleatoria,
        minimo_observacoes=configuracoes.ml_minimo_observacoes,
        versao_modelo=configuracoes.ml_versao_modelo,
    )
    treinamento = [LeituraParaModelo.model_validate(item) for item in dados["treinamento"]]
    detector.treinar(treinamento)
    avaliacao = dados["avaliacao"]
    leituras = [LeituraParaModelo.model_validate(item["leitura"]) for item in avaliacao]
    rotulos = [bool(item["rotuloAnomalia"]) for item in avaliacao]
    resultado = avaliar_detector(detector, leituras, rotulos)
    resultado["dadosSinteticos"] = True
    resultado["conjunto"] = dados["metadados"]["versao"]
    print(json.dumps(resultado, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
