"""Talleres, horarios, sesiones, inscripciones, asistencia y lista de aptos."""
from fastapi import APIRouter, Response
from sqlalchemy import func, select

from app.api.deps import CtxAcademico, CtxAdmin, PaginacionDep
from app.models import EstadoSesion, EstadoTaller, Inscripcion, ListaAptos, Sesion, Taller
from app.repositories import asistencia_repo
from app.schemas.comun import ConMotivo, Pagina
from app.schemas.talleres import (
    AutorizacionSalida,
    AvanceSalida,
    BloqueoEntrada,
    CambioTallerEntrada,
    EstadoTallerEntrada,
    FilaResumenSalida,
    GenerarListaEntrada,
    GuardarAsistencia,
    HojaAsistencia,
    HorariosEntrada,
    InscripcionEntrada,
    InscripcionSalida,
    ListaDetalleSalida,
    ListaSalida,
    MovimientoSalida,
    SesionSalida,
    SesionVencida,
    TallerActualizacion,
    TallerDetalle,
    TallerEntrada,
    TallerSalida,
)
from app.services import aptos_service, asistencia_service, inscripcion_service, taller_service
from app.services.asistencia_service import RegistroEntrada
from app.services.contexto import Contexto
from app.services.taller_service import BloqueHorario

router = APIRouter(tags=["talleres"])


def _detalle(ctx: Contexto, taller: Taller) -> dict:
    conteo = dict(ctx.db.execute(
        select(Sesion.estado, func.count()).where(Sesion.taller_id == taller.id).group_by(Sesion.estado)
    ).all())
    filas = asistencia_repo.resumen_taller(ctx.db, taller)
    base = TallerSalida.model_validate(taller).model_dump()
    return {
        **base,
        "inscritos_activos": len(filas),
        "sesiones_realizadas": conteo.get(EstadoSesion.REALIZADA, 0),
        "sesiones_programadas": conteo.get(EstadoSesion.PROGRAMADA, 0),
        "inscripciones_cerradas": taller_service.inscripciones_cerradas(ctx.db, taller.id),
        "en_riesgo": any(f.resultado.en_riesgo for f in filas),
    }


# ---------- Talleres ----------

@router.get("/talleres", response_model=Pagina[TallerSalida])
def listar_talleres(
    ctx: CtxAcademico, pag: PaginacionDep, sede_id: int | None = None, ciclo_id: int | None = None,
    estado: EstadoTaller | None = None, texto: str | None = None,
) -> dict:
    filas, total = taller_service.listar(
        ctx, sede_id=sede_id, ciclo_id=ciclo_id, estado=estado, texto=texto, offset=pag.offset, limite=pag.tamano
    )
    return {"items": filas, "total": total, "pagina": pag.pagina, "tamano": pag.tamano}


@router.post("/talleres", response_model=TallerDetalle, status_code=201)
def crear_taller(datos: TallerEntrada, ctx: CtxAdmin) -> dict:
    valores = datos.model_dump(exclude={"justificacion_area"})
    taller = taller_service.crear(ctx, valores, datos.justificacion_area)
    return _detalle(ctx, taller)


@router.get("/talleres/{taller_id}", response_model=TallerDetalle)
def ver_taller(taller_id: int, ctx: CtxAcademico) -> dict:
    taller = taller_service.obtener_taller(ctx.db, taller_id)
    taller_service.verificar_acceso(ctx, taller)
    return _detalle(ctx, taller)


@router.patch("/talleres/{taller_id}", response_model=TallerDetalle)
def editar_taller(taller_id: int, datos: TallerActualizacion, ctx: CtxAdmin) -> dict:
    valores = datos.model_dump(exclude_unset=True, exclude={"justificacion_area"})
    taller = taller_service.actualizar(ctx, taller_id, valores, datos.justificacion_area)
    return _detalle(ctx, taller)


@router.post("/talleres/{taller_id}/estado", response_model=TallerDetalle)
def cambiar_estado(taller_id: int, datos: EstadoTallerEntrada, ctx: CtxAdmin) -> dict:
    return _detalle(ctx, taller_service.cambiar_estado(ctx, taller_id, datos.estado, datos.motivo))


@router.post("/talleres/{taller_id}/bloqueo-inscripciones", response_model=TallerDetalle)
def bloqueo(taller_id: int, datos: BloqueoEntrada, ctx: CtxAdmin) -> dict:
    return _detalle(ctx, taller_service.bloquear_inscripciones(ctx, taller_id, datos.bloquear, datos.motivo))


@router.put("/talleres/{taller_id}/horarios", response_model=TallerDetalle)
def fijar_horarios(taller_id: int, datos: HorariosEntrada, ctx: CtxAdmin) -> dict:
    bloques = [BloqueHorario(b.dia_semana, b.hora_inicio, b.hora_fin, b.ambiente_id) for b in datos.bloques]
    return _detalle(ctx, taller_service.fijar_horarios(ctx, taller_id, bloques, datos.motivo))


@router.post("/talleres/{taller_id}/regenerar-sesiones", response_model=TallerDetalle)
def regenerar(taller_id: int, ctx: CtxAdmin) -> dict:
    taller_service.generar_sesiones(ctx, taller_id)
    return _detalle(ctx, taller_service.obtener_taller(ctx.db, taller_id))


# ---------- Sesiones ----------

@router.get("/talleres/{taller_id}/sesiones", response_model=list[SesionSalida])
def sesiones(taller_id: int, ctx: CtxAcademico) -> list[Sesion]:
    return taller_service.listar_sesiones(ctx, taller_id)


@router.post("/sesiones/{sesion_id}/cancelar", response_model=SesionSalida)
def cancelar(sesion_id: int, datos: ConMotivo, ctx: CtxAcademico) -> Sesion:
    return taller_service.cancelar_sesion(ctx, sesion_id, datos.motivo)


@router.get("/sesiones/vencidas", response_model=list[SesionVencida])
def vencidas(ctx: CtxAdmin, sede_id: int | None = None) -> list[dict]:
    return [
        {"sesion_id": s.id, "taller_id": s.taller_id, "taller": f"{s.taller.codigo} {s.taller.nombre}",
         "numero": s.numero_sesion, "fecha": s.fecha.isoformat(), "inicio": f"{s.hora_inicio:%H:%M}",
         "fin": f"{s.hora_fin:%H:%M}"}
        for s in taller_service.sesiones_vencidas(ctx.db, ctx.reloj.hoy(), sede_id)
    ]


# ---------- Inscripciones ----------

@router.get("/talleres/{taller_id}/inscripciones", response_model=list[InscripcionSalida])
def inscritos(taller_id: int, ctx: CtxAcademico) -> list[Inscripcion]:
    taller_service.verificar_acceso(ctx, taller_service.obtener_taller(ctx.db, taller_id))
    filas = list(ctx.db.scalars(select(Inscripcion).where(Inscripcion.taller_id == taller_id)))
    return sorted(filas, key=lambda i: (i.estado.value, i.estudiante.apellido_paterno, i.estudiante.nombres))


@router.post("/talleres/{taller_id}/inscripciones", response_model=InscripcionSalida, status_code=201)
def inscribir(taller_id: int, datos: InscripcionEntrada, ctx: CtxAdmin) -> Inscripcion:
    return inscripcion_service.inscribir(ctx, taller_id, datos.estudiante_id, datos.motivo)


@router.post("/inscripciones/{inscripcion_id}/retirar", response_model=InscripcionSalida)
def retirar(inscripcion_id: int, datos: ConMotivo, ctx: CtxAdmin) -> Inscripcion:
    return inscripcion_service.retirar(ctx, inscripcion_id, datos.motivo)


@router.post("/inscripciones/{inscripcion_id}/cambiar-taller", response_model=InscripcionSalida)
def cambiar_taller(inscripcion_id: int, datos: CambioTallerEntrada, ctx: CtxAdmin) -> Inscripcion:
    return inscripcion_service.cambiar_taller(ctx, inscripcion_id, datos.taller_destino_id, datos.motivo)


@router.get("/inscripciones/{inscripcion_id}/movimientos", response_model=list[MovimientoSalida])
def movimientos(inscripcion_id: int, ctx: CtxAdmin) -> list:
    return inscripcion_service.listar_movimientos(ctx.db, inscripcion_id)


# ---------- Asistencia ----------

@router.get("/sesiones/{sesion_id}/asistencia", response_model=HojaAsistencia)
def hoja(sesion_id: int, ctx: CtxAcademico) -> dict:
    sesion, inscritos_activos, registros, estado = asistencia_service.hoja(ctx, sesion_id)
    return {
        "sesion": sesion, "taller_id": sesion.taller_id,
        "taller": f"{sesion.taller.codigo} {sesion.taller.nombre}",
        "congelada": estado.congelada, "primer_registro": estado.primer_registro,
        "puede_editar": estado.puede_editar, "motivo_bloqueo": estado.motivo,
        "filas": [
            {"inscripcion_id": i.id, "estudiante": i.estudiante,
             "estado": registros[i.id].estado if i.id in registros else None,
             "observacion": registros[i.id].observacion if i.id in registros else None}
            for i in inscritos_activos
        ],
    }


@router.put("/sesiones/{sesion_id}/asistencia", response_model=SesionSalida)
def guardar_asistencia(sesion_id: int, datos: GuardarAsistencia, ctx: CtxAcademico) -> Sesion:
    registros = [RegistroEntrada(r.inscripcion_id, r.estado, r.observacion) for r in datos.registros]
    return asistencia_service.guardar(ctx, sesion_id, registros)


@router.post("/sesiones/{sesion_id}/autorizar-edicion", response_model=AutorizacionSalida, status_code=201)
def autorizar(sesion_id: int, datos: ConMotivo, ctx: CtxAdmin) -> object:
    return asistencia_service.autorizar_edicion(ctx, sesion_id, datos.motivo)


@router.get("/talleres/{taller_id}/resumen-asistencia", response_model=list[FilaResumenSalida])
def resumen(taller_id: int, ctx: CtxAcademico) -> list[dict]:
    taller, filas, _ = aptos_service.avance(ctx, taller_id)
    return [{"inscripcion_id": f.inscripcion.id, "estudiante": f.inscripcion.estudiante,
             "resultado": f.resultado.__dict__} for f in filas]


# ---------- Lista de aptos ----------

@router.get("/talleres/{taller_id}/aptos/avance", response_model=AvanceSalida)
def avance(taller_id: int, ctx: CtxAcademico) -> dict:
    taller, filas, disp = aptos_service.avance(ctx, taller_id)
    return {
        "taller_id": taller.id, "umbral_aptitud": taller.umbral_aptitud, "puede_generar": disp.puede_generar,
        "definitivo": disp.puede_generar, "sesiones_programadas": disp.programadas,
        "sesiones_realizadas": disp.realizadas, "motivo": disp.motivo,
        "filas": [{"inscripcion_id": f.inscripcion.id, "estudiante": f.inscripcion.estudiante,
                   "resultado": f.resultado.__dict__} for f in filas],
    }


@router.get("/talleres/{taller_id}/aptos", response_model=list[ListaSalida])
def listas(taller_id: int, ctx: CtxAdmin) -> list[ListaAptos]:
    return aptos_service.listar(ctx, taller_id)


@router.post("/talleres/{taller_id}/aptos", response_model=ListaDetalleSalida, status_code=201)
def generar(taller_id: int, datos: GenerarListaEntrada, ctx: CtxAdmin) -> ListaAptos:
    return aptos_service.generar(ctx, taller_id, {e.estudiante_id: e.motivo for e in datos.exclusiones})


@router.get("/aptos/{lista_id}", response_model=ListaDetalleSalida)
def ver_lista(lista_id: int, ctx: CtxAdmin) -> ListaAptos:
    return aptos_service.obtener_lista(ctx, lista_id)


@router.post("/aptos/{lista_id}/anular", response_model=ListaSalida)
def anular(lista_id: int, datos: ConMotivo, ctx: CtxAdmin) -> ListaAptos:
    return aptos_service.anular(ctx, lista_id, datos.motivo)


@router.get("/aptos/{lista_id}/excel")
def exportar(lista_id: int, ctx: CtxAdmin) -> Response:
    nombre, contenido = aptos_service.exportar_excel(ctx, lista_id)
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )

