"""Datos de instalación: roles, tipos de documento, áreas y parámetros del sistema.

No son datos ficticios: son los catálogos fijados en la especificación v3.

Revision ID: 0002
Revises: 0001
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = [(1, "Administrador"), (2, "Docente"), (3, "Operador")]

# Formatos de CE, Pasaporte y Otros: propuesta P1 aprobada, editable por el administrador.
TIPOS_DOCUMENTO = [
    (1, "DNI", "DNI", 8, 8, True),
    (2, "CE", "Carné de extranjería", 9, 12, False),
    (3, "PAS", "Pasaporte", 6, 12, False),
    (4, "OTR", "Otros", 1, 20, False),
]

AREAS = ["Danza", "Teatro", "Canto", "Música", "Dibujo y Pintura"]

PARAMETROS = [
    ("TRASLADO_MINUTOS", 60, 0, 240, "Minutos mínimos entre actividades en sedes distintas."),
    ("PLAZO_REGISTRO_TARDIO_DIAS", 7, 0, 60,
     "Días tras la fecha de la sesión en que el docente puede hacer el primer registro, "
     "cancelar o reprogramar."),
    ("VIGENCIA_AUTORIZACION_HORAS", 72, 1, 720, "Horas de validez de una autorización de edición."),
    ("SESIONES_CIERRE_INSCRIPCION", 3, 1, 50,
     "Sesiones realizadas a partir de las cuales se cierran las inscripciones."),
    ("UMBRAL_RIESGO_PCT", 10, 1, 50, "Porcentaje de faltas desde el cual un estudiante está en riesgo."),
    ("PASSWORD_MIN", 10, 8, 64, "Longitud mínima de contraseña."),
    ("INACTIVIDAD_MINUTOS", 60, 5, 480, "Minutos de inactividad que cierran la sesión."),
    ("SESION_MAX_HORAS", 12, 1, 72, "Duración máxima absoluta de una sesión de usuario."),
    ("BLOQUEO_INTENTOS", 5, 3, 20, "Intentos fallidos que bloquean la cuenta."),
    ("BLOQUEO_MINUTOS", 30, 1, 1440, "Minutos de bloqueo de la cuenta."),
    ("IP_MAX_FALLOS", 20, 5, 500, "Fallos de inicio de sesión permitidos por IP en la ventana."),
    ("IP_VENTANA_MINUTOS", 15, 1, 1440, "Ventana en minutos del límite por IP."),
]


def upgrade() -> None:
    roles = sa.table("roles", sa.column("id"), sa.column("nombre"))
    op.bulk_insert(roles, [{"id": i, "nombre": n} for i, n in ROLES])

    tipos = sa.table(
        "tipos_documento", sa.column("id"), sa.column("codigo"), sa.column("nombre"),
        sa.column("longitud_min"), sa.column("longitud_max"), sa.column("solo_digitos"),
        sa.column("activo"),
    )
    op.bulk_insert(tipos, [
        {"id": i, "codigo": c, "nombre": n, "longitud_min": mi, "longitud_max": ma,
         "solo_digitos": d, "activo": True}
        for i, c, n, mi, ma, d in TIPOS_DOCUMENTO
    ])

    areas = sa.table("areas", sa.column("nombre"), sa.column("activo"))
    op.bulk_insert(areas, [{"nombre": n, "activo": True} for n in AREAS])

    parametros = sa.table(
        "parametros_sistema", sa.column("clave"), sa.column("valor"), sa.column("minimo"),
        sa.column("maximo"), sa.column("descripcion"),
    )
    op.bulk_insert(parametros, [
        {"clave": c, "valor": v, "minimo": mi, "maximo": ma, "descripcion": d}
        for c, v, mi, ma, d in PARAMETROS
    ])


def downgrade() -> None:
    op.execute("DELETE FROM parametros_sistema")
    op.execute("DELETE FROM areas")
    op.execute("DELETE FROM tipos_documento")
    op.execute("DELETE FROM roles")
