"""Contexto de cada operación: quién la hace, desde dónde y con qué reloj."""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.reloj import Reloj
from app.models import Rol, Usuario


@dataclass(frozen=True)
class Actor:
    usuario_id: int
    rol: str
    ip: str | None = None
    user_agent: str | None = None

    @property
    def es_admin(self) -> bool:
        return self.rol == Rol.ADMINISTRADOR

    @property
    def es_docente(self) -> bool:
        return self.rol == Rol.DOCENTE

    @classmethod
    def desde_usuario(cls, usuario: Usuario, ip: str | None = None, ua: str | None = None) -> "Actor":
        return cls(usuario_id=usuario.id, rol=usuario.rol.nombre, ip=ip, user_agent=ua)


@dataclass(frozen=True)
class Contexto:
    db: Session
    actor: Actor
    reloj: Reloj
