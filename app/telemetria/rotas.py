from datetime import datetime, timezone
from functools import lru_cache
import logging
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.inteligencia_artificial.aprendizado_maquina.detector_anomalias import DetectorAnomalias
from app.inteligencia_artificial.aprendizado_maquina.esquemas import LeituraParaModelo
from app.nucleo.configuracoes import obter_configuracoes
from app.telemetria.banco import obter_fabrica_sessoes
from app.telemetria.conversoes import converter_temperatura_dht22_em_umidade_solo
from app.telemetria.esquemas import LeituraIoT, MetadadosUmidadeSolo, UNIDADES_CANONICAS
from app.telemetria.modelos import AnaliseAnomalia, Dispositivo, Leitura

roteador_telemetria = APIRouter(prefix="/api/v1/iot", tags=["Demonstração IoT"])
roteador_dashboard = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard IoT"])


logger = logging.getLogger("agroconnect.telemetria.ml")
STATUS_ML_PENDENTE = "PENDENTE"
STATUS_ML_CONCLUIDA = "CONCLUIDA"
STATUS_ML_FALHA = "FALHA"
MENSAGEM_ML_PENDENTE = "A captura foi persistida; a análise ML está pendente."
MENSAGEM_ML_FALHA = "A captura foi persistida, mas a análise ML falhou. Consulte os logs da API."


@lru_cache(maxsize=4)
def carregar_detector_telemetria(caminho: str) -> DetectorAnomalias:
    return DetectorAnomalias.carregar(caminho)


def _resposta_analise(resultado) -> dict[str, object]:
    return {
        "status": STATUS_ML_CONCLUIDA,
        "executed": True,
        "isAnomaly": resultado.classificada_como_anomalia,
        "classification": resultado.classificacao,
        "score": resultado.pontuacao_anomalia,
        "variables": resultado.variaveis_utilizadas,
        "analyzedAt": resultado.data_analise,
        "modelVersion": resultado.versao_modelo,
        "explanation": resultado.justificativa,
    }

def _sessao():
    fabrica = obter_fabrica_sessoes()
    if fabrica is None:
        raise HTTPException(status_code=503, detail="Banco de telemetria não configurado.")
    return fabrica()

def adaptar_para_indicadores(payload: LeituraIoT, limite_inferior_c: float = 15.0, limite_superior_c: float = 35.0) -> tuple[dict[str, float], dict[str, str], dict[str, object]]:
    """Converte a temperatura DHT22 enviada em umidadeSolo para percentual."""
    temperatura_dht = float(payload.values["umidadeSolo"])
    umidade_solo = converter_temperatura_dht22_em_umidade_solo(
        temperatura_dht,
        limite_inferior_c=limite_inferior_c,
        limite_superior_c=limite_superior_c,
    )
    metadados_solo = MetadadosUmidadeSolo(
        origem="DHT22_TEMPERATURA",
        metodo="CONVERSAO_LINEAR_DEMONSTRATIVA",
        simulado=True,
        temperatura_fonte_c=temperatura_dht,
    ).model_dump(mode="json", by_alias=True)
    valores = {
        "temperaturaAr": float(payload.values["temperaturaAr"]),
        "umidadeSolo": umidade_solo,
        "umidadeAr": float(payload.values["umidadeAr"]),
        "luminosidade": float(payload.values["luminosidade"]),
    }
    complementos: dict[str, object] = {"umidadeSolo": metadados_solo}
    return valores, dict(UNIDADES_CANONICAS), complementos

def _violacao_unicidade_observacao(erro: IntegrityError) -> bool:
    original = erro.orig
    nome_constraint = getattr(getattr(original, "diag", None), "constraint_name", None)
    if nome_constraint == "uq_iot_reading_observation":
        return True
    return (
        "UNIQUE constraint failed: iot_readings.device_id, iot_readings.observation_id"
        in str(original)
    )


@roteador_telemetria.post(
    "/readings", status_code=201,
    summary="Persiste uma captura IoT e tenta analisá-la com Isolation Forest",
)
def receber(payload: LeituraIoT):
    configuracoes = obter_configuracoes()
    try:
        valores, unidades, complementos = adaptar_para_indicadores(
            payload,
            limite_inferior_c=configuracoes.telemetry_soil_moisture_temp_min_c,
            limite_superior_c=configuracoes.telemetry_soil_moisture_temp_max_c,
        )
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro

    with _sessao() as db:
        try:
            dispositivo = db.scalar(
                select(Dispositivo).where(Dispositivo.device_id == payload.deviceId)
            )
            if dispositivo is None:
                dispositivo = Dispositivo(device_id=payload.deviceId, source=payload.source)
                db.add(dispositivo)
            dispositivo.last_seen_at = datetime.now(timezone.utc)
            dispositivo.source = payload.source
            leitura = Leitura(
                device_id=payload.deviceId,
                observation_id=payload.observationId,
                measured_at=payload.measuredAt,
                source=payload.source,
                quality=payload.quality,
                analysis_status=STATUS_ML_PENDENTE,
                values=valores,
                units=unidades,
                complements=complementos,
            )
            db.add(leitura)
            db.commit()
            reading_id = leitura.id
        except IntegrityError as erro:
            db.rollback()
            if _violacao_unicidade_observacao(erro):
                raise HTTPException(
                    status_code=409,
                    detail="observationId já recebido para este dispositivo.",
                ) from erro
            raise HTTPException(
                status_code=503,
                detail="Falha de integridade ao persistir a telemetria.",
            ) from erro
        except SQLAlchemyError as erro:
            db.rollback()
            raise HTTPException(
                status_code=503,
                detail="Banco de telemetria indisponível.",
            ) from erro

        # A captura já foi commitada. A inferência lê novamente os valores canônicos
        # persistidos e acontece numa transação separada, para uma falha ML não apagá-la.
        try:
            persistida = db.scalar(select(Leitura).where(Leitura.id == reading_id))
            if persistida is None:
                raise RuntimeError("Captura commitada não foi encontrada para análise.")
            detector = carregar_detector_telemetria(str(configuracoes.ml_caminho_modelo))
            if detector.versao_modelo != configuracoes.ml_versao_modelo:
                raise ValueError("A versão configurada não corresponde ao artefato carregado.")
            leitura_modelo = LeituraParaModelo(
                id_observacao=persistida.observation_id,
                id_dispositivo=persistida.device_id,
                registrado_em=persistida.measured_at,
                valores=persistida.values,
                unidades=persistida.units,
                qualidade="VALIDA",
                origem=persistida.source,
            )
            resultado = detector.predizer(leitura_modelo)
            db.add(AnaliseAnomalia(
                reading_id=persistida.id,
                model_version=resultado.versao_modelo,
                is_anomaly=resultado.classificada_como_anomalia,
                score=resultado.pontuacao_anomalia,
                analyzed_at=resultado.data_analise,
                variables=resultado.variaveis_utilizadas,
                explanation=resultado.justificativa,
            ))
            persistida.analysis_status = STATUS_ML_CONCLUIDA
            db.commit()
            return {
                "observationId": persistida.observation_id,
                "deviceId": persistida.device_id,
                "quality": persistida.quality,
                "receivedAt": persistida.received_at,
                "values": persistida.values,
                "units": persistida.units,
                "complements": persistida.complements,
                "analysisStatus": STATUS_ML_CONCLUIDA,
                "analysis": _resposta_analise(resultado),
            }
        except Exception:
            db.rollback()
            logger.exception(
                "Falha na análise ML após persistir captura deviceId=%s observationId=%s",
                payload.deviceId,
                payload.observationId,
            )
            try:
                persistida = db.get(Leitura, reading_id)
                if persistida is not None:
                    persistida.analysis_status = STATUS_ML_FALHA
                    db.commit()
            except SQLAlchemyError:
                db.rollback()
                logger.exception(
                    "Não foi possível persistir estado de falha ML deviceId=%s observationId=%s",
                    payload.deviceId,
                    payload.observationId,
                )
            return {
                "observationId": payload.observationId,
                "deviceId": payload.deviceId,
                "quality": payload.quality,
                "receivedAt": leitura.received_at,
                "values": valores,
                "units": unidades,
                "complements": complementos,
                "analysisStatus": STATUS_ML_FALHA,
                "analysis": {
                    "status": STATUS_ML_FALHA,
                    "executed": False,
                    "message": MENSAGEM_ML_FALHA,
                },
            }


@roteador_dashboard.get("/status")
def status():
    with _sessao() as db:
        dispositivos = db.scalars(select(Dispositivo)).all()
        agora = datetime.now(timezone.utc)
        timeout = obter_configuracoes().telemetry_device_timeout_seconds

        def conectado(dispositivo: Dispositivo) -> bool:
            visto = dispositivo.last_seen_at
            if visto is None:
                return False
            if visto.tzinfo is None:  # SQLite nos testes pode devolver datetime sem fuso.
                visto = visto.replace(tzinfo=timezone.utc)
            return (agora - visto).total_seconds() <= timeout

        return {
            "devices": [
                {
                    "deviceId": dispositivo.device_id,
                    "source": dispositivo.source,
                    "lastSeenAt": dispositivo.last_seen_at,
                    "connected": conectado(dispositivo),
                }
                for dispositivo in dispositivos
            ]
        }


@roteador_dashboard.get("/readings")
def historico(
    limit: int = Query(100, ge=1, le=1000),
    device_id: str | None = None,
):
    with _sessao() as db:
        consulta = select(Leitura).order_by(desc(Leitura.measured_at)).limit(limit)
        if device_id:
            consulta = consulta.where(Leitura.device_id == device_id)
        leituras = db.scalars(consulta).all()
        return [
            {
                "observationId": leitura.observation_id,
                "deviceId": leitura.device_id,
                "measuredAt": leitura.measured_at,
                "receivedAt": leitura.received_at,
                "source": leitura.source,
                "quality": leitura.quality,
                "values": leitura.values,
                "units": leitura.units,
                "complements": leitura.complements,
                "analysisStatus": (
                    STATUS_ML_CONCLUIDA if leitura.anomaly else leitura.analysis_status
                ),
                "analysis": (
                    {
                        "status": STATUS_ML_CONCLUIDA,
                        "executed": True,
                        "isAnomaly": leitura.anomaly.is_anomaly,
                        "classification": "ANOMALIA_ESTATISTICA" if leitura.anomaly.is_anomaly else "NAO_ATIPICA_ESTIMADA",
                        "score": leitura.anomaly.score,
                        "modelVersion": leitura.anomaly.model_version,
                        "analyzedAt": leitura.anomaly.analyzed_at,
                        "variables": leitura.anomaly.variables,
                        "explanation": leitura.anomaly.explanation,
                    }
                    if leitura.anomaly else {
                        "status": leitura.analysis_status,
                        "executed": False,
                        "message": MENSAGEM_ML_FALHA if leitura.analysis_status == STATUS_ML_FALHA else MENSAGEM_ML_PENDENTE,
                    }
                ),
            }
            for leitura in leituras
        ]
