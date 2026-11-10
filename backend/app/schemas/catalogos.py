from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.models import EstadoRegistro
from app.schemas.comun import Esquema, TextoCorto


class SedeEntrada(BaseModel):
    nombre: TextoCorto
    direccion: str = Field(min_length=3, max_length=200)
    estado: EstadoRegistro = EstadoRegistro.ACTIVO


class SedeSalida(Esquema):
    id: int
    nombre: str
    direccion: str
    estado: EstadoRegistro


class AmbienteEntrada(BaseModel):
    sede_id: int
    codigo: str = Field(min_length=1, max_length=20)
    nombre: TextoCorto
    capacidad: int | None = Field(default=None, gt=0, le=2000)
    estado: EstadoRegistro = EstadoRegistro.ACTIVO


class AmbienteSalida(Esquema):
    id: int
    sede_id: int
    codigo: str
    nombre: str
    capacidad: int | None
    estado: EstadoRegistro
    sede: SedeSalida


class AreaEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    activo: bool = True


class AreaSalida(Esquema):
    id: int
    nombre: str
    activo: bool


class FacultadEntrada(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=2, max_length=150)
    activo: bool = True


class FacultadSalida(Esquema):
    id: int
    codigo: str
    nombre: str
    activo: bool


class CarreraEntrada(BaseModel):
    facultad_id: int
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=2, max_length=150)
    activo: bool = True


class CarreraSalida(Esquema):
    id: int
    facultad_id: int
    codigo: str
    nombre: str
    activo: bool
    facultad: FacultadSalida


class CicloEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=30)
    fecha_inicio: date
    fecha_fin: date

    @model_validator(mode="after")
    def _fechas(self) -> "CicloEntrada":
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("La fecha de fin debe ser posterior a la de inicio.")
        return self


class CicloSalida(Esquema):
    id: int
    nombre: str
    fecha_inicio: date
    fecha_fin: date
    activo: bool


class TipoDocumentoSalida(Esquema):
    id: int
    codigo: str
    nombre: str
    longitud_min: int
    longitud_max: int
    solo_digitos: bool
    activo: bool
