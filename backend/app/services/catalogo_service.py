"""Catálogos: sedes, ambientes, áreas, facultades, carreras, ciclos y tipos de documento."""
from typing import Any, TypeVar

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errores import ConflictoError, NoEncontradoError, ReglaNegocioError
from app.models import (
    Ambiente,
    Area,
    Base,
    Carrera,
    CicloAcademico,
    EstadoRegistro,
    Facultad,
    Sede,
    TipoDocumento,
)
from app.services import auditoria_service
from app.services.contexto import Contexto

M = TypeVar("M", bound=Base)

ENTIDADES: dict[str, type[Base]] = {
    "sedes": Sede,
    "ambientes": Ambiente,
    "areas": Area,
    "facultades": Facultad,
    "carreras": Carrera,
    "ciclos": CicloAcademico,
}


def obtener(db: Session, modelo: type[M], id_: int) -> M:
    objeto = db.get(modelo, id_)
    if objeto is None:
        raise NoEncontradoError("Registro no encontrado.")
    return objeto


def _guardar(ctx: Contexto, objeto: Base, evento: str, accion: str, datos: dict[str, Any], antes: dict[str, Any] | None = None) -> None:
    try:
        ctx.db.flush()
    except IntegrityError as exc:
        raise ConflictoError("Ya existe un registro con ese código o nombre.") from exc
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="catalogos", evento=evento, accion=accion,
        entidad=objeto.__tablename__, registro_id=objeto.id, antes=antes, despues=datos,  # type: ignore[attr-defined]
    )


def listar(db: Session, modelo: type[M]) -> list[M]:
    orden = getattr(modelo, "nombre", None) or getattr(modelo, "id")
    return list(db.scalars(select(modelo).order_by(orden)))


def crear(ctx: Contexto, modelo: type[M], datos: dict[str, Any]) -> M:
    if modelo is Ambiente:
        sede = obtener(ctx.db, Sede, datos["sede_id"])
        if sede.estado != EstadoRegistro.ACTIVO:
            raise ReglaNegocioError("La sede está inactiva.")
    if modelo is Carrera:
        obtener(ctx.db, Facultad, datos["facultad_id"])
    if modelo is CicloAcademico:
        datos = {**datos, "activo": False}
    objeto = modelo(**datos)
    ctx.db.add(objeto)
    _guardar(ctx, objeto, f"{modelo.__tablename__}_creado", "crear", datos)
    return objeto


def actualizar(ctx: Contexto, modelo: type[M], id_: int, datos: dict[str, Any]) -> M:
    objeto = obtener(ctx.db, modelo, id_)
    if modelo is Ambiente and "sede_id" in datos and datos["sede_id"] != objeto.sede_id:  # type: ignore[attr-defined]
        raise ReglaNegocioError("Un ambiente no puede cambiar de sede; cree uno nuevo.")
    antes = {k: getattr(objeto, k) for k in datos}
    for clave, valor in datos.items():
        setattr(objeto, clave, valor)
    _guardar(ctx, objeto, f"{modelo.__tablename__}_modificado", "modificar", datos, antes)
    return objeto


def activar_ciclo(ctx: Contexto, ciclo_id: int) -> CicloAcademico:
    ciclo = obtener(ctx.db, CicloAcademico, ciclo_id)
    # Desactivar el anterior y activar el nuevo en la misma transacción.
    ctx.db.execute(update(CicloAcademico).where(CicloAcademico.activo.is_(True)).values(activo=False))
    ctx.db.flush()
    ciclo.activo = True
    _guardar(ctx, ciclo, "ciclo_activado", "modificar", {"activo": True})
    return ciclo


def validar_documento(db: Session, tipo_documento_id: int, numero: str) -> str:
    tipo = db.get(TipoDocumento, tipo_documento_id)
    if tipo is None or not tipo.activo:
        raise ReglaNegocioError("Tipo de documento inválido.")
    numero = numero.strip().upper()
    if not tipo.longitud_min <= len(numero) <= tipo.longitud_max:
        raise ReglaNegocioError(
            f"El {tipo.nombre} debe tener entre {tipo.longitud_min} y {tipo.longitud_max} caracteres."
            if tipo.longitud_min != tipo.longitud_max
            else f"El {tipo.nombre} debe tener {tipo.longitud_min} caracteres."
        )
    if tipo.solo_digitos and not numero.isdigit():
        raise ReglaNegocioError(f"El {tipo.nombre} solo admite dígitos.")
    if not numero.isalnum():
        raise ReglaNegocioError("El número de documento solo admite letras y dígitos.")
    return numero
