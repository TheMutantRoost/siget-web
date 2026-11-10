# SIGET WEB

Sistema de Gestión de Talleres Extracurriculares de arte y cultura de la Universidad Nacional de Barranca (UNAB). Es la versión web del sistema de escritorio [Sistema-extracurricular](https://github.com/czamora242/Sistema-extracurricular). La base de datos se inicia limpia.

**Stack:** FastAPI · SQLAlchemy 2.0 · Alembic · MySQL 8.4 · Argon2id · React 19 · TypeScript · Vite · Tailwind CSS.

## Estado: núcleo funcional (entrega 1)

| Módulo | Estado |
| --- | --- |
| Inicio de sesión con sesión en servidor, CSRF, bloqueo por cuenta y por IP, cambio obligatorio de contraseña | Listo |
| Roles (Administrador, Docente, Operador) verificados en cada endpoint | Listo |
| Sedes, ambientes, áreas, facultades, carreras, ciclos (un solo ciclo activo garantizado por la base) | Listo |
| Estudiantes (tipo de documento, apellidos separados, búsqueda, historial) | Listo |
| Docentes con usuario propio, áreas autorizadas y disponibilidad | Listo |
| Talleres con varios bloques por día, sesiones generadas y regeneradas sin colisiones | Listo |
| Cruces de estudiante, docente y ambiente; traslado entre sedes; excepción de área | Listo |
| Inscripciones: cupo, cierre tras 3 sesiones realizadas, bloqueo manual, retiro, reactivación, cambio de taller | Listo |
| Asistencia P/A/J, congelación, primer registro tardío, autorización puntual | Listo |
| Porcentaje, riesgo y aptitud (`AsistenciaCalculator`) | Listo |
| Lista de aptos inmutable, exclusiones, versiones y Excel | Listo |
| Dashboard, auditoría y parámetros | Listo |
| Cancelación de sesiones; alerta de sesiones vencidas | Listo |
| Reprogramación de sesiones, bienes patrimoniales, reportes Excel/PDF, importación masiva desde Excel, recuperación de contraseña por correo | Pendiente (entrega 2) |

## Desarrollo local

Requisitos: Python 3.14, Node 22.12 o superior y MySQL 8.4.

```bash
# Base de datos (en MySQL Workbench o en la consola)
CREATE DATABASE siget_dev CHARACTER SET utf8mb4;
CREATE USER 'siget'@'127.0.0.1' IDENTIFIED BY 'una-clave';
GRANT ALL ON siget_dev.* TO 'siget'@'127.0.0.1';

# Backend
cd backend
python -m venv .venv && . .venv/bin/activate       # en Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp ../.env.example .env                              # edite DATABASE_URL
alembic upgrade head
python -m app.cli crear-admin --usuario admin --email admin@unab.edu.pe
python -m app.cli datos-demo                         # opcional: datos de ejemplo
uvicorn app.main:app --reload                        # http://127.0.0.1:8000/api/docs

# Frontend (otra terminal)
cd frontend
npm install
npm run dev                                          # http://localhost:5173
```

Pruebas del backend (crean y borran las tablas de `siget_test`):

```bash
cd backend && DATABASE_URL=mysql+pymysql://siget:una-clave@127.0.0.1:3306/siget_test python -m pytest -q
```

## Publicación en Railway

1. En [railway.com](https://railway.com), cree un proyecto con **Deploy from GitHub repo** y elija este repositorio. Railway detecta el `Dockerfile`.
2. En el mismo proyecto, agregue **Database → MySQL**.
3. En el servicio de la aplicación, pestaña **Variables**, agregue:
   - `DATABASE_URL` = `${{MySQL.MYSQL_URL}}`
   - `ENTORNO` = `demo`
   - `COOKIE_SEGURA` = `true`
   - `ADMIN_USERNAME` = `admin`, `ADMIN_EMAIL` = su correo y `ADMIN_PASSWORD` = una clave de al menos 10 caracteres con letras y números.
   - `CARGAR_DATOS_DEMO` = `1` solo si quiere datos de ejemplo.
4. En **Settings → Networking**, pulse **Generate Domain**. Esa es la URL pública, con HTTPS.
5. Ingrese con `admin` y la clave del paso 3. El sistema le pedirá cambiarla.

Al arrancar, `backend/start.sh` aplica las migraciones y crea el administrador solo si todavía no existe.

## Estructura

```
backend/
  app/api/v1/        endpoints (sin lógica de negocio)
  app/services/      reglas: DisponibilidadService, AsistenciaCalculator, AuditoriaService…
  app/repositories/  consultas en bloque
  app/models/        modelos SQLAlchemy
  alembic/versions/  migraciones (0001 esquema, 0002 datos de instalación)
  tests/             pruebas sobre MySQL real
frontend/src/
  api/ contexts/ hooks/ layouts/ pages/ components/
```

La zona horaria es America/Lima en todo el sistema. "Hoy" sale de un `Reloj` inyectable, y las pruebas lo congelan.
