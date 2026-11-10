"""Lista de aptos: avance informativo, generación inmutable, anulación con versión y Excel."""
from dataclasses import dataclass
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import func, select

from app.core.errores import ConflictoError, NoEncontradoError, ReglaNegocioError
from app.models import EstadoLista, EstadoSesion, ListaAptos, ListaAptosDetalle, Sesion, Taller
from app.repositories import asistencia_repo
from app.services import auditoria_service, taller_service
from app.services.contexto import Contexto
from app.services.excel import celda_segura


@dataclass(frozen=True)
class Disponibilidad:
    puede_generar: bool
    programadas: int
    realizadas: int
    motivo: str | None


def disponibilidad(ctx: Contexto, taller: Taller) -> Disponibilidad:
    conteo = dict(ctx.db.execute(
        select(Sesion.estado, func.count()).where(Sesion.taller_id == taller.id).group_by(Sesion.estado)
    ).all())
    programadas = conteo.get(EstadoSesion.PROGRAMADA, 0)
    realizadas = conteo.get(EstadoSesion.REALIZADA, 0)
    motivo = None
    if realizadas == 0:
        motivo = "El taller no tiene sesiones realizadas."
    elif programadas:
        motivo = f"Quedan {programadas} sesiones programadas; el resultado aún no es definitivo."
    return Disponibilidad(motivo is None, programadas, realizadas, motivo)


def avance(ctx: Contexto, taller_id: int) -> tuple[Taller, list[asistencia_repo.FilaResumen], Disponibilidad]:
    taller = taller_service.obtener_taller(ctx.db, taller_id)
    taller_service.verificar_acceso(ctx, taller)
    return taller, asistencia_repo.resumen_taller(ctx.db, taller), disponibilidad(ctx, taller)


def generar(ctx: Contexto, taller_id: int, exclusiones: dict[int, str]) -> ListaAptos:
    taller = taller_service.bloquear_taller(ctx.db, taller_id)
    estado = disponibilidad(ctx, taller)
    if not estado.puede_generar:
        raise ReglaNegocioError(estado.motivo or "No se puede generar la lista.")
    if ctx.db.scalar(select(ListaAptos.id).where(ListaAptos.taller_id == taller.id, ListaAptos.estado == EstadoLista.VIGENTE)):
        raise ConflictoError("Ya existe una lista vigente. Anúlela con motivo para generar una nueva versión.")
    filas = asistencia_repo.resumen_taller(ctx.db, taller)
    ids_validos = {f.inscripcion.estudiante_id for f in filas}
    desconocidos = set(exclusiones) - ids_validos
    if desconocidos:
        raise ReglaNegocioError("Se excluyó a estudiantes que no están inscritos en el taller.")
    for motivo in exclusiones.values():
        if not motivo or len(motivo.strip()) < 3:
            raise ReglaNegocioError("Cada exclusión manual requiere un motivo.")
    version = (ctx.db.scalar(select(func.max(ListaAptos.version)).where(ListaAptos.taller_id == taller.id)) or 0) + 1
    lista = ListaAptos(
        taller_id=taller.id, version=version, estado=EstadoLista.VIGENTE,
        umbral_aplicado=taller.umbral_aptitud, sesiones_realizadas=estado.realizadas,
        total_inscritos=len(filas), total_aptos=0, total_excluidos=len(exclusiones),
        generada_por=ctx.actor.usuario_id, generada_en=ctx.reloj.ahora(),
    )
    ctx.db.add(lista)
    ctx.db.flush()
    aptos = 0
    for f in filas:
        e = f.inscripcion.estudiante
        excluido = e.id in exclusiones
        es_apto = bool(f.resultado.apto) and not excluido
        aptos += es_apto
        ctx.db.add(ListaAptosDetalle(
            lista_id=lista.id, estudiante_id=e.id, tipo_documento=e.tipo_documento.nombre,
            numero_documento=e.numero_documento, codigo_universitario=e.codigo_universitario,
            nombres=e.nombres, apellido_paterno=e.apellido_paterno, apellido_materno=e.apellido_materno,
            carrera=e.carrera.nombre, sesiones_correspondientes=f.resultado.sesiones_correspondientes,
            sesiones_validas=f.resultado.validas, porcentaje=f.resultado.porcentaje, es_apto=es_apto,
            excluido_manual=excluido, motivo_exclusion=exclusiones.get(e.id),
        ))
    lista.total_aptos = aptos
    ctx.db.flush()
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="aptos", evento="lista_generada", accion="crear",
        entidad="listas_aptos", registro_id=lista.id,
        despues={"taller_id": taller.id, "version": version, "aptos": aptos,
                 "inscritos": len(filas), "exclusiones": exclusiones},
    )
    return lista


def obtener_lista(ctx: Contexto, lista_id: int) -> ListaAptos:
    lista = ctx.db.get(ListaAptos, lista_id)
    if lista is None:
        raise NoEncontradoError("Lista no encontrada.")
    taller_service.verificar_acceso(ctx, lista.taller)
    return lista


def listar(ctx: Contexto, taller_id: int) -> list[ListaAptos]:
    taller_service.verificar_acceso(ctx, taller_service.obtener_taller(ctx.db, taller_id))
    return list(ctx.db.scalars(
        select(ListaAptos).where(ListaAptos.taller_id == taller_id).order_by(ListaAptos.version.desc())
    ))


def anular(ctx: Contexto, lista_id: int, motivo: str) -> ListaAptos:
    lista = obtener_lista(ctx, lista_id)
    taller_service.bloquear_taller(ctx.db, lista.taller_id)
    if lista.estado != EstadoLista.VIGENTE:
        raise ReglaNegocioError("La lista ya está anulada.")
    lista.estado = EstadoLista.ANULADA
    lista.motivo_anulacion = motivo
    lista.anulada_por = ctx.actor.usuario_id
    lista.anulada_en = ctx.reloj.ahora()
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="aptos", evento="lista_anulada", accion="modificar",
        entidad="listas_aptos", registro_id=lista.id, despues={"motivo": motivo},
    )
    return lista


def exportar_excel(ctx: Contexto, lista_id: int) -> tuple[str, bytes]:
    lista = obtener_lista(ctx, lista_id)
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Aptos"
    t = lista.taller
    hoja.append([celda_segura(f"Relación de estudiantes aptos – {t.codigo} {t.nombre}")])
    hoja["A1"].font = Font(bold=True, size=13)
    hoja.append([celda_segura(f"Versión {lista.version} ({lista.estado.value}) · generada el {lista.generada_en:%d/%m/%Y %H:%M} · umbral {lista.umbral_aplicado} %")])
    hoja.append([])
    encabezado = ["N.°", "Tipo doc.", "N.° documento", "Código", "Apellido paterno", "Apellido materno",
                  "Nombres", "Carrera", "Sesiones", "Válidas", "% asistencia", "Condición", "Observación"]
    hoja.append(encabezado)
    for celda in hoja[4]:
        celda.font = Font(bold=True)
    for n, d in enumerate(lista.detalle, start=1):
        condicion = "Excluido" if d.excluido_manual else ("Apto" if d.es_apto else "No apto")
        hoja.append([n] + [celda_segura(v) for v in (
            d.tipo_documento, d.numero_documento, d.codigo_universitario, d.apellido_paterno,
            d.apellido_materno or "", d.nombres, d.carrera)] + [
            d.sesiones_correspondientes, d.sesiones_validas, float(d.porcentaje), condicion,
            celda_segura(d.motivo_exclusion or "")])
    for columna, ancho in zip("ABCDEFGHIJKLM", (5, 18, 14, 12, 18, 18, 22, 30, 9, 9, 12, 10, 30)):
        hoja.column_dimensions[columna].width = ancho
    salida = BytesIO()
    libro.save(salida)
    return f"aptos_{t.codigo}_v{lista.version}.xlsx", salida.getvalue()
