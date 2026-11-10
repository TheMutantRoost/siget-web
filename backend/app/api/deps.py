"""Dependencias comunes: base de datos, reloj, sesión, CSRF y roles."""
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.errores import PermisoDenegadoError
from app.core.reloj import Reloj, obtener_reloj
from app.core.seguridad import CABECERA_CSRF, COOKIE_SESION
from app.models import Rol, SesionUsuario
from app.services import auth_service
from app.services.contexto import Actor, Contexto

METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}
RUTAS_SIN_CAMBIO_PASSWORD = {"/api/v1/auth/me", "/api/v1/auth/cambiar-password", "/api/v1/auth/logout"}

DB = Annotated[Session, Depends(obtener_db)]
RelojDep = Annotated[Reloj, Depends(obtener_reloj)]


def ip_cliente(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


def sesion_actual(request: Request, db: DB, reloj: RelojDep) -> SesionUsuario:
    sesion = auth_service.validar_sesion(db, reloj, request.cookies.get(COOKIE_SESION))
    if request.method not in METODOS_SEGUROS:
        auth_service.verificar_csrf(sesion, request.headers.get(CABECERA_CSRF))
    if sesion.usuario.debe_cambiar_password and request.url.path not in RUTAS_SIN_CAMBIO_PASSWORD:
        raise PermisoDenegadoError(
            "Debe cambiar su contraseña antes de continuar.", codigo="cambio_password_requerido"
        )
    return sesion


SesionDep = Annotated[SesionUsuario, Depends(sesion_actual)]


def actor_actual(request: Request, sesion: SesionDep) -> Actor:
    return Actor.desde_usuario(sesion.usuario, ip_cliente(request), request.headers.get("user-agent"))


ActorDep = Annotated[Actor, Depends(actor_actual)]


def contexto(db: DB, reloj: RelojDep, actor: ActorDep) -> Contexto:
    return Contexto(db=db, actor=actor, reloj=reloj)


Ctx = Annotated[Contexto, Depends(contexto)]


def requiere_rol(*roles: str) -> Callable[[Contexto], Contexto]:
    def _verificar(ctx: Ctx) -> Contexto:
        if ctx.actor.rol not in roles:
            raise PermisoDenegadoError("No tiene permiso para esta operación.")
        return ctx

    return _verificar


CtxAdmin = Annotated[Contexto, Depends(requiere_rol(Rol.ADMINISTRADOR))]
CtxAcademico = Annotated[Contexto, Depends(requiere_rol(Rol.ADMINISTRADOR, Rol.DOCENTE))]


class Paginacion:
    def __init__(
        self,
        pagina: Annotated[int, Query(ge=1)] = 1,
        tamano: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> None:
        self.pagina = pagina
        self.tamano = tamano

    @property
    def offset(self) -> int:
        return (self.pagina - 1) * self.tamano


PaginacionDep = Annotated[Paginacion, Depends()]
