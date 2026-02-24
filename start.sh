#!/usr/bin/env bash
set -e  # Exit immediately on error

# Apply database migrations
# IMPORTANT: Removed 'alembic stamp' which was skipping table creation
alembic upgrade head

echo "Starting application..."
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 2 \
  --bind 0.0.0.0:${PORT:-10000} \
  --timeout 120
