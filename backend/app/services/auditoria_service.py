"""Único punto de escritura de la auditoría. Nunca guarda contraseñas ni tokens."""
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Auditoria
from app.services.contexto import Actor

CAMPOS_SENSIBLES = {"password", "password_hash", "token", "token_hash", "csrf_hash", "csrf"}


def _limpiar(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {k: _limpiar(v) for k, v in valor.items() if k not in CAMPOS_SENSIBLES}
    if isinstance(valor, (list, tuple)):
        return [_limpiar(v) for v in valor]
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, (datetime, date, time)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    return valor


def registrar(
    db: Session,
    actor: Actor | None,
    *,
    modulo: str,
    evento: str,
    accion: str,
    entidad: str | None = None,
    registro_id: int | str | None = None,
    antes: dict[str, Any] | None = None,
    despues: dict[str, Any] | None = None,
) -> None:
    db.add(
        Auditoria(
            usuario_id=actor.usuario_id if actor else None,
            ip=actor.ip if actor else None,
            user_agent=(actor.user_agent or "")[:255] if actor else None,
            modulo=modulo,
            evento=evento,
            accion=accion,
            entidad=entidad,
            registro_id=str(registro_id) if registro_id is not None else None,
            datos_anteriores=_limpiar(antes) if antes else None,
            datos_nuevos=_limpiar(despues) if despues else None,
        )
    )


def listar(
    db: Session, *, modulo: str | None, usuario_id: int | None, pagina: int, tamano: int
) -> tuple[list[Auditoria], int]:
    consulta = select(Auditoria)
    if modulo:
        consulta = consulta.where(Auditoria.modulo == modulo)
    if usuario_id:
        consulta = consulta.where(Auditoria.usuario_id == usuario_id)
    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    filas = db.scalars(
        consulta.order_by(Auditoria.id.desc()).offset((pagina - 1) * tamano).limit(tamano)
    ).all()
    return list(filas), total
