from datetime import timedelta

from sqlalchemy import select

from app.core.reloj import RelojSistema
from app.models import Auditoria, Usuario
from tests.conftest import PASSWORD, iniciar


def test_login_correcto_crea_cookies_httponly(cliente, mundo):
    r = cliente.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower()
    assert r.json()["usuario"]["rol"] == "Administrador"


def test_password_incorrecta_mensaje_generico(cliente, mundo):
    r = cliente.post("/api/v1/auth/login", json={"username": "admin", "password": "mala"})
    assert r.status_code == 401
    assert r.json()["mensaje"] == "Usuario o contraseña incorrectos."
    r2 = cliente.post("/api/v1/auth/login", json={"username": "noexiste", "password": "mala"})
    assert r2.json()["mensaje"] == r.json()["mensaje"]


def test_bloqueo_tras_cinco_intentos_y_desbloqueo_tras_30_minutos(cliente, mundo, reloj):
    for _ in range(5):
        cliente.post("/api/v1/auth/login", json={"username": "admin", "password": "mala"})
    r = cliente.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert r.status_code == 401 and r.json()["codigo"] == "cuenta_bloqueada"
    reloj.momento += timedelta(minutes=31)
    assert cliente.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}).status_code == 200


def test_limite_por_ip(cliente, mundo):
    for i in range(20):
        cliente.post("/api/v1/auth/login", json={"username": f"x{i}", "password": "mala"})
    r = cliente.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert r.status_code == 429


def test_csrf_obligatorio_en_metodos_que_modifican(cliente, mundo):
    iniciar(cliente, "admin")
    token = cliente.headers.pop("X-CSRF-Token")
    r = cliente.post("/api/v1/catalogos/areas", json={"nombre": "Coro"})
    assert r.status_code == 403 and r.json()["codigo"] == "csrf_invalido"
    cliente.headers["X-CSRF-Token"] = token
    assert cliente.post("/api/v1/catalogos/areas", json={"nombre": "Coro"}).status_code == 201


def test_inactividad_usa_total_seconds(cliente, mundo, reloj):
    iniciar(cliente, "admin")
    # 1 día y 5 minutos: con .seconds serían 5 minutos y la sesión seguiría viva.
    reloj.momento += timedelta(days=1, minutes=5)
    r = cliente.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["codigo"] == "sesion_expirada"


def test_inactividad_menor_a_60_minutos_mantiene_sesion(cliente, mundo, reloj):
    iniciar(cliente, "admin")
    reloj.momento += timedelta(minutes=59)
    assert cliente.get("/api/v1/auth/me").status_code == 200


def test_cambio_de_password_obligatorio(cliente, mundo, db):
    usuario = db.scalar(select(Usuario).where(Usuario.username == "admin"))
    usuario.debe_cambiar_password = True
    db.commit()
    iniciar(cliente, "admin")
    assert cliente.get("/api/v1/dashboard").json()["codigo"] == "cambio_password_requerido"
    corta = cliente.post("/api/v1/auth/cambiar-password", json={"actual": PASSWORD, "nueva": "corta1"})
    assert corta.status_code == 422
    ok = cliente.post("/api/v1/auth/cambiar-password", json={"actual": PASSWORD, "nueva": "NuevaClave2026"})
    assert ok.status_code == 200
    assert cliente.get("/api/v1/dashboard").status_code == 200


def test_docente_no_accede_a_endpoints_de_administrador(cliente, mundo):
    iniciar(cliente, "doc1")
    assert cliente.get("/api/v1/estudiantes").status_code == 403
    assert cliente.get("/api/v1/parametros").status_code == 403


def test_docente_no_ve_talleres_ajenos(cliente, mundo, db):
    propio = mundo.taller("T1")
    otro_docente, _ = mundo.nuevo_docente("doc2", "Danza")
    ajeno = mundo.taller("T2", docente=otro_docente, ambiente=mundo.aula_a2)
    db.commit()
    iniciar(cliente, "doc1")
    assert cliente.get(f"/api/v1/talleres/{propio.id}").status_code == 200
    assert cliente.get(f"/api/v1/talleres/{ajeno.id}").status_code == 403
    codigos = [t["codigo"] for t in cliente.get("/api/v1/talleres").json()["items"]]
    assert codigos == ["T1"]


def test_auditoria_no_guarda_passwords(cliente, mundo, db):
    iniciar(cliente, "admin")
    cliente.post("/api/v1/auth/cambiar-password", json={"actual": PASSWORD, "nueva": "OtraClave2026"})
    for fila in db.scalars(select(Auditoria)):
        texto = f"{fila.datos_anteriores} {fila.datos_nuevos}"
        assert PASSWORD not in texto and "OtraClave2026" not in texto and "password_hash" not in texto


def test_reloj_del_sistema_esta_en_hora_de_lima():
    from datetime import UTC, datetime

    diferencia = datetime.now(UTC).replace(tzinfo=None) - RelojSistema().ahora()
    assert abs(diferencia - timedelta(hours=5)) < timedelta(minutes=1)
