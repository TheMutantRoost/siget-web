"""Indicadores del inicio, filtrados por sede y por permisos del usuario."""
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import func, select

from app.models import (
    Docente,
    EstadoEstudiante,
    EstadoInscripcion,
    EstadoTaller,
    Estudiante,
    Inscripcion,
    Taller,
)
from app.repositories import asistencia_repo
from app.services import taller_service
from app.services.contexto import Contexto


@dataclass
class TallerIndicador:
    id: int
    codigo: str
    nombre: str
    sede: str
    fecha_fin: str
    inscritos: int
    en_riesgo: int
    porcentaje_promedio: float | None


@dataclass
class Dashboard:
    estudiantes_activos: int = 0
    docentes_activos: int = 0
    talleres_activos: int = 0
    talleres_finalizados: int = 0
    inscripciones_activas: int = 0
    asistencia_general: float | None = None
    aptos: int = 0
    no_aptos: int = 0
    estudiantes_en_riesgo: int = 0
    talleres_en_riesgo: list[TallerIndicador] = field(default_factory=list)
    proximos_a_finalizar: list[TallerIndicador] = field(default_factory=list)
    sesiones_vencidas: list[dict] = field(default_factory=list)


def construir(ctx: Contexto, sede_id: int | None) -> Dashboard:
    tablero = Dashboard()
    if not (ctx.actor.es_admin or ctx.actor.es_docente):
        return tablero  # el operador solo ve su módulo de bienes
    db = ctx.db
    talleres_q = select(Taller)
    if sede_id:
        talleres_q = talleres_q.where(Taller.sede_id == sede_id)
    if ctx.actor.es_docente:
        talleres_q = talleres_q.join(Docente, Docente.id == Taller.docente_id).where(
            Docente.usuario_id == ctx.actor.usuario_id
        )
    talleres = list(db.scalars(talleres_q))
    ids = [t.id for t in talleres]
    tablero.talleres_activos = sum(t.estado == EstadoTaller.ACTIVO for t in talleres)
    tablero.talleres_finalizados = sum(t.estado == EstadoTaller.FINALIZADO for t in talleres)
    if ctx.actor.es_admin:
        tablero.estudiantes_activos = db.scalar(
            select(func.count()).where(Estudiante.estado == EstadoEstudiante.ACTIVO)
        ) or 0
        tablero.docentes_activos = db.scalar(select(func.count()).where(Docente.activo.is_(True))) or 0
    if ids:
        tablero.inscripciones_activas = db.scalar(
            select(func.count()).where(Inscripcion.taller_id.in_(ids), Inscripcion.estado == EstadoInscripcion.ACTIVO)
        ) or 0
    hoy = ctx.reloj.hoy()
    validas = correspondientes = 0
    for t in talleres:
        if t.estado == EstadoTaller.SUSPENDIDO:
            continue
        filas = asistencia_repo.resumen_taller(db, t)
        calculables = [f.resultado for f in filas if f.resultado.calculable]
        validas += sum(r.validas for r in calculables)
        correspondientes += sum(r.sesiones_correspondientes for r in calculables)
        riesgo = sum(1 for r in calculables if r.en_riesgo)
        tablero.aptos += sum(1 for r in calculables if r.apto)
        tablero.no_aptos += sum(1 for r in calculables if r.apto is False)
        tablero.estudiantes_en_riesgo += riesgo
        indicador = TallerIndicador(
            id=t.id, codigo=t.codigo, nombre=t.nombre, sede=t.sede.nombre, fecha_fin=t.fecha_fin.isoformat(),
            inscritos=len(filas), en_riesgo=riesgo,
            porcentaje_promedio=round(sum(float(r.porcentaje) for r in calculables) / len(calculables), 1)
            if calculables else None,
        )
        if riesgo and t.estado == EstadoTaller.ACTIVO:
            tablero.talleres_en_riesgo.append(indicador)
        if t.estado == EstadoTaller.ACTIVO and hoy <= t.fecha_fin <= hoy + timedelta(days=14):
            tablero.proximos_a_finalizar.append(indicador)
    if correspondientes:
        tablero.asistencia_general = round(validas * 100 / correspondientes, 1)
    if ctx.actor.es_admin:
        tablero.sesiones_vencidas = [
            {"sesion_id": s.id, "taller_id": s.taller_id, "taller": f"{s.taller.codigo} {s.taller.nombre}",
             "numero": s.numero_sesion, "fecha": s.fecha.isoformat(),
             "inicio": f"{s.hora_inicio:%H:%M}", "fin": f"{s.hora_fin:%H:%M}"}
            for s in taller_service.sesiones_vencidas(db, hoy, sede_id)
        ]
    return tablero
