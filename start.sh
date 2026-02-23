#!/usr/bin/env bash
set -e  # Exit immediately on error

echo "Applying database migrations..."
# Force stamp the local version to the new version_table (alembic_version_mobile)
alembic stamp 001_initial_schema
alembic upgrade head

echo "Starting application..."
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 2 \
  --bind 0.0.0.0:${PORT:-10000} \
  --timeout 120
