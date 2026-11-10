"""Motor, sesiones y unidad de trabajo por petición."""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DESFASE_MYSQL, obtener_configuracion


def crear_motor(url: str | None = None) -> Engine:
    config = obtener_configuracion()
    motor = create_engine(
        url or config.database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        hide_parameters=True,  # los valores de las consultas nunca llegan a los registros
    )

    @event.listens_for(motor, "connect")
    def _al_conectar(conexion, _registro) -> None:  # type: ignore[no-untyped-def]
        cursor = conexion.cursor()
        cursor.execute(f"SET time_zone = '{DESFASE_MYSQL}'")
        cursor.close()

    return motor


motor = crear_motor()
FabricaSesion = sessionmaker(bind=motor, expire_on_commit=False)


def obtener_db() -> Iterator[Session]:
    """Una transacción por petición: commit al terminar bien, rollback ante cualquier error."""
    sesion = FabricaSesion()
    try:
        yield sesion
        sesion.commit()
    except Exception:
        sesion.rollback()
        raise
    finally:
        sesion.close()
