from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, StringConstraints

T = TypeVar("T")

Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
TextoCorto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Motivo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)]


class Esquema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Pagina(BaseModel, Generic[T]):
    items: list[T]
    total: int
    pagina: int
    tamano: int


class Mensaje(BaseModel):
    mensaje: str


class ConMotivo(BaseModel):
    motivo: Motivo
