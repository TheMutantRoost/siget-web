"""Consultas en bloque que alimentan a AsistenciaCalculator (sin N+1)."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Asistencia,
    EstadoAsistencia,
    EstadoInscripcion,
    EstadoSesion,
    Inscripcion,
    MovimientoInscripcion,
    Sesion,
    Taller,
)
from app.services import asistencia_calculator as calc
from app.services.parametros_service import Parametro, obtener


@dataclass(frozen=True)
class FilaResumen:
    inscripcion: Inscripcion
    resultado: calc.ResultadoAsistencia


def sesiones_realizadas(db: Session, taller_id: int) -> list[tuple[int, date]]:
    return [
        (sid, fecha)
        for sid, fecha in db.execute(
            select(Sesion.id, Sesion.fecha).where(
                Sesion.taller_id == taller_id, Sesion.estado == EstadoSesion.REALIZADA
            )
        ).all()
    ]


def resumen_taller(db: Session, taller: Taller, solo_activos: bool = True) -> list[FilaResumen]:
    consulta = select(Inscripcion).where(Inscripcion.taller_id == taller.id)
    if solo_activos:
        consulta = consulta.where(Inscripcion.estado == EstadoInscripcion.ACTIVO)
    inscripciones = list(db.scalars(consulta))
    if not inscripciones:
        return []
    ids = [i.id for i in inscripciones]
    movimientos: dict[int, list[tuple]] = defaultdict(list)
    for m in db.scalars(
        select(MovimientoInscripcion).where(MovimientoInscripcion.inscripcion_id.in_(ids))
        .order_by(MovimientoInscripcion.fecha, MovimientoInscripcion.id)
    ):
        movimientos[m.inscripcion_id].append((m.tipo, m.fecha))
    asistencias: dict[int, dict[int, EstadoAsistencia]] = defaultdict(dict)
    for a in db.execute(
        select(Asistencia.inscripcion_id, Asistencia.sesion_id, Asistencia.estado).where(
            Asistencia.inscripcion_id.in_(ids)
        )
    ).all():
        asistencias[a.inscripcion_id][a.sesion_id] = a.estado
    realizadas = sesiones_realizadas(db, taller.id)
    riesgo = obtener(db, Parametro.UMBRAL_RIESGO_PCT)
    filas = [
        FilaResumen(
            i,
            calc.calcular(
                sesiones_realizadas=realizadas,
                periodos=calc.periodos_desde_movimientos(movimientos[i.id]),
                asistencias=asistencias[i.id],
                umbral_aptitud=taller.umbral_aptitud,
                umbral_riesgo_pct=riesgo,
            ),
        )
        for i in inscripciones
    ]
    return sorted(
        filas,
        key=lambda f: (f.inscripcion.estudiante.apellido_paterno, f.inscripcion.estudiante.apellido_materno or "",
                       f.inscripcion.estudiante.nombres),
    )
