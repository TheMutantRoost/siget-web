"""Estudiantes, docentes y usuarios: módulo del administrador."""
from fastapi import APIRouter

from app.api.deps import CtxAdmin, PaginacionDep
from app.models import Docente, EstadoEstudiante, Estudiante, Usuario
from app.schemas.comun import Mensaje, Pagina
from app.schemas.personas import (
    BloqueDisponibilidad,
    DocenteActualizacion,
    DocenteCreado,
    DocenteEntrada,
    DocenteSalida,
    EstudianteEntrada,
    EstudianteSalida,
    PasswordTemporal,
    UsuarioEntrada,
    UsuarioSalida,
)
from app.schemas.talleres import InscripcionConTaller
from app.services import inscripcion_service, persona_service, usuario_service

router = APIRouter(tags=["personas"])


# ---------- Estudiantes ----------

@router.get("/estudiantes", response_model=Pagina[EstudianteSalida])
def buscar_estudiantes(
    ctx: CtxAdmin, pag: PaginacionDep, texto: str | None = None, carrera_id: int | None = None,
    taller_id: int | None = None, estado: EstadoEstudiante | None = None,
) -> dict:
    filas, total = persona_service.buscar_estudiantes(
        ctx.db, texto=texto, carrera_id=carrera_id, taller_id=taller_id, estado=estado,
        offset=pag.offset, limite=pag.tamano,
    )
    return {"items": filas, "total": total, "pagina": pag.pagina, "tamano": pag.tamano}


@router.post("/estudiantes", response_model=EstudianteSalida, status_code=201)
def crear_estudiante(datos: EstudianteEntrada, ctx: CtxAdmin) -> Estudiante:
    return persona_service.crear_estudiante(ctx, datos.model_dump())


@router.get("/estudiantes/{estudiante_id}", response_model=EstudianteSalida)
def ver_estudiante(estudiante_id: int, ctx: CtxAdmin) -> Estudiante:
    return persona_service.obtener_estudiante(ctx.db, estudiante_id)


@router.put("/estudiantes/{estudiante_id}", response_model=EstudianteSalida)
def editar_estudiante(estudiante_id: int, datos: EstudianteEntrada, ctx: CtxAdmin) -> Estudiante:
    return persona_service.actualizar_estudiante(ctx, estudiante_id, datos.model_dump())


@router.get("/estudiantes/{estudiante_id}/inscripciones", response_model=list[InscripcionConTaller])
def historial_estudiante(estudiante_id: int, ctx: CtxAdmin) -> list[dict]:
    return [
        {"id": i.id, "estado": i.estado, "fecha_inscripcion": i.fecha_inscripcion, "taller_id": i.taller_id,
         "taller_codigo": i.taller.codigo, "taller_nombre": i.taller.nombre}
        for i in inscripcion_service.historial_estudiante(ctx.db, estudiante_id)
    ]


# ---------- Docentes ----------

@router.get("/docentes", response_model=list[DocenteSalida])
def listar_docentes(ctx: CtxAdmin, area_id: int | None = None, solo_activos: bool = False) -> list[Docente]:
    return persona_service.listar_docentes(ctx.db, area_id, solo_activos)


@router.post("/docentes", response_model=DocenteCreado, status_code=201)
def crear_docente(datos: DocenteEntrada, ctx: CtxAdmin) -> dict:
    docente, clave = persona_service.crear_docente(ctx, datos.model_dump())
    return {"docente": docente, "username": docente.usuario.username, "password_temporal": clave}


@router.patch("/docentes/{docente_id}", response_model=DocenteSalida)
def editar_docente(docente_id: int, datos: DocenteActualizacion, ctx: CtxAdmin) -> Docente:
    return persona_service.actualizar_docente(ctx, docente_id, datos.model_dump(exclude_unset=True))


@router.put("/docentes/{docente_id}/disponibilidad", response_model=DocenteSalida)
def fijar_disponibilidad(docente_id: int, bloques: list[BloqueDisponibilidad], ctx: CtxAdmin) -> Docente:
    return persona_service.fijar_disponibilidad(
        ctx, docente_id,
        [(b.dia_semana, b.hora_inicio, b.hora_fin, b.vigente_desde, b.vigente_hasta) for b in bloques],
    )


# ---------- Usuarios ----------

@router.get("/usuarios", response_model=Pagina[UsuarioSalida])
def listar_usuarios(ctx: CtxAdmin, pag: PaginacionDep, texto: str | None = None) -> dict:
    filas, total = usuario_service.listar(ctx.db, texto, pag.offset, pag.tamano)
    return {"items": filas, "total": total, "pagina": pag.pagina, "tamano": pag.tamano}


@router.post("/usuarios", response_model=PasswordTemporal, status_code=201)
def crear_usuario(datos: UsuarioEntrada, ctx: CtxAdmin) -> PasswordTemporal:
    usuario, clave = usuario_service.crear(ctx, **datos.model_dump())
    return PasswordTemporal(username=usuario.username, password_temporal=clave)


@router.post("/usuarios/{usuario_id}/activar", response_model=UsuarioSalida)
def activar(usuario_id: int, ctx: CtxAdmin) -> Usuario:
    return usuario_service.cambiar_activo(ctx, usuario_id, True)


@router.post("/usuarios/{usuario_id}/desactivar", response_model=UsuarioSalida)
def desactivar(usuario_id: int, ctx: CtxAdmin) -> Usuario:
    return usuario_service.cambiar_activo(ctx, usuario_id, False)


@router.post("/usuarios/{usuario_id}/desbloquear", response_model=UsuarioSalida)
def desbloquear(usuario_id: int, ctx: CtxAdmin) -> Usuario:
    return usuario_service.desbloquear(ctx, usuario_id)


@router.post("/usuarios/{usuario_id}/restablecer-password", response_model=PasswordTemporal)
def restablecer(usuario_id: int, ctx: CtxAdmin) -> PasswordTemporal:
    clave = usuario_service.restablecer_password(ctx, usuario_id)
    return PasswordTemporal(username=usuario_service.obtener(ctx.db, usuario_id).username, password_temporal=clave)


@router.post("/usuarios/{usuario_id}/cerrar-sesiones", response_model=Mensaje)
def cerrar_sesiones(usuario_id: int, ctx: CtxAdmin) -> Mensaje:
    cerradas = usuario_service.cerrar_sesiones(ctx, usuario_id)
    return Mensaje(mensaje=f"Se cerraron {cerradas} sesiones.")
