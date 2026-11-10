from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models import EstadoAsistencia, EstadoInscripcion, EstadoLista, EstadoSesion, EstadoTaller, TipoMovimiento
from app.schemas.catalogos import AmbienteSalida, AreaSalida, CicloSalida, SedeSalida
from app.schemas.comun import Esquema, Motivo


class TallerEntrada(BaseModel):
    codigo: str = Field(min_length=2, max_length=20)
    nombre: str = Field(min_length=3, max_length=120)
    descripcion: str | None = Field(default=None, max_length=2000)
    area_id: int
    ciclo_academico_id: int
    docente_id: int
    sede_id: int
    ambiente_id: int | None = None
    cupo_maximo: int = Field(gt=0, le=1000)
    horas_totales: int = Field(gt=0, le=1000)
    umbral_aptitud: int = Field(default=80, ge=50, le=100)
    fecha_inicio: date
    fecha_fin: date
    justificacion_area: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _fechas(self) -> "TallerEntrada":
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha de fin debe ser igual o posterior a la de inicio.")
        return self


class TallerActualizacion(BaseModel):
    nombre: str | None = Field(default=None, min_length=3, max_length=120)
    descripcion: str | None = Field(default=None, max_length=2000)
    docente_id: int | None = None
    ambiente_id: int | None = None
    cupo_maximo: int | None = Field(default=None, gt=0, le=1000)
    horas_totales: int | None = Field(default=None, gt=0, le=1000)
    umbral_aptitud: int | None = Field(default=None, ge=50, le=100)
    fecha_fin: date | None = None
    justificacion_area: str | None = Field(default=None, max_length=500)


class BloqueEntrada(BaseModel):
    dia_semana: int = Field(ge=1, le=7)
    hora_inicio: time
    hora_fin: time
    ambiente_id: int | None = None

    @model_validator(mode="after")
    def _horas(self) -> "BloqueEntrada":
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("La hora final debe ser posterior a la inicial.")
        return self


class HorariosEntrada(BaseModel):
    bloques: list[BloqueEntrada] = Field(min_length=1, max_length=21)
    motivo: str | None = Field(default=None, max_length=255)


class BloqueSalida(Esquema):
    id: int
    dia_semana: int
    hora_inicio: time
    hora_fin: time
    ambiente_id: int | None


class DocenteResumen(Esquema):
    id: int
    nombre_completo: str


class TallerSalida(Esquema):
    id: int
    codigo: str
    nombre: str
    descripcion: str | None
    area: AreaSalida
    ciclo: CicloSalida
    docente: DocenteResumen
    sede: SedeSalida
    ambiente: AmbienteSalida | None
    cupo_maximo: int
    horas_totales: int
    umbral_aptitud: int
    fecha_inicio: date
    fecha_fin: date
    estado: EstadoTaller
    inscripciones_bloqueadas: bool
    motivo_bloqueo: str | None
    horarios: list[BloqueSalida]


class TallerDetalle(TallerSalida):
    inscritos_activos: int
    sesiones_realizadas: int
    sesiones_programadas: int
    inscripciones_cerradas: bool
    en_riesgo: bool


class EstadoTallerEntrada(BaseModel):
    estado: EstadoTaller
    motivo: Motivo


class BloqueoEntrada(BaseModel):
    bloquear: bool
    motivo: str | None = Field(default=None, max_length=255)


class SesionSalida(Esquema):
    id: int
    taller_id: int
    numero_sesion: int
    fecha: date
    hora_inicio: time
    hora_fin: time
    ambiente_id: int | None
    estado: EstadoSesion
    motivo_estado: str | None


class SesionVencida(BaseModel):
    sesion_id: int
    taller_id: int
    taller: str
    numero: int
    fecha: str
    inicio: str
    fin: str


# ---------- Inscripciones ----------

class InscripcionEntrada(BaseModel):
    estudiante_id: int
    motivo: str | None = Field(default=None, max_length=255)


class CambioTallerEntrada(BaseModel):
    taller_destino_id: int
    motivo: Motivo


class EstudianteBreve(Esquema):
    id: int
    codigo_universitario: str
    numero_documento: str
    nombres: str
    apellido_paterno: str
    apellido_materno: str | None


class InscripcionSalida(Esquema):
    id: int
    taller_id: int
    estado: EstadoInscripcion
    fecha_inscripcion: date
    estudiante: EstudianteBreve


class InscripcionConTaller(Esquema):
    id: int
    estado: EstadoInscripcion
    fecha_inscripcion: date
    taller_id: int
    taller_codigo: str
    taller_nombre: str


class MovimientoSalida(Esquema):
    id: int
    tipo: TipoMovimiento
    fecha: date
    motivo: str | None
    taller_relacionado_id: int | None


# ---------- Asistencia ----------

class ResultadoAsistenciaSalida(BaseModel):
    sesiones_correspondientes: int
    validas: int
    faltas: int
    porcentaje: Decimal
    calculable: bool
    en_riesgo: bool | None
    apto: bool | None


class FilaResumenSalida(BaseModel):
    inscripcion_id: int
    estudiante: EstudianteBreve
    resultado: ResultadoAsistenciaSalida


class RegistroAsistencia(BaseModel):
    inscripcion_id: int
    estado: EstadoAsistencia
    observacion: str | None = Field(default=None, max_length=255)


class GuardarAsistencia(BaseModel):
    registros: list[RegistroAsistencia]


class FilaHoja(BaseModel):
    inscripcion_id: int
    estudiante: EstudianteBreve
    estado: EstadoAsistencia | None
    observacion: str | None


class HojaAsistencia(BaseModel):
    sesion: SesionSalida
    taller_id: int
    taller: str
    congelada: bool
    primer_registro: bool
    puede_editar: bool
    motivo_bloqueo: str | None
    filas: list[FilaHoja]


class AutorizacionSalida(Esquema):
    id: int
    sesion_id: int
    docente_id: int
    motivo: str
    otorgada_en: datetime
    vence_en: datetime


# ---------- Aptos ----------

class Exclusion(BaseModel):
    estudiante_id: int
    motivo: Motivo


class GenerarListaEntrada(BaseModel):
    exclusiones: list[Exclusion] = []


class AvanceSalida(BaseModel):
    taller_id: int
    umbral_aptitud: int
    puede_generar: bool
    definitivo: bool
    sesiones_programadas: int
    sesiones_realizadas: int
    motivo: str | None
    filas: list[FilaResumenSalida]


class DetalleListaSalida(Esquema):
    estudiante_id: int
    tipo_documento: str
    numero_documento: str
    codigo_universitario: str
    nombres: str
    apellido_paterno: str
    apellido_materno: str | None
    carrera: str
    sesiones_correspondientes: int
    sesiones_validas: int
    porcentaje: Decimal
    es_apto: bool
    excluido_manual: bool
    motivo_exclusion: str | None


class ListaSalida(Esquema):
    id: int
    taller_id: int
    version: int
    estado: EstadoLista
    umbral_aplicado: int
    sesiones_realizadas: int
    total_inscritos: int
    total_aptos: int
    total_excluidos: int
    generada_en: datetime
    motivo_anulacion: str | None
    anulada_en: datetime | None


class ListaDetalleSalida(ListaSalida):
    detalle: list[DetalleListaSalida]
