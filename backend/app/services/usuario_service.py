"""Administración de usuarios (no docentes: esos se crean desde DocenteService)."""
import secrets

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import seguridad
from app.core.errores import ConflictoError, NoEncontradoError, ReglaNegocioError
from app.models import Rol, Usuario
from app.services import auditoria_service, auth_service
from app.services.contexto import Contexto


def rol_por_nombre(db: Session, nombre: str) -> Rol:
    rol = db.scalar(select(Rol).where(Rol.nombre == nombre))
    if rol is None:
        raise NoEncontradoError(f"Rol inexistente: {nombre}.")
    return rol


def password_temporal() -> str:
    # 14 caracteres con letras y dígitos: cumple la política mínima configurable por defecto.
    return secrets.token_urlsafe(10)[:12] + str(secrets.randbelow(90) + 10)


def crear(
    ctx: Contexto,
    *,
    username: str,
    email: str,
    nombres: str,
    apellido_paterno: str,
    apellido_materno: str | None,
    rol: str,
    password: str | None = None,
    debe_cambiar: bool = True,
) -> tuple[Usuario, str]:
    clave = password or password_temporal()
    auth_service.validar_politica_password(ctx.db, clave)
    usuario = Usuario(
        rol_id=rol_por_nombre(ctx.db, rol).id,
        username=username.strip().lower(),
        email=email.strip().lower(),
        nombres=nombres,
        apellido_paterno=apellido_paterno,
        apellido_materno=apellido_materno,
        password_hash=seguridad.hashear_password(clave),
        activo=True,
        debe_cambiar_password=debe_cambiar,
        intentos_fallidos=0,
    )
    ctx.db.add(usuario)
    try:
        ctx.db.flush()
    except IntegrityError as exc:
        raise ConflictoError("Ya existe un usuario con ese nombre de usuario o correo.") from exc
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="usuarios", evento="usuario_creado", accion="crear",
        entidad="usuarios", registro_id=usuario.id,
        despues={"username": usuario.username, "email": usuario.email, "rol": rol},
    )
    return usuario, clave


def obtener(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise NoEncontradoError("Usuario no encontrado.")
    return usuario


def listar(db: Session, texto: str | None, offset: int, limite: int) -> tuple[list[Usuario], int]:
    consulta = select(Usuario)
    if texto:
        patron = f"%{texto}%"
        consulta = consulta.where(
            or_(Usuario.username.like(patron), Usuario.nombres.like(patron),
                Usuario.apellido_paterno.like(patron), Usuario.email.like(patron))
        )
    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    filas = db.scalars(consulta.order_by(Usuario.username).offset(offset).limit(limite)).all()
    return list(filas), total


def cambiar_activo(ctx: Contexto, usuario_id: int, activo: bool) -> Usuario:
    usuario = obtener(ctx.db, usuario_id)
    if usuario.id == ctx.actor.usuario_id and not activo:
        raise ReglaNegocioError("No puede desactivar su propia cuenta.")
    usuario.activo = activo
    if not activo:
        auth_service.cerrar_sesiones_de(ctx.db, ctx.reloj, usuario.id, ctx.actor)
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="usuarios",
        evento="usuario_activado" if activo else "usuario_desactivado", accion="modificar",
        entidad="usuarios", registro_id=usuario.id, despues={"activo": activo},
    )
    return usuario


def desbloquear(ctx: Contexto, usuario_id: int) -> Usuario:
    usuario = obtener(ctx.db, usuario_id)
    usuario.bloqueado_hasta = None
    usuario.intentos_fallidos = 0
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="usuarios", evento="usuario_desbloqueado", accion="modificar",
        entidad="usuarios", registro_id=usuario.id,
    )
    return usuario


def restablecer_password(ctx: Contexto, usuario_id: int) -> str:
    usuario = obtener(ctx.db, usuario_id)
    clave = password_temporal()
    usuario.password_hash = seguridad.hashear_password(clave)
    usuario.debe_cambiar_password = True
    usuario.bloqueado_hasta = None
    usuario.intentos_fallidos = 0
    auth_service.cerrar_sesiones_de(ctx.db, ctx.reloj, usuario.id, ctx.actor)
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="usuarios", evento="password_restablecida", accion="modificar",
        entidad="usuarios", registro_id=usuario.id,
    )
    return clave


def cerrar_sesiones(ctx: Contexto, usuario_id: int) -> int:
    obtener(ctx.db, usuario_id)
    cerradas = auth_service.cerrar_sesiones_de(ctx.db, ctx.reloj, usuario_id, ctx.actor)
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="usuarios", evento="sesiones_cerradas", accion="evento",
        entidad="usuarios", registro_id=usuario_id, despues={"cerradas": cerradas},
    )
    return cerradas
