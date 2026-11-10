"""Configuración leída de variables de entorno (nunca secretos en el código)."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ZONA_HORARIA = "America/Lima"
# Perú no usa horario de verano: el desfase fijo equivale a America/Lima.
DESFASE_MYSQL = "-05:00"


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    entorno: Literal["desarrollo", "pruebas", "demo", "produccion"] = "desarrollo"
    database_url: str = Field(
        default="mysql+pymysql://siget:siget_dev_pw@127.0.0.1:3306/siget_dev",
        validation_alias="DATABASE_URL",
    )
    cookie_segura: bool = False
    cors_origenes: list[str] = ["http://localhost:5173"]
    frontend_dist: Path = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    pool_size: int = 5
    max_overflow: int = 5

    @field_validator("database_url")
    @classmethod
    def normalizar_url(cls, valor: str) -> str:
        # Railway entrega mysql://...; SQLAlchemy necesita el controlador explícito.
        if valor.startswith("mysql://"):
            return "mysql+pymysql://" + valor.removeprefix("mysql://")
        return valor

    @property
    def es_produccion(self) -> bool:
        return self.entorno == "produccion"


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()
