"""Registro de asistencia por sesión, congelación, primer registro tardío y autorizaciones."""
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select

from app.core.errores import NoEncontradoError, PermisoDenegadoError, ReglaNegocioError
from app.models import (
    Asistencia,
    AutorizacionEdicion,
    EstadoAsistencia,
    EstadoInscripcion,
    EstadoSesion,
    Inscripcion,
    Sesion,
    Taller,
)
from app.services import auditoria_service, taller_service
from app.services.contexto import Contexto
from app.services.parametros_service import Parametro, obtener


@dataclass(frozen=True)
class RegistroEntrada:
    inscripcion_id: int
    estado: EstadoAsistencia
    observacion: str | None


@dataclass(frozen=True)
class EstadoEdicion:
    congelada: bool
    primer_registro: bool
    puede_editar: bool
    motivo: str | None
    autorizacion_id: int | None


def _sesion(ctx: Contexto, sesion_id: int) -> Sesion:
    sesion = ctx.db.get(Sesion, sesion_id)
    if sesion is None:
        raise NoEncontradoError("Sesión no encontrada.")
    return sesion


def _autorizacion_vigente(ctx: Contexto, sesion: Sesion, taller: Taller) -> AutorizacionEdicion | None:
    return ctx.db.scalar(
        select(AutorizacionEdicion).where(
            AutorizacionEdicion.sesion_id == sesion.id,
            AutorizacionEdicion.docente_id == taller.docente_id,
            AutorizacionEdicion.consumida_en.is_(None),
            AutorizacionEdicion.revocada_en.is_(None),
            AutorizacionEdicion.vence_en > ctx.reloj.ahora(),
        ).order_by(AutorizacionEdicion.id.desc())
    )


def estado_edicion(ctx: Contexto, sesion: Sesion, taller: Taller) -> EstadoEdicion:
    hoy = ctx.reloj.hoy()
    congelada = hoy > sesion.fecha
    primer = not ctx.db.scalar(select(func.count()).where(Asistencia.sesion_id == sesion.id))
    if sesion.estado in (EstadoSesion.CANCELADA, EstadoSesion.REPROGRAMADA):
        return EstadoEdicion(congelada, primer, False, f"La sesión está {sesion.estado.value.lower()}.", None)
    if sesion.fecha > hoy:
        return EstadoEdicion(False, primer, False, "La sesión todavía no ocurre.", None)
    if ctx.actor.es_admin or not congelada:
        return EstadoEdicion(congelada, primer, True, None, None)
    if not ctx.actor.es_docente:
        return EstadoEdicion(congelada, primer, False, "Su rol no registra asistencia.", None)
    plazo = obtener(ctx.db, Parametro.PLAZO_REGISTRO_TARDIO_DIAS)
    if primer:
        if hoy <= sesion.fecha + timedelta(days=plazo):
            return EstadoEdicion(congelada, primer, True, None, None)
        return EstadoEdicion(
            congelada, primer, False,
            f"Pasaron más de {plazo} días: solo el administrador puede hacer el primer registro.", None,
        )
    autorizacion = _autorizacion_vigente(ctx, sesion, taller)
    if autorizacion:
        return EstadoEdicion(congelada, primer, True, None, autorizacion.id)
    return EstadoEdicion(
        congelada, primer, False,
        "Sesión congelada: necesita la autorización del administrador para editarla.", None,
    )


def hoja(ctx: Contexto, sesion_id: int) -> tuple[Sesion, list[Inscripcion], dict[int, Asistencia], EstadoEdicion]:
    sesion = _sesion(ctx, sesion_id)
    taller = taller_service.obtener_taller(ctx.db, sesion.taller_id)
    taller_service.verificar_acceso(ctx, taller)
    inscritos = list(ctx.db.scalars(
        select(Inscripcion).where(
            Inscripcion.taller_id == taller.id, Inscripcion.estado == EstadoInscripcion.ACTIVO
        )
    ))
    inscritos.sort(key=lambda i: (i.estudiante.apellido_paterno, i.estudiante.apellido_materno or "", i.estudiante.nombres))
    registros = {a.inscripcion_id: a for a in ctx.db.scalars(select(Asistencia).where(Asistencia.sesion_id == sesion.id))}
    return sesion, inscritos, registros, estado_edicion(ctx, sesion, taller)


def guardar(ctx: Contexto, sesion_id: int, registros: list[RegistroEntrada]) -> Sesion:
    sesion = _sesion(ctx, sesion_id)
    taller = taller_service.bloquear_taller(ctx.db, sesion.taller_id)  # orden: taller primero
    taller_service.verificar_acceso(ctx, taller)
    estado = estado_edicion(ctx, sesion, taller)
    if not estado.puede_editar:
        raise PermisoDenegadoError(estado.motivo or "No puede editar esta sesión.", codigo="sesion_congelada")

    registros = [RegistroEntrada(r.inscripcion_id, EstadoAsistencia(r.estado), r.observacion) for r in registros]
    activos = set(ctx.db.scalars(
        select(Inscripcion.id).where(
            Inscripcion.taller_id == taller.id, Inscripcion.estado == EstadoInscripcion.ACTIVO
        )
    ))
    enviados = [r.inscripcion_id for r in registros]
    if len(enviados) != len(set(enviados)):
        raise ReglaNegocioError("Hay estudiantes repetidos en el registro.")
    if set(enviados) != activos:
        raise ReglaNegocioError(
            "Debe registrar la asistencia de todos los inscritos activos (y solo de ellos).",
            codigo="registro_incompleto",
            detalles={"faltan": sorted(activos - set(enviados)), "sobran": sorted(set(enviados) - activos)},
        )
    for r in registros:
        if r.estado == EstadoAsistencia.JUSTIFICADO and not (r.observacion and r.observacion.strip()):
            raise ReglaNegocioError("Toda asistencia Justificada (J) requiere observación.")

    existentes = {a.inscripcion_id: a for a in ctx.db.scalars(
        select(Asistencia).where(Asistencia.sesion_id == sesion.id).with_for_update()
    )}
    antes = {i: (a.estado.value, a.observacion) for i, a in existentes.items()}
    for r in registros:
        observacion = r.observacion.strip() if r.observacion and r.observacion.strip() else None
        actual = existentes.get(r.inscripcion_id)
        if actual is None:
            ctx.db.add(Asistencia(
                inscripcion_id=r.inscripcion_id, sesion_id=sesion.id, estado=r.estado,
                observacion=observacion, registrado_por=ctx.actor.usuario_id,
            ))
        elif (actual.estado, actual.observacion) != (r.estado, observacion):
            actual.estado = r.estado
            actual.observacion = observacion
            actual.actualizado_por = ctx.actor.usuario_id
    estado_anterior = sesion.estado
    if sesion.estado == EstadoSesion.PROGRAMADA:
        sesion.estado = EstadoSesion.REALIZADA  # primera vez que se guarda asistencia
        sesion.cambiado_por = ctx.actor.usuario_id
        sesion.cambiado_en = ctx.reloj.ahora()
    if estado.autorizacion_id:
        autorizacion = ctx.db.get(AutorizacionEdicion, estado.autorizacion_id)
        if autorizacion:
            autorizacion.consumida_en = ctx.reloj.ahora()
    ctx.db.flush()
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="asistencia",
        evento="asistencia_registrada" if estado.primer_registro else "asistencia_modificada",
        accion="crear" if estado.primer_registro else "modificar", entidad="sesiones", registro_id=sesion.id,
        antes={"estado_sesion": estado_anterior, "registros": antes} if antes else {"estado_sesion": estado_anterior},
        despues={"estado_sesion": sesion.estado, "autorizacion_id": estado.autorizacion_id,
                 "registros": {r.inscripcion_id: (r.estado.value, r.observacion) for r in registros}},
    )
    return sesion


def autorizar_edicion(ctx: Contexto, sesion_id: int, motivo: str) -> AutorizacionEdicion:
    """También es la forma de "descongelar" una sesión para el docente (propuesta P3 aprobada)."""
    sesion = _sesion(ctx, sesion_id)
    taller = taller_service.bloquear_taller(ctx.db, sesion.taller_id)
    if sesion.estado in (EstadoSesion.CANCELADA, EstadoSesion.REPROGRAMADA):
        raise ReglaNegocioError("No se autoriza la edición de una sesión cancelada o reprogramada.")
    ahora = ctx.reloj.ahora()
    autorizacion = AutorizacionEdicion(
        sesion_id=sesion.id, docente_id=taller.docente_id, otorgada_por=ctx.actor.usuario_id,
        motivo=motivo, otorgada_en=ahora,
        vence_en=ahora + timedelta(hours=obtener(ctx.db, Parametro.VIGENCIA_AUTORIZACION_HORAS)),
    )
    ctx.db.add(autorizacion)
    ctx.db.flush()
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="asistencia", evento="autorizacion_edicion", accion="crear",
        entidad="autorizaciones_edicion", registro_id=autorizacion.id,
        despues={"sesion_id": sesion.id, "docente_id": taller.docente_id, "motivo": motivo,
                 "vence_en": autorizacion.vence_en},
    )
    return autorizacion
