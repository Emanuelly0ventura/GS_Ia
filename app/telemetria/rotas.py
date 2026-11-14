from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.nucleo.configuracoes import obter_configuracoes
from app.telemetria.banco import obter_fabrica_sessoes
from app.telemetria.conversoes import converter_temperatura_dht22_em_umidade_solo
from app.telemetria.esquemas import LeituraIoT, MetadadosUmidadeSolo, UNIDADES_CANONICAS
from app.telemetria.modelos import AnaliseAnomalia, Dispositivo, Leitura

roteador_telemetria = APIRouter(prefix="/api/v1/iot", tags=["Demonstração IoT"])
roteador_dashboard = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard IoT"])


STATUS_ML_PENDENTE = "PENDENTE_ADEQUACAO_CONTRATO_ML"
MENSAGEM_ML_PENDENTE = (
    "A captura foi persistida. A análise ML está pendente de adequação do Isolation Forest "
    "ao contrato de quatro indicadores."
)

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
    summary="Recebe e persiste uma captura IoT de quatro indicadores",
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
                values=valores,
                units=unidades,
                complements=complementos,
            )
            db.add(leitura)
            db.commit()
            return {
                "observationId": leitura.observation_id,
                "deviceId": leitura.device_id,
                "quality": leitura.quality,
                "receivedAt": leitura.received_at,
                "values": valores,
                "units": unidades,
                "complements": complementos,
                "analysisStatus": STATUS_ML_PENDENTE,
                "analysis": {
                    "status": STATUS_ML_PENDENTE,
                    "executed": False,
                    "message": MENSAGEM_ML_PENDENTE,
                },
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
                "analysisStatus": (
                    "CONCLUIDA" if leitura.anomaly else STATUS_ML_PENDENTE
                ),
                "analysis": (
                    {
                        "status": "CONCLUIDA",
                        "executed": True,
                        "isAnomaly": leitura.anomaly.is_anomaly,
                        "score": leitura.anomaly.score,
                        "modelVersion": leitura.anomaly.model_version,
                        "analyzedAt": leitura.anomaly.analyzed_at,
                        "variables": leitura.anomaly.variables,
                        "explanation": leitura.anomaly.explanation,
                    }
                    if leitura.anomaly else {
                        "status": STATUS_ML_PENDENTE,
                        "executed": False,
                        "message": MENSAGEM_ML_PENDENTE,
                    }
                ),
            }
            for leitura in leituras
        ]
