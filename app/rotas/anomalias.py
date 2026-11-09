from functools import lru_cache

from fastapi import APIRouter, HTTPException

from app.inteligencia_artificial.aprendizado_maquina.detector_anomalias import DetectorAnomalias
from app.inteligencia_artificial.aprendizado_maquina.esquemas import LeituraParaModelo, ResultadoAnomalia
from app.nucleo.configuracoes import obter_configuracoes

roteador = APIRouter(prefix="/api/v1/anomalias", tags=["Anomalias estatísticas (demonstração)"])

@lru_cache(maxsize=4)
def carregar_detector_demo(caminho: str) -> DetectorAnomalias:
    return DetectorAnomalias.carregar(caminho)

@roteador.post("/analisar-demo", response_model=ResultadoAnomalia, summary="Analisa uma leitura simulada com Isolation Forest")
def analisar_demo(leitura: LeituraParaModelo) -> ResultadoAnomalia:
    configuracoes = obter_configuracoes()
    if configuracoes.ambiente.casefold() not in {"desenvolvimento", "teste", "test"}:
        raise HTTPException(status_code=404, detail="Recurso disponível somente em ambiente de desenvolvimento ou teste.")
    if leitura.origem != "SIMULADO_TESTE":
        raise HTTPException(status_code=422, detail="A demonstração aceita exclusivamente dados com origem SIMULADO_TESTE.")
    try:
        detector = carregar_detector_demo(str(configuracoes.ml_caminho_modelo))
    except FileNotFoundError as erro:
        raise HTTPException(status_code=503, detail="Modelo de demonstração ausente. Execute scripts/treinar_modelo.py.") from erro
    except (ValueError, KeyError) as erro:
        raise HTTPException(status_code=503, detail="Artefato do modelo incompatível ou inválido. Treine novamente o modelo.") from erro
    if detector.versao_modelo != configuracoes.ml_versao_modelo:
        raise HTTPException(status_code=503, detail="A versão configurada não corresponde ao artefato; treine novamente o modelo.")
    try:
        return detector.predizer(leitura)
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro
