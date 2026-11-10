"""Excepciones de dominio y su traducción a respuestas HTTP."""
import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

registro = logging.getLogger("siget")


class ErrorDominio(Exception):
    estado_http = 400
    codigo = "error"

    def __init__(self, mensaje: str, *, codigo: str | None = None, detalles: Any = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        if codigo:
            self.codigo = codigo
        self.detalles = detalles


class ReglaNegocioError(ErrorDominio):
    estado_http = 422
    codigo = "regla_negocio"


class ConflictoError(ErrorDominio):
    estado_http = 409
    codigo = "conflicto"


class ConflictoHorarioError(ConflictoError):
    codigo = "conflicto_horario"


class NoEncontradoError(ErrorDominio):
    estado_http = 404
    codigo = "no_encontrado"


class PermisoDenegadoError(ErrorDominio):
    estado_http = 403
    codigo = "permiso_denegado"


class NoAutenticadoError(ErrorDominio):
    estado_http = 401
    codigo = "no_autenticado"


class DemasiadosIntentosError(ErrorDominio):
    estado_http = 429
    codigo = "demasiados_intentos"


def _respuesta(estado: int, codigo: str, mensaje: str, detalles: Any = None) -> JSONResponse:
    cuerpo: dict[str, Any] = {"codigo": codigo, "mensaje": mensaje}
    if detalles is not None:
        cuerpo["detalles"] = detalles
    return JSONResponse(status_code=estado, content=cuerpo)


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorDominio)
    async def _dominio(_: Request, exc: ErrorDominio) -> JSONResponse:
        return _respuesta(exc.estado_http, exc.codigo, exc.mensaje, exc.detalles)

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
        detalles = [
            {"campo": ".".join(str(p) for p in err["loc"][1:]), "mensaje": err["msg"]}
            for err in exc.errors()
        ]
        return _respuesta(422, "validacion", "Hay datos inválidos en la solicitud.", detalles)

    @app.exception_handler(Exception)
    async def _inesperado(_: Request, exc: Exception) -> JSONResponse:
        referencia = uuid.uuid4().hex[:12]
        registro.error("ref=%s %s", referencia, type(exc).__name__, exc_info=exc)
        return _respuesta(
            500, "error_interno", f"Ocurrió un error inesperado. Referencia: {referencia}."
        )
