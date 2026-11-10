"""Estudiantes y docentes (cada docente tiene su usuario con rol Docente)."""
from datetime import date, time
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errores import ConflictoError, NoEncontradoError, ReglaNegocioError
from app.models import (
    Area,
    Carrera,
    DisponibilidadDocente,
    Docente,
    DocenteArea,
    EstadoEstudiante,
    Estudiante,
    Inscripcion,
    Rol,
)
from app.services import auditoria_service, catalogo_service, disponibilidad_service, usuario_service
from app.services.contexto import Contexto

CAMPOS_ESTUDIANTE = (
    "tipo_documento_id", "numero_documento", "codigo_universitario", "nombres", "apellido_paterno",
    "apellido_materno", "fecha_nacimiento", "carrera_id", "ciclo_actual", "email", "telefono", "estado",
)


# ---------- Estudiantes ----------

def obtener_estudiante(db: Session, estudiante_id: int) -> Estudiante:
    estudiante = db.get(Estudiante, estudiante_id)
    if estudiante is None:
        raise NoEncontradoError("Estudiante no encontrado.")
    return estudiante


def _validar_estudiante(db: Session, datos: dict[str, Any]) -> dict[str, Any]:
    datos = dict(datos)
    datos["numero_documento"] = catalogo_service.validar_documento(
        db, datos["tipo_documento_id"], datos["numero_documento"]
    )
    datos["codigo_universitario"] = datos["codigo_universitario"].strip().upper()
    carrera = db.get(Carrera, datos["carrera_id"])
    if carrera is None or not carrera.activo:
        raise ReglaNegocioError("La carrera no existe o está inactiva.")
    return datos


def _guardar(ctx: Contexto, mensaje_duplicado: str) -> None:
    try:
        ctx.db.flush()
    except IntegrityError as exc:
        raise ConflictoError(mensaje_duplicado) from exc


def crear_estudiante(ctx: Contexto, datos: dict[str, Any]) -> Estudiante:
    datos = _validar_estudiante(ctx.db, datos)
    estudiante = Estudiante(**datos)
    ctx.db.add(estudiante)
    _guardar(ctx, "Ya existe un estudiante con ese documento o código universitario.")
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="estudiantes", evento="estudiante_creado", accion="crear",
        entidad="estudiantes", registro_id=estudiante.id, despues=datos,
    )
    return estudiante


def actualizar_estudiante(ctx: Contexto, estudiante_id: int, datos: dict[str, Any]) -> Estudiante:
    estudiante = obtener_estudiante(ctx.db, estudiante_id)
    datos = _validar_estudiante(ctx.db, datos)
    antes = {k: getattr(estudiante, k) for k in CAMPOS_ESTUDIANTE}
    for clave, valor in datos.items():
        setattr(estudiante, clave, valor)
    _guardar(ctx, "Ya existe un estudiante con ese documento o código universitario.")
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="estudiantes", evento="estudiante_modificado", accion="modificar",
        entidad="estudiantes", registro_id=estudiante.id, antes=antes, despues=datos,
    )
    return estudiante


def buscar_estudiantes(
    db: Session, *, texto: str | None, carrera_id: int | None, taller_id: int | None,
    estado: EstadoEstudiante | None, offset: int, limite: int,
) -> tuple[list[Estudiante], int]:
    consulta = select(Estudiante)
    if texto:
        patron = f"%{texto.strip()}%"
        consulta = consulta.where(
            or_(
                Estudiante.numero_documento.like(patron),
                Estudiante.codigo_universitario.like(patron),
                Estudiante.nombres.like(patron),
                Estudiante.apellido_paterno.like(patron),
                Estudiante.apellido_materno.like(patron),
            )
        )
    if carrera_id:
        consulta = consulta.where(Estudiante.carrera_id == carrera_id)
    if estado:
        consulta = consulta.where(Estudiante.estado == estado)
    if taller_id:
        consulta = consulta.where(
            Estudiante.id.in_(select(Inscripcion.estudiante_id).where(Inscripcion.taller_id == taller_id))
        )
    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    filas = db.scalars(
        consulta.order_by(Estudiante.apellido_paterno, Estudiante.apellido_materno, Estudiante.nombres)
        .offset(offset).limit(limite)
    ).all()
    return list(filas), total


# ---------- Docentes ----------

def obtener_docente(db: Session, docente_id: int) -> Docente:
    docente = db.get(Docente, docente_id)
    if docente is None:
        raise NoEncontradoError("Docente no encontrado.")
    return docente


def docente_de_usuario(db: Session, usuario_id: int) -> Docente | None:
    return db.scalar(select(Docente).where(Docente.usuario_id == usuario_id))


def _fijar_areas(db: Session, docente: Docente, area_ids: list[int]) -> None:
    areas = list(db.scalars(select(Area).where(Area.id.in_(area_ids), Area.activo.is_(True))))
    if len(areas) != len(set(area_ids)):
        raise ReglaNegocioError("Alguna de las áreas no existe o está inactiva.")
    db.execute(delete(DocenteArea).where(DocenteArea.docente_id == docente.id))
    for area in areas:
        db.add(DocenteArea(docente_id=docente.id, area_id=area.id))


def crear_docente(ctx: Contexto, datos: dict[str, Any]) -> tuple[Docente, str]:
    numero = catalogo_service.validar_documento(
        ctx.db, datos["tipo_documento_id"], datos["numero_documento"]
    )
    usuario, clave = usuario_service.crear(
        ctx,
        username=datos["username"],
        email=datos["email"],
        nombres=datos["nombres"],
        apellido_paterno=datos["apellido_paterno"],
        apellido_materno=datos.get("apellido_materno"),
        rol=Rol.DOCENTE,
    )
    docente = Docente(
        usuario_id=usuario.id,
        tipo_documento_id=datos["tipo_documento_id"],
        numero_documento=numero,
        nombres=datos["nombres"],
        apellido_paterno=datos["apellido_paterno"],
        apellido_materno=datos.get("apellido_materno"),
        email=datos["email"].strip().lower(),
        telefono=datos.get("telefono"),
        activo=True,
    )
    ctx.db.add(docente)
    _guardar(ctx, "Ya existe un docente con ese documento.")
    _fijar_areas(ctx.db, docente, datos.get("area_ids", []))
    ctx.db.flush()
    ctx.db.refresh(docente)
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="docentes", evento="docente_creado", accion="crear",
        entidad="docentes", registro_id=docente.id,
        despues={**{k: v for k, v in datos.items()}, "numero_documento": numero},
    )
    return docente, clave


def actualizar_docente(ctx: Contexto, docente_id: int, datos: dict[str, Any]) -> Docente:
    docente = obtener_docente(ctx.db, docente_id)
    antes = {"areas": [a.id for a in docente.areas], "telefono": docente.telefono, "activo": docente.activo}
    if "area_ids" in datos:
        _fijar_areas(ctx.db, docente, datos["area_ids"])
    for campo in ("nombres", "apellido_paterno", "apellido_materno", "telefono"):
        if campo in datos:
            setattr(docente, campo, datos[campo])
            if campo in ("nombres", "apellido_paterno", "apellido_materno"):
                setattr(docente.usuario, campo, datos[campo])
    if "activo" in datos:
        docente.activo = datos["activo"]
        docente.usuario.activo = datos["activo"]
    ctx.db.flush()
    ctx.db.refresh(docente)
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="docentes", evento="docente_modificado", accion="modificar",
        entidad="docentes", registro_id=docente.id, antes=antes, despues=datos,
    )
    return docente


def fijar_disponibilidad(
    ctx: Contexto, docente_id: int, bloques: list[tuple[int, time, time, date | None, date | None]]
) -> Docente:
    docente = obtener_docente(ctx.db, docente_id)
    disponibilidad_service.bloquear_filas(ctx.db, Docente, [docente.id])
    for dia, inicio, fin, _desde, _hasta in bloques:
        if fin <= inicio:
            raise ReglaNegocioError("La hora final debe ser posterior a la inicial.")
        if not 1 <= dia <= 7:
            raise ReglaNegocioError("Día de la semana inválido.")
    antes = [(d.dia_semana, d.hora_inicio, d.hora_fin) for d in docente.disponibilidad]
    ctx.db.execute(delete(DisponibilidadDocente).where(DisponibilidadDocente.docente_id == docente.id))
    for dia, inicio, fin, desde, hasta in bloques:
        ctx.db.add(DisponibilidadDocente(
            docente_id=docente.id, dia_semana=dia, hora_inicio=inicio, hora_fin=fin,
            vigente_desde=desde, vigente_hasta=hasta,
        ))
    ctx.db.flush()
    ctx.db.expire(docente, ["disponibilidad"])
    # La nueva disponibilidad debe cubrir las sesiones futuras ya asignadas.
    disponibilidad_service.validar_disponibilidad_vigente(ctx, docente)
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="docentes", evento="disponibilidad_modificada", accion="modificar",
        entidad="docentes", registro_id=docente.id, antes={"bloques": antes},
        despues={"bloques": bloques},
    )
    return docente


def listar_docentes(db: Session, area_id: int | None = None, solo_activos: bool = False) -> list[Docente]:
    consulta = select(Docente)
    if area_id:
        consulta = consulta.where(
            Docente.id.in_(select(DocenteArea.docente_id).where(DocenteArea.area_id == area_id))
        )
    if solo_activos:
        consulta = consulta.where(Docente.activo.is_(True))
    return list(db.scalars(consulta.order_by(Docente.apellido_paterno, Docente.nombres)))
