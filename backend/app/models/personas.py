"""Estudiantes, docentes, áreas autorizadas y disponibilidad."""
from datetime import date, datetime, time
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
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
from app.models.catalogos import Area, Carrera, TipoDocumento
from app.models.seguridad import Usuario


class EstadoEstudiante(StrEnum):
    ACTIVO = "Activo"
    INACTIVO = "Inactivo"
    EGRESADO = "Egresado"


class Estudiante(ConFechas, Base):
    __tablename__ = "estudiantes"
    __table_args__ = (
        UniqueConstraint("tipo_documento_id", "numero_documento", name="uq_estudiantes_documento"),
        Index("ix_estudiantes_apellidos", "apellido_paterno", "apellido_materno", "nombres"),
        Index("ix_estudiantes_carrera_estado", "carrera_id", "estado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo_documento_id: Mapped[int] = mapped_column(ForeignKey("tipos_documento.id"))
    numero_documento: Mapped[str] = mapped_column(String(20))
    codigo_universitario: Mapped[str] = mapped_column(String(20), unique=True)
    nombres: Mapped[str] = mapped_column(String(100))
    apellido_paterno: Mapped[str] = mapped_column(String(60))
    apellido_materno: Mapped[str | None] = mapped_column(String(60))
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date)
    carrera_id: Mapped[int] = mapped_column(ForeignKey("carreras.id"))
    ciclo_actual: Mapped[int | None] = mapped_column(SmallInteger)
    email: Mapped[str | None] = mapped_column(String(120))
    telefono: Mapped[str | None] = mapped_column(String(20))
    foto_ruta: Mapped[str | None] = mapped_column(String(255))
    estado: Mapped[EstadoEstudiante] = mapped_column(
        enum_columna(EstadoEstudiante, "estado_estudiante"), default=EstadoEstudiante.ACTIVO
    )

    tipo_documento: Mapped[TipoDocumento] = relationship(lazy="joined")
    carrera: Mapped[Carrera] = relationship(lazy="joined")

    @property
    def apellidos(self) -> str:
        return " ".join(p for p in (self.apellido_paterno, self.apellido_materno) if p)


class Docente(ConFechas, Base):
    __tablename__ = "docentes"
    __table_args__ = (
        UniqueConstraint("tipo_documento_id", "numero_documento", name="uq_docentes_documento"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), unique=True)
    tipo_documento_id: Mapped[int] = mapped_column(ForeignKey("tipos_documento.id"))
    numero_documento: Mapped[str] = mapped_column(String(20))
    nombres: Mapped[str] = mapped_column(String(100))
    apellido_paterno: Mapped[str] = mapped_column(String(60))
    apellido_materno: Mapped[str | None] = mapped_column(String(60))
    email: Mapped[str] = mapped_column(String(120))
    telefono: Mapped[str | None] = mapped_column(String(20))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    usuario: Mapped[Usuario] = relationship(lazy="joined")
    tipo_documento: Mapped[TipoDocumento] = relationship(lazy="joined")
    areas: Mapped[list[Area]] = relationship(secondary="docente_areas", lazy="selectin")
    disponibilidad: Mapped[list["DisponibilidadDocente"]] = relationship(
        lazy="selectin", order_by="DisponibilidadDocente.dia_semana"
    )

    @property
    def nombre_completo(self) -> str:
        return " ".join(p for p in (self.nombres, self.apellido_paterno, self.apellido_materno) if p)


class DocenteArea(Base):
    __tablename__ = "docente_areas"

    docente_id: Mapped[int] = mapped_column(ForeignKey("docentes.id"), primary_key=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"), primary_key=True)


class DisponibilidadDocente(ConFechas, Base):
    __tablename__ = "disponibilidad_docente"
    __table_args__ = (
        CheckConstraint("hora_fin > hora_inicio", name="horas"),
        CheckConstraint("dia_semana BETWEEN 1 AND 7", name="dia"),
        Index("ix_disponibilidad_docente_dia", "docente_id", "dia_semana"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    docente_id: Mapped[int] = mapped_column(ForeignKey("docentes.id"))
    dia_semana: Mapped[int] = mapped_column(SmallInteger)  # 1 = lunes … 7 = domingo
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)
    vigente_desde: Mapped[date | None] = mapped_column(Date)
    vigente_hasta: Mapped[date | None] = mapped_column(Date)


class ExcepcionAreaDocente(Base):
    __tablename__ = "excepciones_area_docente"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    docente_id: Mapped[int] = mapped_column(ForeignKey("docentes.id"))
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"))
    taller_id: Mapped[int] = mapped_column(ForeignKey("talleres.id"))
    justificacion: Mapped[str] = mapped_column(Text)
    autorizado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
