"""Alembic migration environment (Render-safe)."""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base
from app.models import Tenant, Warehouse, User, Manifest, ScanEvent

config = context.config

# Load DATABASE_URL from environment (REQUIRED on Render)
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not set")

# Force sync-compatible driver URL for Alembic
# - Legacy asyncpg URLs are mapped to psycopg (installed driver)
# - psycopg URLs are already sync-compatible for Alembic
if "+asyncpg" in database_url:
    sync_database_url = database_url.replace("+asyncpg", "+psycopg")
else:
    sync_database_url = database_url

config.set_main_option("sqlalchemy.url", sync_database_url)

# Logging config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
