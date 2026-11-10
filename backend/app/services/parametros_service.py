"""Parámetros configurables por el administrador (con auditoría)."""
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errores import NoEncontradoError, ReglaNegocioError
from app.models import ParametroSistema
from app.services import auditoria_service
from app.services.contexto import Contexto


class Parametro(StrEnum):
    TRASLADO_MINUTOS = "TRASLADO_MINUTOS"
    PLAZO_REGISTRO_TARDIO_DIAS = "PLAZO_REGISTRO_TARDIO_DIAS"
    VIGENCIA_AUTORIZACION_HORAS = "VIGENCIA_AUTORIZACION_HORAS"
    SESIONES_CIERRE_INSCRIPCION = "SESIONES_CIERRE_INSCRIPCION"
    UMBRAL_RIESGO_PCT = "UMBRAL_RIESGO_PCT"
    PASSWORD_MIN = "PASSWORD_MIN"
    INACTIVIDAD_MINUTOS = "INACTIVIDAD_MINUTOS"
    SESION_MAX_HORAS = "SESION_MAX_HORAS"
    BLOQUEO_INTENTOS = "BLOQUEO_INTENTOS"
    BLOQUEO_MINUTOS = "BLOQUEO_MINUTOS"
    IP_MAX_FALLOS = "IP_MAX_FALLOS"
    IP_VENTANA_MINUTOS = "IP_VENTANA_MINUTOS"


def obtener(db: Session, clave: Parametro) -> int:
    valor = db.scalar(select(ParametroSistema.valor).where(ParametroSistema.clave == clave.value))
    if valor is None:
        raise NoEncontradoError(f"Falta el parámetro {clave.value}.")
    return valor


def listar(db: Session) -> list[ParametroSistema]:
    return list(db.scalars(select(ParametroSistema).order_by(ParametroSistema.clave)))


def actualizar(ctx: Contexto, clave: str, valor: int) -> ParametroSistema:
    parametro = ctx.db.scalar(
        select(ParametroSistema).where(ParametroSistema.clave == clave).with_for_update()
    )
    if parametro is None:
        raise NoEncontradoError("Parámetro inexistente.")
    if not parametro.minimo <= valor <= parametro.maximo:
        raise ReglaNegocioError(
            f"El valor debe estar entre {parametro.minimo} y {parametro.maximo}."
        )
    anterior = parametro.valor
    parametro.valor = valor
    parametro.actualizado_por = ctx.actor.usuario_id
    auditoria_service.registrar(
        ctx.db, ctx.actor, modulo="parametros", evento="parametro_modificado", accion="modificar",
        entidad="parametros_sistema", registro_id=clave,
        antes={"valor": anterior}, despues={"valor": valor},
    )
    return parametro
