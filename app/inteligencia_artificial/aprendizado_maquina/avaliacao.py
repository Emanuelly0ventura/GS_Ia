from typing import Any

from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

from app.inteligencia_artificial.aprendizado_maquina.detector_anomalias import DetectorAnomalias
from app.inteligencia_artificial.aprendizado_maquina.esquemas import LeituraParaModelo

def avaliar_detector(
    detector: DetectorAnomalias,
    leituras: list[LeituraParaModelo],
    rotulos_anomalia: list[bool],
) -> dict[str, Any]:
    if not leituras or len(leituras) != len(rotulos_anomalia):
        raise ValueError("As leituras e os rótulos precisam ter o mesmo tamanho não vazio.")
    previstos = detector.classificar_lote(leituras)
    matriz = confusion_matrix(rotulos_anomalia, previstos, labels=[False, True])
    return {
        "quantidade_avaliada": len(leituras),
        "precisao": float(precision_score(rotulos_anomalia, previstos, zero_division=0)),
        "revocacao": float(recall_score(rotulos_anomalia, previstos, zero_division=0)),
        "f1": float(f1_score(rotulos_anomalia, previstos, zero_division=0)),
        "matriz_confusao": {
            "ordem_rotulos": ["NORMAL", "ANOMALIA"],
            "valores": matriz.tolist(),
        },
        "predicoes": previstos,
    }
