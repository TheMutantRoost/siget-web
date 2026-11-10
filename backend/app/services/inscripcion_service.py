"""Inscripciones: alta, reactivación, retiro y cambio de taller (con movimientos)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errores import ConflictoError, NoEncontradoError, ReglaNegocioError
from app.models import (
    EstadoEstudiante,
    EstadoInscripcion,
    EstadoTaller,
    Estudiante,
    Inscripcion,
    MovimientoInscripcion,
    Taller,
    TipoMovimiento,
)
from app.services import auditoria_service, disponibilidad_service, taller_service
from app.services.contexto import Contexto
from app.services.parametros_service import Parametro, obtener


def _validar_destino(ctx: Contexto, taller: Taller, estudiante: Estudiante, excluir: list[int]) -> None:
    """Todas las validaciones de una inscripción nueva, con el taller ya bloqueado."""
    if estudiante.estado != EstadoEstudiante.ACTIVO:
        raise ReglaNegocioError(f"El estudiante está {estudiante.estado.value.lower()}.")
    if taller.estado != EstadoTaller.ACTIVO:
        raise ReglaNegocioError("El taller no está activo.")
    if taller.inscripciones_bloqueadas:
        raise ReglaNegocioError(
            f"Inscripciones bloqueadas: {taller.motivo_bloqueo}", codigo="inscripciones_bloqueadas"
        )
    cierre = obtener(ctx.db, Parametro.SESIONES_CIERRE_INSCRIPCION)
    if taller_service.contar_realizadas(ctx.db, taller.id) >= cierre:
        raise ReglaNegocioError(
            f"Inscripciones cerradas: el taller ya tiene {cierre} o más sesiones realizadas.",
            codigo="inscripciones_cerradas",
        )
    if taller_service.contar_inscritos_activos(ctx.db, taller.id) >= taller.cupo_maximo:
        raise ConflictoError("No hay cupo disponible en el taller.", codigo="sin_cupo")
    disponibilidad_service.validar_estudiante(ctx, estudiante.id, taller.id, excluir)


def _movimiento(ctx: Contexto, inscripcion: Inscripcion, tipo: TipoMovimiento, motivo: str | None, relacionado: int | None = None) -> None:
    ctx.db.add(MovimientoInscripcion(
        inscripcion_id=inscripcion.id, tipo=tipo, fecha=ctx.reloj.hoy(), motivo=motivo,
        usuario_id=ctx.actor.usuario_id, taller_relacionado_id=relacionado,
    ))


def _bloquear_estudiante(db: Session, estudiante_id: int) -> Estudiante:
    estudiante = db.scalar(select(Estudiante).where(Estudiante.id == estudiante_id).with_for_update())
    if estudiante is None:
        raise NoEncontradoError("Estudiante no encontrado.")
    return estudiante


def _alta_o_reactivacion(
    ctx: Contexto, taller: Taller, estudiante: Estudiante, motivo: str | None,
    tipo_alta: TipoMovimiento, excluir: list[int], relacionado: int | None = None,
) -> Inscripcion:
    existente = ctx.db.scalar(
        select(Inscripcion).where(Inscripcion.taller_id == taller.id, Inscripcion.estudiante_id == estudiante.id)
    )
    if existente and existente.estado == EstadoInscripcion.ACTIVO:
        raise ConflictoError("El estudiante ya está inscrito en este taller.", codigo="duplicado")
    _validar_destino(ctx, taller, estudiante, excluir)
    if existente:
        existente.estado = EstadoInscripcion.ACTIVO
        existente.fecha_inscripcion = ctx.reloj.hoy()
        inscripcion = existente
        tipo = TipoMovimiento.REACTIVACION if tipo_alta == TipoMovimiento.ALTA else tipo_alta
    else:
        inscripcion = Inscripcion(
            taller_id=taller.id, estudiante_id=estudiante.id, estado=EstadoInscripcion.ACTIVO,
            fecha_inscripcion=ctx.reloj.hoy(),
        )
        ctx.db.add(inscripcion)
        ctx.db.flush()
        tipo = tipo_alta
    _movimiento(ctx, inscripcion, tipo, motivo, relacionado)
    ctx.db.flush()
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="inscripciones", evento=f"inscripcion_{tipo.value}", accion="crear",
        entidad="inscripciones", registro_id=inscripcion.id,
        despues={"taller_id": taller.id, "estudiante_id": estudiante.id, "motivo": motivo},
    )
    return inscripcion


def inscribir(ctx: Contexto, taller_id: int, estudiante_id: int, motivo: str | None = None) -> Inscripcion:
    # Orden global de bloqueo: taller → estudiante.
    taller = taller_service.bloquear_taller(ctx.db, taller_id)
    estudiante = _bloquear_estudiante(ctx.db, estudiante_id)
    return _alta_o_reactivacion(ctx, taller, estudiante, motivo, TipoMovimiento.ALTA, [])


def retirar(ctx: Contexto, inscripcion_id: int, motivo: str) -> Inscripcion:
    inscripcion = ctx.db.get(Inscripcion, inscripcion_id)
    if inscripcion is None:
        raise NoEncontradoError("Inscripción no encontrada.")
    taller_service.bloquear_taller(ctx.db, inscripcion.taller_id)
    if inscripcion.estado != EstadoInscripcion.ACTIVO:
        raise ReglaNegocioError("La inscripción ya está retirada.")
    inscripcion.estado = EstadoInscripcion.RETIRADO
    _movimiento(ctx, inscripcion, TipoMovimiento.RETIRO, motivo)
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="inscripciones", evento="inscripcion_retiro", accion="modificar",
        entidad="inscripciones", registro_id=inscripcion.id,
        antes={"estado": EstadoInscripcion.ACTIVO}, despues={"estado": EstadoInscripcion.RETIRADO, "motivo": motivo},
    )
    return inscripcion


def cambiar_taller(ctx: Contexto, inscripcion_id: int, taller_destino_id: int, motivo: str) -> Inscripcion:
    origen = ctx.db.get(Inscripcion, inscripcion_id)
    if origen is None:
        raise NoEncontradoError("Inscripción no encontrada.")
    if origen.estado != EstadoInscripcion.ACTIVO:
        raise ReglaNegocioError("Solo se cambia de taller una inscripción activa.")
    if origen.taller_id == taller_destino_id:
        raise ReglaNegocioError("El taller destino es el mismo que el de origen.")
    # Talleres en orden ascendente y luego el estudiante.
    talleres = {t: taller_service.bloquear_taller(ctx.db, t) for t in sorted({origen.taller_id, taller_destino_id})}
    estudiante = _bloquear_estudiante(ctx.db, origen.estudiante_id)
    origen.estado = EstadoInscripcion.RETIRADO
    _movimiento(ctx, origen, TipoMovimiento.CAMBIO_SALIDA, motivo, taller_destino_id)
    ctx.db.flush()
    destino = _alta_o_reactivacion(
        ctx, talleres[taller_destino_id], estudiante, motivo, TipoMovimiento.CAMBIO_ENTRADA,
        [origen.taller_id], origen.taller_id,
    )
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="inscripciones", evento="cambio_taller", accion="modificar",
        entidad="inscripciones", registro_id=origen.id,
        despues={"taller_origen": origen.taller_id, "taller_destino": taller_destino_id, "motivo": motivo},
    )
    return destino


def listar_movimientos(db: Session, inscripcion_id: int) -> list[MovimientoInscripcion]:
    return list(db.scalars(
        select(MovimientoInscripcion).where(MovimientoInscripcion.inscripcion_id == inscripcion_id)
        .order_by(MovimientoInscripcion.id)
    ))


def historial_estudiante(db: Session, estudiante_id: int) -> list[Inscripcion]:
    return list(db.scalars(
        select(Inscripcion).where(Inscripcion.estudiante_id == estudiante_id).order_by(Inscripcion.id.desc())
    ))
