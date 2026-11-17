from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.telemetria.banco import BaseTelemetria

JSON_COMPAT = JSON().with_variant(JSONB, "postgresql")


class TipoSemente(BaseTelemetria):
    __tablename__ = "tipos_semente"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    compatibilidades: Mapped[list["Compatibilidade"]] = relationship(back_populates="semente")


class TipoSolo(BaseTelemetria):
    __tablename__ = "tipos_solo"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    compatibilidades: Mapped[list["Compatibilidade"]] = relationship(back_populates="solo")


class Compatibilidade(BaseTelemetria):
    __tablename__ = "compatibilidades"
    __table_args__ = (
        UniqueConstraint("semente_id", "solo_id", name="uq_compatibilidades_semente_solo"),
        CheckConstraint(
            "resultado IN ('COMPATIVEL', 'INCOMPATIVEL', 'DADOS_INSUFICIENTES')",
            name="ck_compatibilidades_resultado",
        ),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    semente_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tipos_semente.id", ondelete="RESTRICT"), nullable=False
    )
    solo_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tipos_solo.id", ondelete="RESTRICT"), nullable=False
    )
    resultado: Mapped[str] = mapped_column(String(30), nullable=False)
    criterios: Mapped[list[str]] = mapped_column(JSON_COMPAT, nullable=False)
    justificativa: Mapped[str] = mapped_column(String(2000), nullable=False)
    referencia_fonte: Mapped[str] = mapped_column(String(1000), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    semente: Mapped[TipoSemente] = relationship(back_populates="compatibilidades")
    solo: Mapped[TipoSolo] = relationship(back_populates="compatibilidades")


class AnaliseCompatibilidade(BaseTelemetria):
    __tablename__ = "analises_compatibilidade"
    __table_args__ = (
        CheckConstraint(
            "resultado IN ('COMPATIVEL', 'INCOMPATIVEL', 'DADOS_INSUFICIENTES')",
            name="ck_analises_compatibilidade_resultado",
        ),
        CheckConstraint(
            "estado_explicacao IN ('PENDENTE', 'NAO_CONFIGURADO', 'SEM_CRITERIOS', 'CONCLUIDA', 'FALHA')",
            name="ck_analises_compatibilidade_estado_explicacao",
        ),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    semente_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tipos_semente.id", ondelete="RESTRICT"), nullable=False
    )
    solo_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tipos_solo.id", ondelete="RESTRICT"), nullable=False
    )
    compatibilidade_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("compatibilidades.id", ondelete="SET NULL")
    )
    semente_codigo: Mapped[str] = mapped_column(String(40), nullable=False)
    semente_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    solo_codigo: Mapped[str] = mapped_column(String(40), nullable=False)
    solo_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    resultado: Mapped[str] = mapped_column(String(30), nullable=False)
    criterios: Mapped[list[str]] = mapped_column(JSON_COMPAT, nullable=False)
    justificativa: Mapped[str | None] = mapped_column(String(2000))
    referencia_fonte: Mapped[str | None] = mapped_column(String(1000))
    explicacao_gemini: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado_explicacao: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDENTE", server_default="NAO_CONFIGURADO")
    codigo_erro_explicacao: Mapped[str | None] = mapped_column(String(60), nullable=True)
    analisado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    compatibilidade: Mapped[Compatibilidade | None] = relationship()
    semente: Mapped[TipoSemente] = relationship(foreign_keys=[semente_id])
    solo: Mapped[TipoSolo] = relationship(foreign_keys=[solo_id])
