from datetime import datetime, timezone
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.inteligencia_artificial.aprendizado_maquina.caracteristicas import VARIAVEIS_MODELO
from app.inteligencia_artificial.aprendizado_maquina.detector_anomalias import DetectorAnomalias
from app.inteligencia_artificial.aprendizado_maquina.esquemas import LeituraParaModelo
from app.nucleo.configuracoes import obter_configuracoes
from app.telemetria.banco import obter_fabrica_sessoes
from app.telemetria.esquemas import LeituraIoT
from app.telemetria.modelos import AnaliseAnomalia, Dispositivo, Leitura

roteador_telemetria = APIRouter(prefix="/api/v1/iot", tags=["Demonstração IoT"])
roteador_dashboard = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard IoT"])


@lru_cache(maxsize=4)
def carregar_detector(caminho: str) -> DetectorAnomalias:
    return DetectorAnomalias.carregar(caminho)


def _sessao():
    fabrica = obter_fabrica_sessoes()
    if fabrica is None:
        raise HTTPException(status_code=503, detail="Banco de telemetria não configurado.")
    return fabrica()


def _leitura_modelo(payload: LeituraIoT) -> LeituraParaModelo:
    return LeituraParaModelo(
        idObservacao=payload.observationId,
        idDispositivo=payload.deviceId,
        registradoEm=payload.measuredAt,
        valores={nome: payload.values[nome] for nome in VARIAVEIS_MODELO},
        unidades={nome: payload.units[nome] for nome in VARIAVEIS_MODELO},
        qualidade="VALIDA",
        origem=payload.source,
    )


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
    summary="Recebe um conjunto coerente agrupado pelo Node-RED",
)
def receber(payload: LeituraIoT):
    configuracoes = obter_configuracoes()
    try:
        detector = carregar_detector(str(configuracoes.ml_caminho_modelo))
    except (OSError, ValueError, KeyError) as erro:
        raise HTTPException(
            status_code=503,
            detail="Modelo v2 de três variáveis ausente ou incompatível; treine novamente.",
        ) from erro
    if detector.versao_modelo != configuracoes.ml_versao_modelo:
        raise HTTPException(status_code=503, detail="Versão do modelo divergente da configuração.")

    try:
        resultado = detector.predizer(_leitura_modelo(payload))
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
                values=payload.values,
                units=payload.units,
                complements=payload.complements,
            )
            db.add(leitura)
            db.flush()

            db.add(AnaliseAnomalia(
                reading_id=leitura.id,
                model_version=resultado.versao_modelo,
                is_anomaly=resultado.classificada_como_anomalia,
                score=resultado.pontuacao_anomalia,
                analyzed_at=resultado.data_analise,
                variables=resultado.variaveis_utilizadas,
                explanation=resultado.justificativa,
            ))
            db.commit()
            return {
                "observationId": leitura.observation_id,
                "deviceId": leitura.device_id,
                "quality": leitura.quality,
                "receivedAt": leitura.received_at,
                "analysis": resultado.model_dump(mode="json", by_alias=True),
            }
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
        except Exception:
            db.rollback()
            raise



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
                "analysis": (
                    {
                        "isAnomaly": leitura.anomaly.is_anomaly,
                        "score": leitura.anomaly.score,
                        "modelVersion": leitura.anomaly.model_version,
                        "analyzedAt": leitura.anomaly.analyzed_at,
                        "variables": leitura.anomaly.variables,
                        "explanation": leitura.anomaly.explanation,
                    }
                    if leitura.anomaly else None
                ),
            }
            for leitura in leituras
        ]
