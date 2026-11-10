"""Entorno de Alembic: la URL sale de la configuración, nunca del .ini."""
from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import DESFASE_MYSQL, obtener_configuracion
from app.models import Base

config = context.config
url = config.attributes.get("url") or obtener_configuracion().database_url
target_metadata = Base.metadata


def ejecutar_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def ejecutar_online() -> None:
    conexion_externa = config.attributes.get("connection")
    if conexion_externa is not None:
        context.configure(connection=conexion_externa, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return
    motor = engine_from_config({"sqlalchemy.url": url}, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with motor.connect() as conexion:
        conexion.exec_driver_sql(f"SET time_zone = '{DESFASE_MYSQL}'")
        conexion.commit()  # cerrar la transacción implícita; si no, Alembic no confirma los datos
        context.configure(connection=conexion, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    ejecutar_offline()
else:
    ejecutar_online()
