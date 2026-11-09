import argparse
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.inteligencia_artificial.aprendizado_maquina.detector_anomalias import DetectorAnomalias
from app.inteligencia_artificial.aprendizado_maquina.esquemas import LeituraParaModelo
from app.nucleo.configuracoes import obter_configuracoes

FIXTURA_PADRAO = RAIZ / "tests" / "fixtures" / "isolation_forest_rotulado.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Treina Isolation Forest com dados controlados.")
    parser.add_argument("--dados", type=Path, default=FIXTURA_PADRAO)
    parser.add_argument("--saida", type=Path, default=None)
    argumentos = parser.parse_args()
    dados = json.loads(argumentos.dados.read_text(encoding="utf-8"))
    if dados.get("metadados", {}).get("origem") != "SIMULADO_TESTE":
        raise SystemExit("Este script de demonstração aceita somente conjuntos SIMULADO_TESTE.")
    configuracoes = obter_configuracoes()
    detector = DetectorAnomalias(
        numero_estimadores=configuracoes.ml_numero_estimadores,
        contaminacao=configuracoes.ml_contaminacao,
        semente_aleatoria=configuracoes.ml_semente_aleatoria,
        minimo_observacoes=configuracoes.ml_minimo_observacoes,
        versao_modelo=configuracoes.ml_versao_modelo,
    )
    leituras = [LeituraParaModelo.model_validate(item) for item in dados["treinamento"]]
    manifesto = detector.treinar(leituras)
    destino = argumentos.saida or configuracoes.ml_caminho_modelo
    detector.salvar(destino)
    print(json.dumps({"arquivoModelo": str(destino), "manifesto": manifesto}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
