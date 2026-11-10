"""Pruebas contra MySQL real (base siget_test). Se recrea el esquema con Alembic al inicio."""
import importlib.util
import os
from collections.abc import Iterator
from datetime import date, datetime, time
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "mysql+pymysql://siget:siget_dev_pw@127.0.0.1:3306/siget_test")
os.environ["ENTORNO"] = "pruebas"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.db import FabricaSesion, motor  # noqa: E402
from app.core.reloj import RelojFijo, obtener_reloj  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Ambiente, Area, Carrera, CicloAcademico, Facultad, Rol, Sede  # noqa: E402
from app.services import catalogo_service, persona_service, taller_service, usuario_service  # noqa: E402
from app.services.contexto import Actor, Contexto  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SEMILLAS = {"roles", "tipos_documento", "areas", "parametros_sistema", "alembic_version"}
HOY = date(2026, 11, 9)  # lunes
AHORA = datetime(2026, 11, 9, 10, 0)
PASSWORD = "ClaveSegura2026"


def _cargar_semillas():  # type: ignore[no-untyped-def]
    ruta = RAIZ / "alembic" / "versions" / "0002_datos_instalacion.py"
    spec = importlib.util.spec_from_file_location("semillas", ruta)
    modulo = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(modulo)  # type: ignore[union-attr]
    return modulo


@pytest.fixture(scope="session", autouse=True)
def esquema() -> Iterator[None]:
    with motor.begin() as con:
        con.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
        for (tabla,) in con.exec_driver_sql("SHOW TABLES").all():
            con.exec_driver_sql(f"DROP TABLE `{tabla}`")
        con.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def limpiar() -> Iterator[None]:
    yield
    semillas = _cargar_semillas()
    with motor.begin() as con:
        con.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
        for (tabla,) in con.exec_driver_sql("SHOW TABLES").all():
            if tabla not in SEMILLAS:
                con.exec_driver_sql(f"TRUNCATE TABLE `{tabla}`")
        for clave, valor, *_ in semillas.PARAMETROS:
            con.execute(text("UPDATE parametros_sistema SET valor=:v WHERE clave=:c"), {"v": valor, "c": clave})
        con.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")


@pytest.fixture
def reloj() -> RelojFijo:
    return RelojFijo(AHORA)


@pytest.fixture
def db() -> Iterator[Session]:
    sesion = FabricaSesion()
    yield sesion
    sesion.rollback()
    sesion.close()


class Mundo:
    """Datos base creados con los servicios reales."""

    def __init__(self, db: Session, reloj: RelojFijo) -> None:
        self.db, self.reloj = db, reloj
        sistema = Contexto(db=db, actor=None, reloj=reloj)  # type: ignore[arg-type]
        self.admin, _ = usuario_service.crear(
            sistema, username="admin", email="admin@test.pe", nombres="Admin", apellido_paterno="Test",
            apellido_materno=None, rol=Rol.ADMINISTRADOR, password=PASSWORD, debe_cambiar=False,
        )
        self.ctx = Contexto(db=db, actor=Actor(self.admin.id, Rol.ADMINISTRADOR, "127.0.0.1"), reloj=reloj)
        self.sede_a = catalogo_service.crear(self.ctx, Sede, {"nombre": "Central", "direccion": "Av. 1"})
        self.sede_b = catalogo_service.crear(self.ctx, Sede, {"nombre": "Norte", "direccion": "Av. 2"})
        self.aula_a = catalogo_service.crear(self.ctx, Ambiente, {"sede_id": self.sede_a.id, "codigo": "A1", "nombre": "Aula A1", "capacidad": 30})
        self.aula_a2 = catalogo_service.crear(self.ctx, Ambiente, {"sede_id": self.sede_a.id, "codigo": "A2", "nombre": "Aula A2", "capacidad": 30})
        self.aula_b = catalogo_service.crear(self.ctx, Ambiente, {"sede_id": self.sede_b.id, "codigo": "B1", "nombre": "Aula B1", "capacidad": 30})
        facultad = catalogo_service.crear(self.ctx, Facultad, {"codigo": "F1", "nombre": "Facultad"})
        self.carrera = catalogo_service.crear(self.ctx, Carrera, {"facultad_id": facultad.id, "codigo": "C1", "nombre": "Carrera"})
        self.ciclo = catalogo_service.crear(self.ctx, CicloAcademico, {"nombre": "2026-II", "fecha_inicio": date(2026, 8, 1), "fecha_fin": date(2026, 12, 31)})
        self.areas = {a.nombre: a for a in db.query(Area).all()}
        self.docente, _ = self.nuevo_docente("doc1", "Danza")
        self._n_est = 0
        db.commit()

    def nuevo_docente(self, username: str, area: str, horario: tuple[time, time] = (time(7), time(21))):  # type: ignore[no-untyped-def]
        n = len(username) * 1000 + sum(map(ord, username))
        docente, clave = persona_service.crear_docente(self.ctx, {
            "username": username, "email": f"{username}@test.pe", "tipo_documento_id": 1,
            "numero_documento": f"{40000000 + n}", "nombres": username.title(), "apellido_paterno": "Docente",
            "area_ids": [self.areas[area].id],
        })
        docente.usuario.debe_cambiar_password = False
        from app.core.seguridad import hashear_password
        docente.usuario.password_hash = hashear_password(PASSWORD)
        persona_service.fijar_disponibilidad(self.ctx, docente.id, [(d, *horario, None, None) for d in range(1, 8)])
        return docente, clave

    def estudiante(self, **extra):  # type: ignore[no-untyped-def]
        self._n_est += 1
        datos = {
            "tipo_documento_id": 1, "numero_documento": f"{70000000 + self._n_est}",
            "codigo_universitario": f"U{self._n_est:05d}", "nombres": f"Est{self._n_est}",
            "apellido_paterno": "Apellido", "apellido_materno": None, "carrera_id": self.carrera.id,
            "estado": "Activo",
        } | extra
        return persona_service.crear_estudiante(self.ctx, datos)

    def taller(self, codigo: str = "T1", bloques=None, docente=None, sede=None, ambiente="defecto",  # type: ignore[no-untyped-def]
               cupo: int = 20, inicio: date = date(2026, 11, 2), fin: date = date(2026, 12, 18), area: str = "Danza"):
        sede = sede or self.sede_a
        if ambiente == "defecto":
            ambiente = self.aula_a if sede is self.sede_a else self.aula_b
        taller = taller_service.crear(self.ctx, {
            "codigo": codigo, "nombre": f"Taller {codigo}", "descripcion": None, "area_id": self.areas[area].id,
            "ciclo_academico_id": self.ciclo.id, "docente_id": (docente or self.docente).id, "sede_id": sede.id,
            "ambiente_id": ambiente.id if ambiente else None, "cupo_maximo": cupo, "horas_totales": 30,
            "umbral_aptitud": 80, "fecha_inicio": inicio, "fecha_fin": fin,
        }, None)
        bloques = bloques or [taller_service.BloqueHorario(1, time(8), time(10))]
        taller_service.fijar_horarios(self.ctx, taller.id, bloques, None)
        return taller


@pytest.fixture
def mundo(db: Session, reloj: RelojFijo) -> Mundo:
    return Mundo(db, reloj)


@pytest.fixture
def cliente(reloj: RelojFijo) -> Iterator[TestClient]:
    app.dependency_overrides[obtener_reloj] = lambda: reloj
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def iniciar(cliente: TestClient, usuario: str, password: str = PASSWORD) -> TestClient:
    r = cliente.post("/api/v1/auth/login", json={"username": usuario, "password": password})
    assert r.status_code == 200, r.text
    cliente.headers["X-CSRF-Token"] = r.json()["csrf"]
    return cliente
