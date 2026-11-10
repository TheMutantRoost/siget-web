"""Inicio de sesión, sesiones en servidor, bloqueos y cambio de contraseña."""
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core import seguridad
from app.core.errores import (
    DemasiadosIntentosError,
    NoAutenticadoError,
    PermisoDenegadoError,
    ReglaNegocioError,
)
from app.core.reloj import Reloj
from app.models import IntentoLogin, SesionUsuario, Usuario
from app.services import auditoria_service
from app.services.contexto import Actor
from app.services.parametros_service import Parametro, obtener

MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos."


@dataclass(frozen=True)
class SesionCreada:
    usuario: Usuario
    token: str
    csrf: str
    expira: int  # segundos hasta el límite absoluto


def validar_politica_password(db: Session, password: str) -> None:
    minimo = obtener(db, Parametro.PASSWORD_MIN)
    if len(password) < minimo:
        raise ReglaNegocioError(f"La contraseña debe tener al menos {minimo} caracteres.")
    if password.isdigit() or password.isalpha():
        raise ReglaNegocioError("La contraseña debe combinar letras y números o símbolos.")


def _registrar_intento(db: Session, username: str, ip: str, exito: bool, reloj: Reloj) -> None:
    db.add(IntentoLogin(username=username[:50], ip=ip, exito=exito, fecha=reloj.ahora()))


def iniciar_sesion(
    db: Session, reloj: Reloj, *, username: str, password: str, ip: str, user_agent: str | None
) -> SesionCreada:
    ahora = reloj.ahora()
    ventana = obtener(db, Parametro.IP_VENTANA_MINUTOS)
    fallos_ip = db.scalar(
        select(func.count()).where(
            IntentoLogin.ip == ip,
            IntentoLogin.exito.is_(False),
            IntentoLogin.fecha >= ahora - timedelta(minutes=ventana),
        )
    ) or 0
    if fallos_ip >= obtener(db, Parametro.IP_MAX_FALLOS):
        raise DemasiadosIntentosError(
            f"Demasiados intentos desde esta conexión. Espere {ventana} minutos."
        )

    usuario = db.scalar(select(Usuario).where(Usuario.username == username).with_for_update())
    actor_ip = Actor(usuario_id=usuario.id, rol=usuario.rol.nombre, ip=ip, user_agent=user_agent) if usuario else None

    if usuario and usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
        _registrar_intento(db, username, ip, False, reloj)
        db.commit()
        raise NoAutenticadoError(
            f"Cuenta bloqueada temporalmente hasta las {usuario.bloqueado_hasta:%H:%M}.",
            codigo="cuenta_bloqueada",
        )

    if usuario is None or not usuario.activo or not seguridad.verificar_password(
        usuario.password_hash, password
    ):
        _registrar_intento(db, username, ip, False, reloj)
        if usuario is not None and usuario.activo:
            usuario.intentos_fallidos += 1
            if usuario.intentos_fallidos >= obtener(db, Parametro.BLOQUEO_INTENTOS):
                usuario.bloqueado_hasta = ahora + timedelta(
                    minutes=obtener(db, Parametro.BLOQUEO_MINUTOS)
                )
                usuario.intentos_fallidos = 0
                auditoria_service.registrar(
                    db, actor_ip, modulo="seguridad", evento="cuenta_bloqueada", accion="evento",
                    entidad="usuarios", registro_id=usuario.id,
                )
        # Los fallos deben persistir aunque la petición termine en error.
        db.commit()
        raise NoAutenticadoError(MENSAJE_CREDENCIALES, codigo="credenciales_invalidas")

    if seguridad.necesita_rehash(usuario.password_hash):
        usuario.password_hash = seguridad.hashear_password(password)
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.ultimo_acceso = ahora
    _registrar_intento(db, username, ip, True, reloj)

    token, csrf = seguridad.generar_token(), seguridad.generar_token()
    horas = obtener(db, Parametro.SESION_MAX_HORAS)
    db.add(
        SesionUsuario(
            usuario_id=usuario.id,
            token_hash=seguridad.hash_token(token),
            csrf_hash=seguridad.hash_token(csrf),
            creada_en=ahora,
            ultimo_uso=ahora,
            expira_absoluta=ahora + timedelta(hours=horas),
            ip=ip,
            user_agent=(user_agent or "")[:255],
        )
    )
    auditoria_service.registrar(
        db, actor_ip, modulo="seguridad", evento="inicio_sesion", accion="evento",
        entidad="usuarios", registro_id=usuario.id,
    )
    return SesionCreada(usuario=usuario, token=token, csrf=csrf, expira=horas * 3600)


def validar_sesion(db: Session, reloj: Reloj, token: str | None) -> SesionUsuario:
    if not token:
        raise NoAutenticadoError("Debe iniciar sesión.")
    sesion = db.scalar(
        select(SesionUsuario).where(
            SesionUsuario.token_hash == seguridad.hash_token(token),
            SesionUsuario.cerrada_en.is_(None),
        )
    )
    if sesion is None:
        raise NoAutenticadoError("La sesión no es válida. Inicie sesión de nuevo.")
    ahora = reloj.ahora()
    inactividad = timedelta(minutes=obtener(db, Parametro.INACTIVIDAD_MINUTOS))
    motivo = None
    if (ahora - sesion.ultimo_uso).total_seconds() > inactividad.total_seconds():
        motivo = "inactividad"
    elif ahora >= sesion.expira_absoluta:
        motivo = "limite_absoluto"
    elif not sesion.usuario.activo:
        motivo = "usuario_desactivado"
    if motivo:
        sesion.cerrada_en = ahora
        sesion.motivo_cierre = motivo
        db.commit()
        raise NoAutenticadoError("Su sesión expiró. Inicie sesión de nuevo.", codigo="sesion_expirada")
    # Escribir el último uso como máximo una vez por minuto.
    if (ahora - sesion.ultimo_uso).total_seconds() >= 60:
        sesion.ultimo_uso = ahora
    return sesion


def verificar_csrf(sesion: SesionUsuario, cabecera: str | None) -> None:
    if not cabecera or not seguridad.tokens_iguales(
        sesion.csrf_hash, seguridad.hash_token(cabecera)
    ):
        raise PermisoDenegadoError("Token CSRF inválido o ausente.", codigo="csrf_invalido")


def cerrar_sesion(db: Session, reloj: Reloj, sesion: SesionUsuario, actor: Actor) -> None:
    sesion.cerrada_en = reloj.ahora()
    sesion.motivo_cierre = "cierre_usuario"
    auditoria_service.registrar(
        db, actor, modulo="seguridad", evento="cierre_sesion", accion="evento",
        entidad="usuarios", registro_id=actor.usuario_id,
    )


def cerrar_sesiones_de(
    db: Session, reloj: Reloj, usuario_id: int, actor: Actor, *, excepto_id: int | None = None
) -> int:
    condicion = [SesionUsuario.usuario_id == usuario_id, SesionUsuario.cerrada_en.is_(None)]
    if excepto_id:
        condicion.append(SesionUsuario.id != excepto_id)
    resultado = db.execute(
        update(SesionUsuario)
        .where(*condicion)
        .values(cerrada_en=reloj.ahora(), cerrada_por=actor.usuario_id, motivo_cierre="cierre_admin")
    )
    return resultado.rowcount or 0


def cambiar_password(
    db: Session, reloj: Reloj, sesion: SesionUsuario, actor: Actor, actual: str, nueva: str
) -> None:
    usuario = sesion.usuario
    if not seguridad.verificar_password(usuario.password_hash, actual):
        raise ReglaNegocioError("La contraseña actual no es correcta.")
    if actual == nueva:
        raise ReglaNegocioError("La nueva contraseña debe ser distinta de la actual.")
    validar_politica_password(db, nueva)
    usuario.password_hash = seguridad.hashear_password(nueva)
    usuario.debe_cambiar_password = False
    cerrar_sesiones_de(db, reloj, usuario.id, actor, excepto_id=sesion.id)
    auditoria_service.registrar(
        db, actor, modulo="seguridad", evento="cambio_password", accion="modificar",
        entidad="usuarios", registro_id=usuario.id,
    )
