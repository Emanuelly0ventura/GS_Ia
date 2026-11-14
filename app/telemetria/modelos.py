from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.telemetria.banco import BaseTelemetria


JSON_COMPAT = JSON().with_variant(JSONB, "postgresql")
ID_COMPAT = BigInteger().with_variant(Integer, "sqlite")


class Dispositivo(BaseTelemetria):
    __tablename__ = "iot_devices"

    id: Mapped[int] = mapped_column(ID_COMPAT, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(120), unique=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    readings: Mapped[list["Leitura"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )


class Leitura(BaseTelemetria):
    __tablename__ = "iot_readings"
    __table_args__ = (
        UniqueConstraint("device_id", "observation_id", name="uq_iot_reading_observation"),
        CheckConstraint("quality = 'VALID'", name="ck_iot_readings_quality"),
        CheckConstraint(
            "analysis_status IN ('PENDENTE', 'CONCLUIDA', 'FALHA')",
            name="ck_iot_readings_analysis_status",
        ),
    )

    id: Mapped[int] = mapped_column(ID_COMPAT, primary_key=True)
    device_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("iot_devices.device_id", ondelete="CASCADE"), index=True
    )
    observation_id: Mapped[str] = mapped_column(String(120))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source: Mapped[str] = mapped_column(String(80))
    quality: Mapped[str] = mapped_column(String(30))
    analysis_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDENTE", server_default="PENDENTE"
    )
    values: Mapped[dict] = mapped_column("sensor_values", JSON_COMPAT, nullable=False)
    units: Mapped[dict] = mapped_column(JSON_COMPAT, nullable=False)
    complements: Mapped[dict] = mapped_column(
        JSON_COMPAT, default=dict, server_default=text("'{}'"), nullable=False
    )
    device: Mapped[Dispositivo] = relationship(back_populates="readings")
    anomaly: Mapped["AnaliseAnomalia | None"] = relationship(
        back_populates="reading", uselist=False, cascade="all, delete-orphan"
    )


class AnaliseAnomalia(BaseTelemetria):
    __tablename__ = "iot_anomaly_analyses"
    __table_args__ = (
        CheckConstraint(
            "jsonb_array_length(variables) = 4",
            name="ck_iot_anomaly_variables_four",
        ).ddl_if(dialect="postgresql"),
    )

    id: Mapped[int] = mapped_column(ID_COMPAT, primary_key=True)
    reading_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("iot_readings.id", ondelete="CASCADE"),
        unique=True,
    )
    model_version: Mapped[str] = mapped_column(String(80))
    is_anomaly: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[float] = mapped_column(Float)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    variables: Mapped[list] = mapped_column(JSON_COMPAT, nullable=False)
    explanation: Mapped[str] = mapped_column(String(500))
    reading: Mapped[Leitura] = relationship(back_populates="anomaly")
