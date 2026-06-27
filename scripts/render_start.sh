#!/bin/sh
set -eu

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting MedRisk API on port ${PORT:-10000}..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-10000}"
