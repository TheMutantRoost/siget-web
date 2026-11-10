"""Inscripciones, movimientos, asistencia, autorizaciones y listas de aptos."""
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ConFechas, enum_columna
from app.models.personas import Estudiante
from app.models.talleres import Sesion, Taller


class EstadoInscripcion(StrEnum):
    ACTIVO = "Activo"
    RETIRADO = "Retirado"


class TipoMovimiento(StrEnum):
    ALTA = "alta"
    RETIRO = "retiro"
    REACTIVACION = "reactivacion"
    CAMBIO_SALIDA = "cambio_salida"
    CAMBIO_ENTRADA = "cambio_entrada"


class EstadoAsistencia(StrEnum):
    PRESENTE = "P"
    AUSENTE = "A"
    JUSTIFICADO = "J"


class EstadoLista(StrEnum):
    VIGENTE = "Vigente"
    ANULADA = "Anulada"


class Inscripcion(ConFechas, Base):
    __tablename__ = "inscripciones"
    __table_args__ = (
        UniqueConstraint("taller_id", "estudiante_id", name="uq_inscripciones_taller_estudiante"),
        Index("ix_inscripciones_estudiante_estado", "estudiante_id", "estado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    taller_id: Mapped[int] = mapped_column(ForeignKey("talleres.id"))
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("estudiantes.id"))
    estado: Mapped[EstadoInscripcion] = mapped_column(
        enum_columna(EstadoInscripcion, "estado_inscripcion"), default=EstadoInscripcion.ACTIVO
    )
    fecha_inscripcion: Mapped[date] = mapped_column(Date)

    estudiante: Mapped[Estudiante] = relationship(lazy="joined")
    taller: Mapped[Taller] = relationship(lazy="joined")


class MovimientoInscripcion(Base):
    __tablename__ = "movimientos_inscripcion"
    __table_args__ = (Index("ix_movimientos_inscripcion_fecha", "inscripcion_id", "fecha"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inscripcion_id: Mapped[int] = mapped_column(ForeignKey("inscripciones.id"))
    tipo: Mapped[TipoMovimiento] = mapped_column(enum_columna(TipoMovimiento, "tipo_movimiento"))
    fecha: Mapped[date] = mapped_column(Date)
    motivo: Mapped[str | None] = mapped_column(String(255))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    taller_relacionado_id: Mapped[int | None] = mapped_column(ForeignKey("talleres.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Asistencia(ConFechas, Base):
    __tablename__ = "asistencia"
    __table_args__ = (
        UniqueConstraint("inscripcion_id", "sesion_id", name="uq_asistencia_inscripcion_sesion"),
        CheckConstraint(
            "estado <> 'J' OR (observacion IS NOT NULL AND CHAR_LENGTH(TRIM(observacion)) > 0)",
            name="justificado_observacion",
        ),
        Index("ix_asistencia_sesion", "sesion_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inscripcion_id: Mapped[int] = mapped_column(ForeignKey("inscripciones.id"))
    sesion_id: Mapped[int] = mapped_column(ForeignKey("sesiones.id"))
    estado: Mapped[EstadoAsistencia] = mapped_column(
        enum_columna(EstadoAsistencia, "estado_asistencia")
    )
    observacion: Mapped[str | None] = mapped_column(String(255))
    registrado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    actualizado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))


class AutorizacionEdicion(Base):
    __tablename__ = "autorizaciones_edicion"
    __table_args__ = (Index("ix_autorizaciones_sesion_docente", "sesion_id", "docente_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sesion_id: Mapped[int] = mapped_column(ForeignKey("sesiones.id"))
    docente_id: Mapped[int] = mapped_column(ForeignKey("docentes.id"))
    otorgada_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    motivo: Mapped[str] = mapped_column(String(255))
    otorgada_en: Mapped[datetime] = mapped_column(DateTime)
    vence_en: Mapped[datetime] = mapped_column(DateTime)
    consumida_en: Mapped[datetime | None] = mapped_column(DateTime)
    revocada_en: Mapped[datetime | None] = mapped_column(DateTime)
    revocada_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    sesion: Mapped[Sesion] = relationship(lazy="joined")


class ListaAptos(Base):
    __tablename__ = "listas_aptos"
    __table_args__ = (UniqueConstraint("taller_id", "version", name="uq_listas_aptos_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    taller_id: Mapped[int] = mapped_column(ForeignKey("talleres.id"))
    version: Mapped[int] = mapped_column(SmallInteger)
    estado: Mapped[EstadoLista] = mapped_column(
        enum_columna(EstadoLista, "estado_lista"), default=EstadoLista.VIGENTE
    )
    umbral_aplicado: Mapped[int] = mapped_column(SmallInteger)
    sesiones_realizadas: Mapped[int] = mapped_column(SmallInteger)
    total_inscritos: Mapped[int] = mapped_column(SmallInteger)
    total_aptos: Mapped[int] = mapped_column(SmallInteger)
    total_excluidos: Mapped[int] = mapped_column(SmallInteger)
    generada_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    generada_en: Mapped[datetime] = mapped_column(DateTime)
    motivo_anulacion: Mapped[str | None] = mapped_column(String(255))
    anulada_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    anulada_en: Mapped[datetime | None] = mapped_column(DateTime)
    # Una sola lista vigente por taller, garantizado por la base.
    vigente_unica: Mapped[int | None] = mapped_column(
        Integer, Computed("IF(estado = 'Vigente', taller_id, NULL)", persisted=True), unique=True
    )

    taller: Mapped[Taller] = relationship(lazy="joined")
    detalle: Mapped[list["ListaAptosDetalle"]] = relationship(
        lazy="selectin",
        order_by="(ListaAptosDetalle.apellido_paterno, ListaAptosDetalle.apellido_materno, ListaAptosDetalle.nombres)",
    )


class ListaAptosDetalle(Base):
    """Copia inmutable: no cambia aunque luego cambien estudiantes, asistencias o el umbral."""

    __tablename__ = "lista_aptos_detalle"
    __table_args__ = (
        UniqueConstraint("lista_id", "estudiante_id", name="uq_lista_aptos_detalle_estudiante"),
        CheckConstraint(
            "excluido_manual = 0 OR motivo_exclusion IS NOT NULL", name="exclusion_motivo"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lista_id: Mapped[int] = mapped_column(ForeignKey("listas_aptos.id"))
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("estudiantes.id"))
    tipo_documento: Mapped[str] = mapped_column(String(40))
    numero_documento: Mapped[str] = mapped_column(String(20))
    codigo_universitario: Mapped[str] = mapped_column(String(20))
    nombres: Mapped[str] = mapped_column(String(100))
    apellido_paterno: Mapped[str] = mapped_column(String(60))
    apellido_materno: Mapped[str | None] = mapped_column(String(60))
    carrera: Mapped[str] = mapped_column(String(150))
    sesiones_correspondientes: Mapped[int] = mapped_column(SmallInteger)
    sesiones_validas: Mapped[int] = mapped_column(SmallInteger)
    porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    es_apto: Mapped[bool] = mapped_column(Boolean)
    excluido_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo_exclusion: Mapped[str | None] = mapped_column(String(255))
