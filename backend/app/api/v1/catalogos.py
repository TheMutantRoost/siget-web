"""Catálogos: lectura para usuarios autenticados, escritura solo del administrador."""
from fastapi import APIRouter

from app.api.deps import Ctx, CtxAdmin
from app.models import Ambiente, Area, Carrera, CicloAcademico, Facultad, Sede, TipoDocumento
from app.schemas.catalogos import (
    AmbienteEntrada,
    AmbienteSalida,
    AreaEntrada,
    AreaSalida,
    CarreraEntrada,
    CarreraSalida,
    CicloEntrada,
    CicloSalida,
    FacultadEntrada,
    FacultadSalida,
    SedeEntrada,
    SedeSalida,
    TipoDocumentoSalida,
)
from app.services import catalogo_service as svc

router = APIRouter(prefix="/catalogos", tags=["catálogos"])


@router.get("/tipos-documento", response_model=list[TipoDocumentoSalida])
def tipos_documento(ctx: Ctx) -> list[TipoDocumento]:
    return svc.listar(ctx.db, TipoDocumento)


@router.get("/sedes", response_model=list[SedeSalida])
def sedes(ctx: Ctx) -> list[Sede]:
    return svc.listar(ctx.db, Sede)


@router.post("/sedes", response_model=SedeSalida, status_code=201)
def crear_sede(datos: SedeEntrada, ctx: CtxAdmin) -> Sede:
    return svc.crear(ctx, Sede, datos.model_dump())


@router.put("/sedes/{id_}", response_model=SedeSalida)
def editar_sede(id_: int, datos: SedeEntrada, ctx: CtxAdmin) -> Sede:
    return svc.actualizar(ctx, Sede, id_, datos.model_dump())


@router.get("/ambientes", response_model=list[AmbienteSalida])
def ambientes(ctx: Ctx, sede_id: int | None = None) -> list[Ambiente]:
    filas = svc.listar(ctx.db, Ambiente)
    return [a for a in filas if sede_id is None or a.sede_id == sede_id]


@router.post("/ambientes", response_model=AmbienteSalida, status_code=201)
def crear_ambiente(datos: AmbienteEntrada, ctx: CtxAdmin) -> Ambiente:
    return svc.crear(ctx, Ambiente, datos.model_dump())


@router.put("/ambientes/{id_}", response_model=AmbienteSalida)
def editar_ambiente(id_: int, datos: AmbienteEntrada, ctx: CtxAdmin) -> Ambiente:
    return svc.actualizar(ctx, Ambiente, id_, datos.model_dump())


@router.get("/areas", response_model=list[AreaSalida])
def areas(ctx: Ctx) -> list[Area]:
    return svc.listar(ctx.db, Area)


@router.post("/areas", response_model=AreaSalida, status_code=201)
def crear_area(datos: AreaEntrada, ctx: CtxAdmin) -> Area:
    return svc.crear(ctx, Area, datos.model_dump())


@router.put("/areas/{id_}", response_model=AreaSalida)
def editar_area(id_: int, datos: AreaEntrada, ctx: CtxAdmin) -> Area:
    return svc.actualizar(ctx, Area, id_, datos.model_dump())


@router.get("/facultades", response_model=list[FacultadSalida])
def facultades(ctx: Ctx) -> list[Facultad]:
    return svc.listar(ctx.db, Facultad)


@router.post("/facultades", response_model=FacultadSalida, status_code=201)
def crear_facultad(datos: FacultadEntrada, ctx: CtxAdmin) -> Facultad:
    return svc.crear(ctx, Facultad, datos.model_dump())


@router.put("/facultades/{id_}", response_model=FacultadSalida)
def editar_facultad(id_: int, datos: FacultadEntrada, ctx: CtxAdmin) -> Facultad:
    return svc.actualizar(ctx, Facultad, id_, datos.model_dump())


@router.get("/carreras", response_model=list[CarreraSalida])
def carreras(ctx: Ctx) -> list[Carrera]:
    return svc.listar(ctx.db, Carrera)


@router.post("/carreras", response_model=CarreraSalida, status_code=201)
def crear_carrera(datos: CarreraEntrada, ctx: CtxAdmin) -> Carrera:
    return svc.crear(ctx, Carrera, datos.model_dump())


@router.put("/carreras/{id_}", response_model=CarreraSalida)
def editar_carrera(id_: int, datos: CarreraEntrada, ctx: CtxAdmin) -> Carrera:
    return svc.actualizar(ctx, Carrera, id_, datos.model_dump())


@router.get("/ciclos", response_model=list[CicloSalida])
def ciclos(ctx: Ctx) -> list[CicloAcademico]:
    return svc.listar(ctx.db, CicloAcademico)


@router.post("/ciclos", response_model=CicloSalida, status_code=201)
def crear_ciclo(datos: CicloEntrada, ctx: CtxAdmin) -> CicloAcademico:
    return svc.crear(ctx, CicloAcademico, datos.model_dump())


@router.post("/ciclos/{id_}/activar", response_model=CicloSalida)
def activar_ciclo(id_: int, ctx: CtxAdmin) -> CicloAcademico:
    return svc.activar_ciclo(ctx, id_)
