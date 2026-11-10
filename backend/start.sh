#!/bin/sh
# Arranque en el servidor: migraciones, administrador inicial (si se configuró) y API.
set -e
alembic upgrade head
if [ -n "$ADMIN_PASSWORD" ]; then
  python -m app.cli crear-admin --si-no-existe
fi
if [ "$CARGAR_DATOS_DEMO" = "1" ]; then
  python -m app.cli datos-demo
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
