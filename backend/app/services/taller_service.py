"""Talleres, bloques horarios, generación de sesiones, cancelación e indicadores."""
from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Any

from sqlalchemy import delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errores import ConflictoError, NoEncontradoError, PermisoDenegadoError, ReglaNegocioError
from app.models import (
    Ambiente,
    Area,
    Asistencia,
    CicloAcademico,
    Docente,
    EstadoInscripcion,
    EstadoRegistro,
    EstadoSesion,
    EstadoTaller,
    HistorialHorario,
    HorarioTaller,
    Inscripcion,
    Sede,
    Sesion,
    Taller,
)
from app.services import auditoria_service, disponibilidad_service, persona_service
from app.services.contexto import Contexto
from app.services.disponibilidad_service import Ocurrencia
from app.services.parametros_service import Parametro, obtener


@dataclass(frozen=True)
class BloqueHorario:
    dia_semana: int
    hora_inicio: time
    hora_fin: time
    ambiente_id: int | None = None


# ---------- Consultas y permisos ----------

def obtener_taller(db: Session, taller_id: int) -> Taller:
    taller = db.get(Taller, taller_id)
    if taller is None:
        raise NoEncontradoError("Taller no encontrado.")
    return taller


def verificar_acceso(ctx: Contexto, taller: Taller) -> None:
    """El docente solo ve sus talleres; el operador no accede a talleres."""
    if ctx.actor.es_admin:
        return
    if ctx.actor.es_docente and taller.docente.usuario_id == ctx.actor.usuario_id:
        return
    raise PermisoDenegadoError("No tiene acceso a este taller.")


def bloquear_taller(db: Session, taller_id: int) -> Taller:
    taller = db.scalar(select(Taller).where(Taller.id == taller_id).with_for_update())
    if taller is None:
        raise NoEncontradoError("Taller no encontrado.")
    return taller


def contar_realizadas(db: Session, taller_id: int) -> int:
    return db.scalar(
        select(func.count()).where(Sesion.taller_id == taller_id, Sesion.estado == EstadoSesion.REALIZADA)
    ) or 0


def contar_inscritos_activos(db: Session, taller_id: int) -> int:
    return db.scalar(
        select(func.count()).where(
            Inscripcion.taller_id == taller_id, Inscripcion.estado == EstadoInscripcion.ACTIVO
        )
    ) or 0


def inscripciones_cerradas(db: Session, taller_id: int) -> bool:
    return contar_realizadas(db, taller_id) >= obtener(db, Parametro.SESIONES_CIERRE_INSCRIPCION)


def listar(
    ctx: Contexto, *, sede_id: int | None, ciclo_id: int | None, estado: EstadoTaller | None,
    texto: str | None, offset: int, limite: int,
) -> tuple[list[Taller], int]:
    consulta = select(Taller)
    if ctx.actor.es_docente:
        consulta = consulta.join(Docente, Docente.id == Taller.docente_id).where(
            Docente.usuario_id == ctx.actor.usuario_id
        )
    elif not ctx.actor.es_admin:
        raise PermisoDenegadoError("No tiene acceso a talleres.")
    if sede_id:
        consulta = consulta.where(Taller.sede_id == sede_id)
    if ciclo_id:
        consulta = consulta.where(Taller.ciclo_academico_id == ciclo_id)
    if estado:
        consulta = consulta.where(Taller.estado == estado)
    if texto:
        patron = f"%{texto.strip()}%"
        consulta = consulta.where(Taller.nombre.like(patron) | Taller.codigo.like(patron))
    total = ctx.db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    filas = ctx.db.scalars(consulta.order_by(Taller.fecha_inicio.desc(), Taller.codigo).offset(offset).limit(limite)).all()
    return list(filas), total


# ---------- Validaciones ----------

def _validar_ambiente(db: Session, ambiente_id: int | None, sede_id: int, cupo: int) -> None:
    if ambiente_id is None:
        return
    ambiente = db.get(Ambiente, ambiente_id)
    if ambiente is None or ambiente.estado != EstadoRegistro.ACTIVO:
        raise ReglaNegocioError("El ambiente no existe o está inactivo.")
    if ambiente.sede_id != sede_id:
        raise ReglaNegocioError("El ambiente pertenece a otra sede distinta a la del taller.")
    if ambiente.capacidad is not None and cupo > ambiente.capacidad:
        raise ReglaNegocioError(
            f"El cupo ({cupo}) supera la capacidad del ambiente {ambiente.codigo} ({ambiente.capacidad})."
        )


def _validar_basicos(db: Session, datos: dict[str, Any]) -> tuple[Docente, Sede]:
    if datos["fecha_fin"] < datos["fecha_inicio"]:
        raise ReglaNegocioError("La fecha de fin debe ser igual o posterior a la de inicio.")
    if not 50 <= datos["umbral_aptitud"] <= 100:
        raise ReglaNegocioError("El umbral de aptitud debe estar entre 50 y 100.")
    area = db.get(Area, datos["area_id"])
    if area is None or not area.activo:
        raise ReglaNegocioError("El área no existe o está inactiva.")
    ciclo = db.get(CicloAcademico, datos["ciclo_academico_id"])
    if ciclo is None:
        raise ReglaNegocioError("El ciclo académico no existe.")
    sede = db.get(Sede, datos["sede_id"])
    if sede is None or sede.estado != EstadoRegistro.ACTIVO:
        raise ReglaNegocioError("La sede no existe o está inactiva.")
    docente = persona_service.obtener_docente(db, datos["docente_id"])
    _validar_ambiente(db, datos.get("ambiente_id"), sede.id, datos["cupo_maximo"])
    return docente, sede


# ---------- Altas y cambios ----------

def crear(ctx: Contexto, datos: dict[str, Any], justificacion_area: str | None) -> Taller:
    docente, _ = _validar_basicos(ctx.db, datos)
    disponibilidad_service.bloquear_filas(ctx.db, Docente, [docente.id])
    usa_excepcion = disponibilidad_service.validar_area(ctx, docente, datos["area_id"], None, justificacion_area)
    taller = Taller(**datos, estado=EstadoTaller.ACTIVO, inscripciones_bloqueadas=False)
    taller.codigo = taller.codigo.strip().upper()
    ctx.db.add(taller)
    try:
        ctx.db.flush()
    except IntegrityError as exc:
        raise ConflictoError("Ya existe un taller con ese código.") from exc
    if usa_excepcion:
        disponibilidad_service.registrar_excepcion_area(ctx, docente.id, datos["area_id"], taller.id, justificacion_area or "")
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="talleres", evento="taller_creado", accion="crear",
        entidad="talleres", registro_id=taller.id, despues=datos,
    )
    return taller


def actualizar(ctx: Contexto, taller_id: int, datos: dict[str, Any], justificacion_area: str | None) -> Taller:
    taller = bloquear_taller(ctx.db, taller_id)
    if taller.estado == EstadoTaller.FINALIZADO:
        raise ReglaNegocioError("Un taller finalizado no se puede modificar.")
    antes = {k: getattr(taller, k) for k in datos}
    if "cupo_maximo" in datos and datos["cupo_maximo"] < contar_inscritos_activos(ctx.db, taller.id):
        raise ReglaNegocioError("El cupo no puede ser menor que la cantidad de inscritos activos.")
    if "umbral_aptitud" in datos and not 50 <= datos["umbral_aptitud"] <= 100:
        raise ReglaNegocioError("El umbral de aptitud debe estar entre 50 y 100.")
    cupo = datos.get("cupo_maximo", taller.cupo_maximo)
    if "ambiente_id" in datos or "cupo_maximo" in datos:
        _validar_ambiente(ctx.db, datos.get("ambiente_id", taller.ambiente_id), taller.sede_id, cupo)
        for bloque in taller.horarios:
            _validar_ambiente(ctx.db, bloque.ambiente_id, taller.sede_id, cupo)
    nuevo_docente_id = datos.get("docente_id", taller.docente_id)
    if nuevo_docente_id != taller.docente_id:
        docente = persona_service.obtener_docente(ctx.db, nuevo_docente_id)
        disponibilidad_service.bloquear_filas(ctx.db, Docente, [docente.id])
        if disponibilidad_service.validar_area(ctx, docente, taller.area_id, taller.id, justificacion_area):
            disponibilidad_service.registrar_excepcion_area(ctx, docente.id, taller.area_id, taller.id, justificacion_area or "")
        futuras = disponibilidad_service.ocurrencias_de_taller(ctx.db, taller.id, ctx.reloj.hoy())
        disponibilidad_service.validar_docente(ctx, docente, futuras, taller.id)
    if "fecha_fin" in datos and datos["fecha_fin"] < taller.fecha_inicio:
        raise ReglaNegocioError("La fecha de fin debe ser igual o posterior a la de inicio.")
    for clave, valor in datos.items():
        setattr(taller, clave, valor)
    ctx.db.flush()
    if "fecha_fin" in datos or "ambiente_id" in datos:
        generar_sesiones(ctx, taller.id)
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="talleres", evento="taller_modificado", accion="modificar",
        entidad="talleres", registro_id=taller.id, antes=antes, despues=datos,
    )
    return taller


def cambiar_estado(ctx: Contexto, taller_id: int, estado: EstadoTaller, motivo: str) -> Taller:
    taller = bloquear_taller(ctx.db, taller_id)
    if taller.estado == EstadoTaller.FINALIZADO:
        raise ReglaNegocioError("El taller ya está finalizado.")
    anterior = taller.estado
    taller.estado = estado
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="talleres", evento="taller_estado", accion="modificar",
        entidad="talleres", registro_id=taller.id, antes={"estado": anterior},
        despues={"estado": estado, "motivo": motivo},
    )
    return taller


def bloquear_inscripciones(ctx: Contexto, taller_id: int, bloquear: bool, motivo: str | None) -> Taller:
    taller = bloquear_taller(ctx.db, taller_id)
    if bloquear and not motivo:
        raise ReglaNegocioError("Indique el motivo del bloqueo.")
    taller.inscripciones_bloqueadas = bloquear
    taller.motivo_bloqueo = motivo if bloquear else None
    taller.bloqueado_por = ctx.actor.usuario_id if bloquear else None
    taller.bloqueado_en = ctx.reloj.ahora() if bloquear else None
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="talleres",
        evento="inscripciones_bloqueadas" if bloquear else "inscripciones_desbloqueadas",
        accion="modificar", entidad="talleres", registro_id=taller.id, despues={"motivo": motivo},
    )
    return taller


# ---------- Horarios y sesiones ----------

def _ocurrencias_desde_bloques(taller: Taller, bloques: list[HorarioTaller], desde: date) -> list[tuple[Ocurrencia, HorarioTaller]]:
    resultado = []
    dia = max(desde, taller.fecha_inicio)
    while dia <= taller.fecha_fin:
        for b in bloques:
            vigente = (b.vigente_desde is None or b.vigente_desde <= dia) and (
                b.vigente_hasta is None or dia <= b.vigente_hasta
            )
            if b.dia_semana == dia.isoweekday() and vigente:
                resultado.append((
                    Ocurrencia(
                        fecha=dia, inicio=b.hora_inicio, fin=b.hora_fin, sede_id=taller.sede_id,
                        sede=taller.sede.nombre, taller_id=taller.id,
                        taller=f"{taller.codigo} {taller.nombre}",
                        ambiente_id=b.ambiente_id or taller.ambiente_id,
                    ),
                    b,
                ))
        dia += timedelta(days=1)
    return resultado


def fijar_horarios(ctx: Contexto, taller_id: int, bloques: list[BloqueHorario], motivo: str | None) -> Taller:
    taller = bloquear_taller(ctx.db, taller_id)
    if taller.estado != EstadoTaller.ACTIVO:
        raise ReglaNegocioError("Solo se programan horarios de talleres activos.")
    if not bloques:
        raise ReglaNegocioError("Indique al menos un bloque horario.")
    for b in bloques:
        if b.hora_fin <= b.hora_inicio:
            raise ReglaNegocioError("En cada bloque la hora final debe ser posterior a la inicial.")
        _validar_ambiente(ctx.db, b.ambiente_id, taller.sede_id, taller.cupo_maximo)
    # Bloques del mismo taller que se solapan entre sí.
    for i, a in enumerate(bloques):
        for b in bloques[i + 1:]:
            if a.dia_semana == b.dia_semana and a.hora_inicio < b.hora_fin and a.hora_fin > b.hora_inicio:
                raise ReglaNegocioError("Dos bloques del taller se solapan el mismo día.")
    for anterior in list(taller.horarios):
        anterior.activo = False
        ctx.db.add(HistorialHorario(
            taller_id=taller.id, horario_id=anterior.id, accion="baja", dia_semana=anterior.dia_semana,
            hora_inicio=anterior.hora_inicio, hora_fin=anterior.hora_fin,
            ambiente_id=anterior.ambiente_id, motivo=motivo, usuario_id=ctx.actor.usuario_id,
        ))
    ctx.db.flush()
    for b in bloques:
        nuevo = HorarioTaller(
            taller_id=taller.id, dia_semana=b.dia_semana, hora_inicio=b.hora_inicio,
            hora_fin=b.hora_fin, ambiente_id=b.ambiente_id, activo=True,
        )
        ctx.db.add(nuevo)
        ctx.db.flush()
        ctx.db.add(HistorialHorario(
            taller_id=taller.id, horario_id=nuevo.id, accion="alta", dia_semana=b.dia_semana,
            hora_inicio=b.hora_inicio, hora_fin=b.hora_fin, ambiente_id=b.ambiente_id,
            motivo=motivo, usuario_id=ctx.actor.usuario_id,
        ))
    ctx.db.flush()
    ctx.db.expire(taller, ["horarios"])
    generar_sesiones(ctx, taller.id)
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="talleres", evento="horario_modificado", accion="modificar",
        entidad="talleres", registro_id=taller.id,
        despues={"bloques": [b.__dict__ for b in bloques], "motivo": motivo},
    )
    return taller


def generar_sesiones(ctx: Contexto, taller_id: int) -> int:
    """Regenera solo sesiones futuras Programadas sin asistencia; la numeración nunca se repite."""
    taller = bloquear_taller(ctx.db, taller_id)
    hoy = ctx.reloj.hoy()
    con_asistencia = exists().where(Asistencia.sesion_id == Sesion.id)
    borrables = ctx.db.scalars(
        select(Sesion.id).where(
            Sesion.taller_id == taller.id,
            Sesion.fecha >= hoy,
            Sesion.estado == EstadoSesion.PROGRAMADA,
            Sesion.sesion_original_id.is_(None),
            ~con_asistencia,
        )
    ).all()
    if borrables:
        ctx.db.execute(delete(Sesion).where(Sesion.id.in_(borrables)))
        ctx.db.flush()
    conservadas = {
        (s.fecha, s.hora_inicio)
        for s in ctx.db.scalars(select(Sesion).where(Sesion.taller_id == taller.id, Sesion.fecha >= hoy))
    }
    # La primera generación cubre todo el taller; las siguientes solo desde hoy.
    hay_sesiones = ctx.db.scalar(select(func.count()).where(Sesion.taller_id == taller.id)) or 0
    desde = hoy if hay_sesiones else taller.fecha_inicio
    nuevas = [
        (oc, b) for oc, b in _ocurrencias_desde_bloques(taller, list(taller.horarios), desde)
        if (oc.fecha, oc.inicio) not in conservadas
    ]
    if nuevas:
        ocurrencias = [oc for oc, _ in nuevas]
        disponibilidad_service.bloquear_filas(ctx.db, Docente, [taller.docente_id])
        disponibilidad_service.bloquear_filas(ctx.db, Ambiente, [oc.ambiente_id for oc in ocurrencias if oc.ambiente_id])
        disponibilidad_service.validar_docente(ctx, taller.docente, ocurrencias, taller.id)
        disponibilidad_service.validar_ambiente(ctx, ocurrencias, taller.id)
        # Los inscritos activos tampoco pueden quedar con cruces.
        for est_id in ctx.db.scalars(
            select(Inscripcion.estudiante_id).where(
                Inscripcion.taller_id == taller.id, Inscripcion.estado == EstadoInscripcion.ACTIVO
            )
        ):
            disponibilidad_service.validar_estudiante(ctx, est_id, taller.id, nuevas=ocurrencias)
    siguiente = (ctx.db.scalar(select(func.max(Sesion.numero_sesion)).where(Sesion.taller_id == taller.id)) or 0) + 1
    for oc, bloque in sorted(nuevas, key=lambda x: (x[0].fecha, x[0].inicio)):
        ctx.db.add(Sesion(
            taller_id=taller.id, numero_sesion=siguiente, horario_id=bloque.id, fecha=oc.fecha,
            hora_inicio=oc.inicio, hora_fin=oc.fin, ambiente_id=oc.ambiente_id,
            estado=EstadoSesion.PROGRAMADA,
        ))
        siguiente += 1
    ctx.db.flush()
    return len(nuevas)


def listar_sesiones(ctx: Contexto, taller_id: int) -> list[Sesion]:
    verificar_acceso(ctx, obtener_taller(ctx.db, taller_id))
    return list(ctx.db.scalars(
        select(Sesion).where(Sesion.taller_id == taller_id).order_by(Sesion.fecha, Sesion.hora_inicio)
    ))


def cancelar_sesion(ctx: Contexto, sesion_id: int, motivo: str) -> Sesion:
    sesion = ctx.db.get(Sesion, sesion_id)
    if sesion is None:
        raise NoEncontradoError("Sesión no encontrada.")
    taller = bloquear_taller(ctx.db, sesion.taller_id)
    verificar_acceso(ctx, taller)
    if ctx.db.scalar(select(func.count()).where(Asistencia.sesion_id == sesion.id)):
        raise ReglaNegocioError("Una sesión con asistencia registrada no puede cancelarse.")
    if sesion.estado != EstadoSesion.PROGRAMADA:
        raise ReglaNegocioError("Solo se pueden cancelar sesiones Programadas.")
    if not ctx.actor.es_admin:
        plazo = obtener(ctx.db, Parametro.PLAZO_REGISTRO_TARDIO_DIAS)
        if ctx.reloj.hoy() > sesion.fecha + timedelta(days=plazo):
            raise PermisoDenegadoError(
                f"Pasaron más de {plazo} días desde la sesión; solo el administrador puede cancelarla."
            )
    sesion.estado = EstadoSesion.CANCELADA
    sesion.motivo_estado = motivo
    sesion.cambiado_por = ctx.actor.usuario_id
    sesion.cambiado_en = ctx.reloj.ahora()
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="sesiones", evento="sesion_cancelada", accion="modificar",
        entidad="sesiones", registro_id=sesion.id,
        antes={"estado": EstadoSesion.PROGRAMADA}, despues={"estado": EstadoSesion.CANCELADA, "motivo": motivo},
    )
    return sesion


def sesiones_vencidas(db: Session, hoy: date, sede_id: int | None = None) -> list[Sesion]:
    consulta = (
        select(Sesion).join(Taller, Taller.id == Sesion.taller_id)
        .where(Sesion.estado == EstadoSesion.PROGRAMADA, Sesion.fecha < hoy, Taller.estado == EstadoTaller.ACTIVO)
    )
    if sede_id:
        consulta = consulta.where(Taller.sede_id == sede_id)
    return list(db.scalars(consulta.order_by(Sesion.fecha)))
