"""Aplicación FastAPI: API en /api/v1 y, en producción, el frontend compilado en el mismo origen."""
import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import auth, catalogos, personas, sistema, talleres
from app.core.config import obtener_configuracion
from app.core.errores import registrar_manejadores

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

config = obtener_configuracion()
app = FastAPI(
    title="SIGET WEB",
    version="0.1.0",
    docs_url=None if config.es_produccion else "/api/docs",
    redoc_url=None,
    openapi_url=None if config.es_produccion else "/api/openapi.json",
)
registrar_manejadores(app)

if not config.es_produccion:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origenes,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):  # type: ignore[no-untyped-def]
    respuesta: Response = await call_next(request)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "same-origin"
    respuesta.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if not request.url.path.startswith("/api/docs"):
        respuesta.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
    if config.cookie_segura:
        respuesta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


for modulo in (auth, catalogos, personas, talleres, sistema):
    app.include_router(modulo.router, prefix="/api/v1")


@app.get("/api/salud", include_in_schema=False)
def salud() -> dict[str, str]:
    return {"estado": "ok"}


@app.api_route("/api/{ruta:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def api_inexistente(ruta: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={"codigo": "no_encontrado", "mensaje": "Ruta inexistente."})


# Frontend compilado (Vite). Cualquier ruta que no sea /api devuelve index.html (SPA).
dist = config.frontend_dist
if dist.is_dir():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{ruta:path}", include_in_schema=False)
    def spa(ruta: str) -> FileResponse:
        archivo = (dist / ruta).resolve()
        if ruta and archivo.is_file() and archivo.is_relative_to(dist.resolve()):
            return FileResponse(archivo)
        return FileResponse(dist / "index.html")
