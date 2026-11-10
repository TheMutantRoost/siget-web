"""Dashboard, auditoría y parámetros del sistema."""
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import Ctx, CtxAdmin, PaginacionDep
from app.schemas.comun import Esquema, Pagina
from app.services import auditoria_service, dashboard_service, parametros_service

router = APIRouter(tags=["sistema"])


class TallerIndicadorSalida(BaseModel):
    id: int
    codigo: str
    nombre: str
    sede: str
    fecha_fin: str
    inscritos: int
    en_riesgo: int
    porcentaje_promedio: float | None


class DashboardSalida(BaseModel):
    estudiantes_activos: int
    docentes_activos: int
    talleres_activos: int
    talleres_finalizados: int
    inscripciones_activas: int
    asistencia_general: float | None
    aptos: int
    no_aptos: int
    estudiantes_en_riesgo: int
    talleres_en_riesgo: list[TallerIndicadorSalida]
    proximos_a_finalizar: list[TallerIndicadorSalida]
    sesiones_vencidas: list[dict]


class AuditoriaSalida(Esquema):
    id: int
    usuario_id: int | None
    ip: str | None
    modulo: str
    evento: str
    accion: str
    entidad: str | None
    registro_id: str | None
    datos_anteriores: dict | None
    datos_nuevos: dict | None
    created_at: datetime


class ParametroSalida(Esquema):
    clave: str
    valor: int
    minimo: int
    maximo: int
    descripcion: str
    updated_at: datetime


class ParametroEntrada(BaseModel):
    valor: int


@router.get("/dashboard", response_model=DashboardSalida)
def dashboard(ctx: Ctx, sede_id: int | None = None) -> object:
    return dashboard_service.construir(ctx, sede_id)


@router.get("/auditoria", response_model=Pagina[AuditoriaSalida])
def auditoria(ctx: CtxAdmin, pag: PaginacionDep, modulo: str | None = None, usuario_id: int | None = None) -> dict:
    filas, total = auditoria_service.listar(
        ctx.db, modulo=modulo, usuario_id=usuario_id, pagina=pag.pagina, tamano=pag.tamano
    )
    return {"items": filas, "total": total, "pagina": pag.pagina, "tamano": pag.tamano}


@router.get("/parametros", response_model=list[ParametroSalida])
def parametros(ctx: CtxAdmin) -> list:
    return parametros_service.listar(ctx.db)


@router.put("/parametros/{clave}", response_model=ParametroSalida)
def actualizar_parametro(clave: str, datos: ParametroEntrada, ctx: CtxAdmin) -> object:
    return parametros_service.actualizar(ctx, clave, datos.valor)
