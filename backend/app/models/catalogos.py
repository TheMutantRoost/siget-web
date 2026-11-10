"""Catálogos académicos e infraestructura."""
from datetime import date
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ConFechas, enum_columna


class EstadoRegistro(StrEnum):
    ACTIVO = "Activo"
    INACTIVO = "Inactivo"


class Facultad(ConFechas, Base):
    __tablename__ = "facultades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(150))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Carrera(ConFechas, Base):
    __tablename__ = "carreras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facultad_id: Mapped[int] = mapped_column(ForeignKey("facultades.id"))
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(150))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    facultad: Mapped[Facultad] = relationship(lazy="joined")


class CicloAcademico(ConFechas, Base):
    __tablename__ = "ciclos_academicos"
    __table_args__ = (CheckConstraint("fecha_fin > fecha_inicio", name="fechas"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(30), unique=True)
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    activo: Mapped[bool] = mapped_column(Boolean, default=False)
    # MySQL no tiene índices parciales: NULL se repite, 1 solo puede existir una vez.
    activo_unico: Mapped[int | None] = mapped_column(
        SmallInteger, Computed("IF(activo = 1, 1, NULL)", persisted=True), unique=True
    )


class TipoDocumento(Base):
    __tablename__ = "tipos_documento"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True)
    nombre: Mapped[str] = mapped_column(String(40))
    longitud_min: Mapped[int] = mapped_column(SmallInteger)
    longitud_max: Mapped[int] = mapped_column(SmallInteger)
    solo_digitos: Mapped[bool] = mapped_column(Boolean)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Area(ConFechas, Base):
    __tablename__ = "areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Sede(ConFechas, Base):
    __tablename__ = "sedes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    direccion: Mapped[str] = mapped_column(String(200))
    estado: Mapped[EstadoRegistro] = mapped_column(
        enum_columna(EstadoRegistro, "estado_sede"), default=EstadoRegistro.ACTIVO
    )


class Ambiente(ConFechas, Base):
    __tablename__ = "ambientes"
    __table_args__ = (
        UniqueConstraint("sede_id", "codigo", name="uq_ambientes_sede_codigo"),
        # Permite la FK compuesta (ambiente_id, sede_id) desde talleres.
        UniqueConstraint("id", "sede_id", name="uq_ambientes_id_sede"),
        CheckConstraint("capacidad IS NULL OR capacidad > 0", name="capacidad"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sede_id: Mapped[int] = mapped_column(ForeignKey("sedes.id"))
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(100))
    capacidad: Mapped[int | None] = mapped_column(SmallInteger)
    estado: Mapped[EstadoRegistro] = mapped_column(
        enum_columna(EstadoRegistro, "estado_ambiente"), default=EstadoRegistro.ACTIVO
    )

    sede: Mapped[Sede] = relationship(lazy="joined")
