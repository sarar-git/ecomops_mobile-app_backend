#!/usr/bin/env bash
set -e  # Exit immediately on error

# Apply database migrations
# Apply database migrations
echo "Checking database state..."
# Defensive: If 'users' table is missing but 'alembic_version_mobile' exists, 
# it means we are in a broken stamped state. Resetting version table.
python3 -c "
import asyncio
from sqlalchemy import text
from app.core.database import engine
async def check():
    async with engine.begin() as conn:
        try:
            await conn.execute(text('SELECT 1 FROM users LIMIT 1'))
            print('Database tables already exist.')
        except Exception as e:
            print(f'Users table missing ({type(e).__name__}). Checking for stale version marker...')
            try:
                await conn.execute(text('DROP TABLE IF EXISTS alembic_version_mobile'))
                print('Dropped alembic_version_mobile to force fresh migration.')
            except Exception as e2:
                print(f'Error resetting version table: {e2}')
asyncio.run(check())
"

echo "Current migration state:"
alembic current || echo "No migration state found."

echo "Running alembic upgrade head..."
alembic upgrade head

echo "Starting application..."
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 2 \
  --bind 0.0.0.0:${PORT:-10000} \
  --timeout 120
