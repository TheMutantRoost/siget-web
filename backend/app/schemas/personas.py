from datetime import date, datetime, time

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models import EstadoEstudiante
from app.schemas.catalogos import AreaSalida, CarreraSalida, TipoDocumentoSalida
from app.schemas.comun import Esquema, TextoCorto

Apellido = Field(min_length=1, max_length=60)


class EstudianteEntrada(BaseModel):
    tipo_documento_id: int
    numero_documento: str = Field(min_length=1, max_length=20)
    codigo_universitario: str = Field(min_length=1, max_length=20)
    nombres: TextoCorto
    apellido_paterno: str = Apellido
    apellido_materno: str | None = Field(default=None, max_length=60)
    fecha_nacimiento: date | None = None
    carrera_id: int
    ciclo_actual: int | None = Field(default=None, ge=1, le=14)
    email: EmailStr | None = None
    telefono: str | None = Field(default=None, max_length=20, pattern=r"^[0-9+ ()-]*$")
    estado: EstadoEstudiante = EstadoEstudiante.ACTIVO


class EstudianteSalida(Esquema):
    id: int
    tipo_documento_id: int
    numero_documento: str
    codigo_universitario: str
    nombres: str
    apellido_paterno: str
    apellido_materno: str | None
    fecha_nacimiento: date | None
    carrera_id: int
    ciclo_actual: int | None
    email: str | None
    telefono: str | None
    estado: EstadoEstudiante
    tipo_documento: TipoDocumentoSalida
    carrera: CarreraSalida


class DocenteEntrada(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")
    email: EmailStr
    tipo_documento_id: int
    numero_documento: str = Field(min_length=1, max_length=20)
    nombres: TextoCorto
    apellido_paterno: str = Apellido
    apellido_materno: str | None = Field(default=None, max_length=60)
    telefono: str | None = Field(default=None, max_length=20, pattern=r"^[0-9+ ()-]*$")
    area_ids: list[int] = Field(min_length=1)


class DocenteActualizacion(BaseModel):
    nombres: str | None = Field(default=None, min_length=1, max_length=100)
    apellido_paterno: str | None = Field(default=None, min_length=1, max_length=60)
    apellido_materno: str | None = Field(default=None, max_length=60)
    telefono: str | None = Field(default=None, max_length=20)
    area_ids: list[int] | None = Field(default=None, min_length=1)
    activo: bool | None = None


class BloqueDisponibilidad(BaseModel):
    dia_semana: int = Field(ge=1, le=7)
    hora_inicio: time
    hora_fin: time
    vigente_desde: date | None = None
    vigente_hasta: date | None = None

    @model_validator(mode="after")
    def _horas(self) -> "BloqueDisponibilidad":
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("La hora final debe ser posterior a la inicial.")
        return self


class DisponibilidadSalida(Esquema):
    id: int
    dia_semana: int
    hora_inicio: time
    hora_fin: time
    vigente_desde: date | None
    vigente_hasta: date | None


class DocenteSalida(Esquema):
    id: int
    usuario_id: int
    tipo_documento_id: int
    numero_documento: str
    nombres: str
    apellido_paterno: str
    apellido_materno: str | None
    nombre_completo: str
    email: str
    telefono: str | None
    activo: bool
    areas: list[AreaSalida]
    disponibilidad: list[DisponibilidadSalida]


class DocenteCreado(BaseModel):
    docente: DocenteSalida
    username: str
    password_temporal: str


class UsuarioEntrada(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")
    email: EmailStr
    nombres: TextoCorto
    apellido_paterno: str = Apellido
    apellido_materno: str | None = Field(default=None, max_length=60)
    rol: str = Field(pattern=r"^(Administrador|Operador)$")


class UsuarioSalida(Esquema):
    id: int
    username: str
    email: str
    nombres: str
    apellido_paterno: str
    apellido_materno: str | None
    activo: bool
    debe_cambiar_password: bool
    ultimo_acceso: datetime | None
    intentos_fallidos: int
    bloqueado_hasta: datetime | None
    rol_nombre: str


class PasswordTemporal(BaseModel):
    username: str
    password_temporal: str
