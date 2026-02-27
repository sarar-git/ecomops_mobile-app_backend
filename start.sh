#!/usr/bin/env bash
set -e  # Exit immediately on error

# Apply database migrations
echo "🔍 Checking environment configuration..."
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL is not set! Please add it to your Render Environment Variables."
    exit 1
fi

echo "🚀 Running database migrations (alembic upgrade head)..."
if ! alembic upgrade head; then
    echo "❌ ERROR: Database migrations failed. This usually means the database connection string is wrong or the database is unreachable."
    exit 1
fi

echo "✅ Migrations complete. Starting application with Gunicorn..."
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 2 \
  --bind 0.0.0.0:${PORT:-10000} \
  --timeout 120
