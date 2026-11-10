from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from app.api.deps import DB, ActorDep, RelojDep, SesionDep, ip_cliente
from app.core.config import obtener_configuracion
from app.core.seguridad import COOKIE_CSRF, COOKIE_SESION
from app.models import Docente, Usuario
from app.schemas.auth import CambioPasswordEntrada, LoginEntrada, SesionSalida, UsuarioSesion
from app.schemas.comun import Mensaje
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["autenticación"])


def _usuario_sesion(db: DB, usuario: Usuario) -> UsuarioSesion:
    docente_id = db.scalar(select(Docente.id).where(Docente.usuario_id == usuario.id))
    return UsuarioSesion(
        id=usuario.id,
        username=usuario.username,
        nombre_completo=usuario.nombre_completo,
        rol=usuario.rol.nombre,
        debe_cambiar_password=usuario.debe_cambiar_password,
        docente_id=docente_id,
        ultimo_acceso=usuario.ultimo_acceso,
    )


def _poner_cookies(response: Response, token: str, csrf: str, max_age: int) -> None:
    segura = obtener_configuracion().cookie_segura
    response.set_cookie(
        COOKIE_SESION, token, max_age=max_age, httponly=True, secure=segura, samesite="lax", path="/"
    )
    # Legible por el frontend para enviarlo en la cabecera X-CSRF-Token (doble envío).
    response.set_cookie(
        COOKIE_CSRF, csrf, max_age=max_age, httponly=False, secure=segura, samesite="strict", path="/"
    )


@router.post("/login", response_model=SesionSalida)
def login(datos: LoginEntrada, request: Request, response: Response, db: DB, reloj: RelojDep) -> SesionSalida:
    creada = auth_service.iniciar_sesion(
        db,
        reloj,
        username=datos.username.strip(),
        password=datos.password,
        ip=ip_cliente(request),
        user_agent=request.headers.get("user-agent"),
    )
    _poner_cookies(response, creada.token, creada.csrf, creada.expira)
    return SesionSalida(usuario=_usuario_sesion(db, creada.usuario), csrf=creada.csrf)


@router.get("/me", response_model=UsuarioSesion)
def yo(sesion: SesionDep, db: DB) -> UsuarioSesion:
    return _usuario_sesion(db, sesion.usuario)


@router.post("/logout", response_model=Mensaje)
def logout(response: Response, sesion: SesionDep, actor: ActorDep, db: DB, reloj: RelojDep) -> Mensaje:
    auth_service.cerrar_sesion(db, reloj, sesion, actor)
    response.delete_cookie(COOKIE_SESION, path="/")
    response.delete_cookie(COOKIE_CSRF, path="/")
    return Mensaje(mensaje="Sesión cerrada.")


@router.post("/cambiar-password", response_model=Mensaje)
def cambiar_password(
    datos: CambioPasswordEntrada, sesion: SesionDep, actor: ActorDep, db: DB, reloj: RelojDep
) -> Mensaje:
    auth_service.cambiar_password(db, reloj, sesion, actor, datos.actual, datos.nueva)
    return Mensaje(mensaje="Contraseña actualizada.")
