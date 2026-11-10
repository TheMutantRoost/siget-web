"""DisponibilidadService: único lugar donde se detectan cruces de horario.

Compara ocurrencias concretas (fecha y hora reales de cada sesión), de modo que
cancelaciones y reprogramaciones quedan incluidas sin lógica especial. Solo se
consideran ocurrencias desde hoy (propuesta P5 aprobada).
"""
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errores import ConflictoHorarioError, PermisoDenegadoError, ReglaNegocioError
from app.models import (
    Base,
    Docente,
    DocenteArea,
    EstadoInscripcion,
    EstadoSesion,
    EstadoTaller,
    ExcepcionAreaDocente,
    Inscripcion,
    Sesion,
    Taller,
)
from app.services import auditoria_service
from app.services.contexto import Contexto
from app.services.parametros_service import Parametro, obtener

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
ESTADOS_OCUPAN = (EstadoSesion.PROGRAMADA, EstadoSesion.REALIZADA)
MOTIVO_CRUCE = "cruce de horario"
MOTIVO_TRASLADO = "tiempo de traslado insuficiente entre sedes"
MOTIVO_AMBIENTE = "ambiente ocupado"


@dataclass(frozen=True)
class Ocurrencia:
    fecha: date
    inicio: time
    fin: time
    sede_id: int
    sede: str
    taller_id: int | None
    taller: str
    ambiente_id: int | None = None


def bloquear_filas(db: Session, modelo: type[Base], ids: Iterable[int]) -> None:
    """SELECT … FOR UPDATE en orden ascendente para evitar interbloqueos."""
    unicos = sorted({i for i in ids if i is not None})
    if unicos:
        db.execute(
            select(modelo.id).where(modelo.id.in_(unicos)).order_by(modelo.id).with_for_update()  # type: ignore[attr-defined]
        ).all()


def _instante(fecha: date, hora: time) -> datetime:
    return datetime.combine(fecha, hora)


def motivo_conflicto(a: Ocurrencia, b: Ocurrencia, traslado_minutos: int) -> str | None:
    """Mismo día: misma sede → inicio_A < fin_B y fin_A > inicio_B; sedes distintas suma T."""
    if a.fecha != b.fecha:
        return None
    ini_a, fin_a = _instante(a.fecha, a.inicio), _instante(a.fecha, a.fin)
    ini_b, fin_b = _instante(b.fecha, b.inicio), _instante(b.fecha, b.fin)
    if ini_a < fin_b and fin_a > ini_b:
        return MOTIVO_CRUCE
    if a.sede_id != b.sede_id:
        t = timedelta(minutes=traslado_minutos)
        if ini_a < fin_b + t and fin_a + t > ini_b:
            return MOTIVO_TRASLADO
    return None


def _detalle(existente: Ocurrencia, nueva: Ocurrencia, motivo: str) -> dict[str, Any]:
    return {
        "taller_actual": existente.taller,
        "taller_nuevo": nueva.taller,
        "fecha": nueva.fecha.isoformat(),
        "dia": DIAS[nueva.fecha.weekday()],
        "inicio": nueva.inicio.strftime("%H:%M"),
        "fin": nueva.fin.strftime("%H:%M"),
        "inicio_actual": existente.inicio.strftime("%H:%M"),
        "fin_actual": existente.fin.strftime("%H:%M"),
        "sede": nueva.sede,
        "sede_actual": existente.sede,
        "motivo": motivo,
    }


def _comparar(
    existentes: Sequence[Ocurrencia], nuevas: Sequence[Ocurrencia], traslado: int, *, considerar_sede: bool = True
) -> list[dict[str, Any]]:
    por_fecha: dict[date, list[Ocurrencia]] = {}
    for e in existentes:
        por_fecha.setdefault(e.fecha, []).append(e)
    conflictos = []
    for n in nuevas:
        for e in por_fecha.get(n.fecha, []):
            motivo = motivo_conflicto(e, n, traslado if considerar_sede else 0)
            if motivo and (considerar_sede or motivo == MOTIVO_CRUCE):
                conflictos.append(_detalle(e, n, motivo if considerar_sede else MOTIVO_AMBIENTE))
    return conflictos


def _ocurrencias(db: Session, condiciones: list[Any], desde: date) -> list[Ocurrencia]:
    filas = db.execute(
        select(Sesion, Taller)
        .join(Taller, Taller.id == Sesion.taller_id)
        .where(Sesion.fecha >= desde, Sesion.estado.in_(ESTADOS_OCUPAN), Taller.estado == EstadoTaller.ACTIVO, *condiciones)
    ).all()
    return [
        Ocurrencia(
            fecha=s.fecha, inicio=s.hora_inicio, fin=s.hora_fin, sede_id=t.sede_id, sede=t.sede.nombre,
            taller_id=t.id, taller=f"{t.codigo} {t.nombre}", ambiente_id=s.ambiente_id,
        )
        for s, t in filas
    ]


def ocurrencias_de_taller(db: Session, taller_id: int, desde: date) -> list[Ocurrencia]:
    return _ocurrencias(db, [Sesion.taller_id == taller_id], desde)


def _lanzar(conflictos: list[dict[str, Any]], sujeto: str) -> None:
    if not conflictos:
        return
    c = conflictos[0]
    raise ConflictoHorarioError(
        f"{sujeto}: {c['motivo']} con {c['taller_actual']} el {c['dia']} {c['fecha']} "
        f"({c['inicio_actual']}–{c['fin_actual']}, sede {c['sede_actual']}) frente a "
        f"{c['taller_nuevo']} ({c['inicio']}–{c['fin']}, sede {c['sede']}).",
        detalles=conflictos[:20],
    )


def validar_estudiante(
    ctx: Contexto,
    estudiante_id: int,
    taller_destino_id: int,
    excluir_taller_ids: Sequence[int] = (),
    nuevas: Sequence[Ocurrencia] | None = None,
) -> None:
    """Compara las sesiones del taller destino (o las indicadas) con sus inscripciones activas."""
    hoy = ctx.reloj.hoy()
    if nuevas is None:
        nuevas = ocurrencias_de_taller(ctx.db, taller_destino_id, hoy)
    talleres_actuales = select(Inscripcion.taller_id).where(
        Inscripcion.estudiante_id == estudiante_id,
        Inscripcion.estado == EstadoInscripcion.ACTIVO,
        Inscripcion.taller_id != taller_destino_id,
        Inscripcion.taller_id.not_in(list(excluir_taller_ids) or [0]),
    )
    existentes = _ocurrencias(ctx.db, [Sesion.taller_id.in_(talleres_actuales)], hoy)
    _lanzar(_comparar(existentes, nuevas, obtener(ctx.db, Parametro.TRASLADO_MINUTOS)), "Estudiante")


def _cubierta_por_disponibilidad(docente: Docente, oc: Ocurrencia) -> bool:
    dia = oc.fecha.isoweekday()
    for d in docente.disponibilidad:
        vigente = (d.vigente_desde is None or d.vigente_desde <= oc.fecha) and (
            d.vigente_hasta is None or oc.fecha <= d.vigente_hasta
        )
        if d.dia_semana == dia and vigente and d.hora_inicio <= oc.inicio and oc.fin <= d.hora_fin:
            return True
    return False


def validar_docente(
    ctx: Contexto, docente: Docente, nuevas: Sequence[Ocurrencia], excluir_taller_id: int | None
) -> None:
    if not docente.activo:
        raise ReglaNegocioError("El docente está inactivo.")
    if not docente.disponibilidad:
        raise ReglaNegocioError(
            f"El docente {docente.nombre_completo} no tiene disponibilidad registrada."
        )
    fuera = [oc for oc in nuevas if not _cubierta_por_disponibilidad(docente, oc)]
    if fuera:
        oc = fuera[0]
        raise ConflictoHorarioError(
            f"Docente: el {DIAS[oc.fecha.weekday()]} {oc.fecha.isoformat()} "
            f"{oc.inicio:%H:%M}–{oc.fin:%H:%M} está fuera de su disponibilidad registrada.",
            detalles=[{"fecha": o.fecha.isoformat(), "inicio": f"{o.inicio:%H:%M}", "fin": f"{o.fin:%H:%M}",
                       "motivo": "fuera de la disponibilidad del docente"} for o in fuera[:20]],
        )
    condiciones = [Taller.docente_id == docente.id]
    if excluir_taller_id:
        condiciones.append(Taller.id != excluir_taller_id)
    existentes = _ocurrencias(ctx.db, condiciones, ctx.reloj.hoy())
    _lanzar(_comparar(existentes, nuevas, obtener(ctx.db, Parametro.TRASLADO_MINUTOS)), "Docente")


def validar_ambiente(ctx: Contexto, nuevas: Sequence[Ocurrencia], excluir_taller_id: int | None) -> None:
    ambientes = {oc.ambiente_id for oc in nuevas if oc.ambiente_id}
    if not ambientes:
        return
    condiciones = [Sesion.ambiente_id.in_(ambientes)]
    if excluir_taller_id:
        condiciones.append(Taller.id != excluir_taller_id)
    existentes = _ocurrencias(ctx.db, condiciones, ctx.reloj.hoy())
    conflictos = []
    for amb in ambientes:
        conflictos += _comparar(
            [e for e in existentes if e.ambiente_id == amb],
            [n for n in nuevas if n.ambiente_id == amb], 0, considerar_sede=False,
        )
    _lanzar(conflictos, "Ambiente")


def validar_area(
    ctx: Contexto, docente: Docente, area_id: int, taller_id: int | None, justificacion: str | None
) -> bool:
    """Devuelve True si se usará una excepción (que se registra cuando exista el taller)."""
    autorizado = ctx.db.scalar(
        select(DocenteArea).where(DocenteArea.docente_id == docente.id, DocenteArea.area_id == area_id)
    )
    if autorizado:
        return False
    if taller_id and ctx.db.scalar(
        select(ExcepcionAreaDocente.id).where(
            ExcepcionAreaDocente.docente_id == docente.id,
            ExcepcionAreaDocente.area_id == area_id,
            ExcepcionAreaDocente.taller_id == taller_id,
        )
    ):
        return False
    if not ctx.actor.es_admin:
        raise PermisoDenegadoError("Solo un administrador puede autorizar una excepción de área.")
    if not justificacion or len(justificacion.strip()) < 10:
        raise ReglaNegocioError(
            "El docente no está autorizado para el área del taller. "
            "Indique una justificación (mínimo 10 caracteres) para registrar la excepción."
        )
    return True


def registrar_excepcion_area(ctx: Contexto, docente_id: int, area_id: int, taller_id: int, justificacion: str) -> None:
    excepcion = ExcepcionAreaDocente(
        docente_id=docente_id, area_id=area_id, taller_id=taller_id,
        justificacion=justificacion.strip(), autorizado_por=ctx.actor.usuario_id,
    )
    ctx.db.add(excepcion)
    ctx.db.flush()
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="talleres", evento="excepcion_area_docente", accion="crear",
        entidad="excepciones_area_docente", registro_id=excepcion.id,
        despues={"docente_id": docente_id, "area_id": area_id, "taller_id": taller_id,
                 "justificacion": justificacion},
    )


def validar_disponibilidad_vigente(ctx: Contexto, docente: Docente) -> None:
    """Tras cambiar la disponibilidad, las sesiones futuras del docente deben seguir cubiertas."""
    existentes = _ocurrencias(ctx.db, [Taller.docente_id == docente.id], ctx.reloj.hoy())
    if existentes and not docente.disponibilidad:
        raise ReglaNegocioError("El docente tiene sesiones asignadas; su disponibilidad no puede quedar vacía.")
    fuera = [oc for oc in existentes if not _cubierta_por_disponibilidad(docente, oc)]
    if fuera:
        oc = fuera[0]
        raise ConflictoHorarioError(
            f"La nueva disponibilidad no cubre la sesión de {oc.taller} del "
            f"{DIAS[oc.fecha.weekday()]} {oc.fecha.isoformat()} ({oc.inicio:%H:%M}–{oc.fin:%H:%M}).",
            detalles=[{"taller": o.taller, "fecha": o.fecha.isoformat(), "inicio": f"{o.inicio:%H:%M}",
                       "fin": f"{o.fin:%H:%M}"} for o in fuera[:20]],
        )
