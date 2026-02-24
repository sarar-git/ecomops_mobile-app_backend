#!/usr/bin/env bash
set -e  # Exit immediately on error

# Apply database migrations
# Apply database migrations
echo "Running alembic upgrade head..."
alembic upgrade head

echo "Starting application..."
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 2 \
  --bind 0.0.0.0:${PORT:-10000} \
  --timeout 120
