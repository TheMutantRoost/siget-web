"""Talleres, bloques horarios, historial y sesiones."""
from datetime import date, datetime, time
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ConFechas, enum_columna
from app.models.catalogos import Ambiente, Area, CicloAcademico, Sede
from app.models.personas import Docente


class EstadoTaller(StrEnum):
    ACTIVO = "Activo"
    SUSPENDIDO = "Suspendido"
    FINALIZADO = "Finalizado"


class EstadoSesion(StrEnum):
    PROGRAMADA = "Programada"
    REALIZADA = "Realizada"
    CANCELADA = "Cancelada"
    REPROGRAMADA = "Reprogramada"


class Taller(ConFechas, Base):
    __tablename__ = "talleres"
    __table_args__ = (
        CheckConstraint("umbral_aptitud BETWEEN 50 AND 100", name="umbral"),
        CheckConstraint("cupo_maximo > 0", name="cupo"),
        CheckConstraint("fecha_fin >= fecha_inicio", name="fechas"),
        CheckConstraint(
            "inscripciones_bloqueadas = 0 OR motivo_bloqueo IS NOT NULL", name="bloqueo_motivo"
        ),
        # El ambiente debe pertenecer a la sede del taller (garantizado por la base).
        ForeignKeyConstraint(
            ["ambiente_id", "sede_id"],
            ["ambientes.id", "ambientes.sede_id"],
            name="fk_talleres_ambiente_sede",
        ),
        Index("ix_talleres_docente_estado", "docente_id", "estado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(Text)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"))
    ciclo_academico_id: Mapped[int] = mapped_column(ForeignKey("ciclos_academicos.id"), index=True)
    docente_id: Mapped[int] = mapped_column(ForeignKey("docentes.id"))
    sede_id: Mapped[int] = mapped_column(ForeignKey("sedes.id"), index=True)
    ambiente_id: Mapped[int | None] = mapped_column(Integer)
    cupo_maximo: Mapped[int] = mapped_column(SmallInteger)
    horas_totales: Mapped[int] = mapped_column(SmallInteger)
    umbral_aptitud: Mapped[int] = mapped_column(SmallInteger, default=80, server_default="80")
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    estado: Mapped[EstadoTaller] = mapped_column(
        enum_columna(EstadoTaller, "estado_taller"), default=EstadoTaller.ACTIVO
    )
    inscripciones_bloqueadas: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo_bloqueo: Mapped[str | None] = mapped_column(String(255))
    bloqueado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    bloqueado_en: Mapped[datetime | None] = mapped_column(DateTime)

    area: Mapped[Area] = relationship(lazy="joined")
    ciclo: Mapped[CicloAcademico] = relationship(lazy="joined")
    docente: Mapped[Docente] = relationship(lazy="joined")
    sede: Mapped[Sede] = relationship(lazy="joined")
    ambiente: Mapped[Ambiente | None] = relationship(
        primaryjoin="Taller.ambiente_id == Ambiente.id",
        foreign_keys="Taller.ambiente_id",
        lazy="joined",
        viewonly=True,
    )
    horarios: Mapped[list["HorarioTaller"]] = relationship(
        lazy="selectin",
        primaryjoin="and_(HorarioTaller.taller_id == Taller.id, HorarioTaller.activo == True)",
        order_by="(HorarioTaller.dia_semana, HorarioTaller.hora_inicio)",
        viewonly=True,
    )


class HorarioTaller(ConFechas, Base):
    """Un bloque semanal por fila. Nunca se guardan horarios en texto ni JSON."""

    __tablename__ = "horarios_taller"
    __table_args__ = (
        CheckConstraint("hora_fin > hora_inicio", name="horas"),
        CheckConstraint("dia_semana BETWEEN 1 AND 7", name="dia"),
        Index("ix_horarios_taller_taller_dia", "taller_id", "dia_semana"),
        Index("ix_horarios_taller_ambiente", "ambiente_id", "dia_semana", "hora_inicio"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    taller_id: Mapped[int] = mapped_column(ForeignKey("talleres.id"))
    dia_semana: Mapped[int] = mapped_column(SmallInteger)
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)
    ambiente_id: Mapped[int | None] = mapped_column(ForeignKey("ambientes.id"))
    vigente_desde: Mapped[date | None] = mapped_column(Date)
    vigente_hasta: Mapped[date | None] = mapped_column(Date)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    ambiente: Mapped[Ambiente | None] = relationship(lazy="joined")


class HistorialHorario(Base):
    __tablename__ = "historial_horarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    taller_id: Mapped[int] = mapped_column(ForeignKey("talleres.id"), index=True)
    horario_id: Mapped[int] = mapped_column(ForeignKey("horarios_taller.id"))
    accion: Mapped[str] = mapped_column(String(12))  # alta, baja
    dia_semana: Mapped[int] = mapped_column(SmallInteger)
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)
    ambiente_id: Mapped[int | None] = mapped_column(ForeignKey("ambientes.id"))
    motivo: Mapped[str | None] = mapped_column(String(255))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Sesion(ConFechas, Base):
    __tablename__ = "sesiones"
    __table_args__ = (
        UniqueConstraint("taller_id", "numero_sesion", name="uq_sesiones_taller_numero"),
        CheckConstraint("hora_fin > hora_inicio", name="horas"),
        Index("ix_sesiones_taller_estado_fecha", "taller_id", "estado", "fecha"),
        Index("ix_sesiones_fecha_hora", "fecha", "hora_inicio"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    taller_id: Mapped[int] = mapped_column(ForeignKey("talleres.id"))
    numero_sesion: Mapped[int] = mapped_column(SmallInteger)
    horario_id: Mapped[int | None] = mapped_column(ForeignKey("horarios_taller.id"))
    sesion_original_id: Mapped[int | None] = mapped_column(
        ForeignKey("sesiones.id"), unique=True
    )
    fecha: Mapped[date] = mapped_column(Date)
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)
    ambiente_id: Mapped[int | None] = mapped_column(ForeignKey("ambientes.id"))
    estado: Mapped[EstadoSesion] = mapped_column(
        enum_columna(EstadoSesion, "estado_sesion"), default=EstadoSesion.PROGRAMADA
    )
    motivo_estado: Mapped[str | None] = mapped_column(String(255))
    cambiado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    cambiado_en: Mapped[datetime | None] = mapped_column(DateTime)

    taller: Mapped[Taller] = relationship(lazy="joined")
