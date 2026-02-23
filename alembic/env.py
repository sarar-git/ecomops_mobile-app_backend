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
from app.core.config import settings

config = context.config

config = context.config

# Load DATABASE_URL from settings (Pydantic handles .env and env vars)
database_url = settings.DATABASE_URL
if not database_url:
    raise RuntimeError("DATABASE_URL is not set in environment or .env")

# Force sync-compatible driver URL for Alembic
# - Mapping everything to postgresql+psycopg so it uses the v3 driver
if database_url.startswith("postgresql+asyncpg://"):
    sync_database_url = database_url.replace("+asyncpg", "+psycopg")
elif database_url.startswith("postgres://"):
    sync_database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://") and "+psycopg" not in database_url:
    sync_database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
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
        version_table=config.get_main_option("version_table", "alembic_version")
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
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            version_table=config.get_main_option("version_table", "alembic_version")
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
