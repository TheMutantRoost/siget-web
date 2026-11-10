from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.comun import Esquema


class LoginEntrada(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class CambioPasswordEntrada(BaseModel):
    actual: str = Field(min_length=1, max_length=128)
    nueva: str = Field(min_length=1, max_length=128)


class UsuarioSesion(Esquema):
    id: int
    username: str
    nombre_completo: str
    rol: str
    debe_cambiar_password: bool
    docente_id: int | None = None
    ultimo_acceso: datetime | None


class SesionSalida(BaseModel):
    usuario: UsuarioSesion
    csrf: str
