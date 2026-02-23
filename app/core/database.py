"""Database configuration and session management."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

from app.core.config import settings


def _normalize_async_database_url(database_url: str) -> str:
    """Normalize async database URL to installed async driver(s)."""
    # Accept legacy asyncpg URLs and run with psycopg driver (psycopg 3)
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    
    # Accept legacy heroku-style postgres:// URLs and ensure psycopg driver
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
        
    # Ensure plain postgresql:// uses the installed psycopg (v3) driver
    if database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        
    return database_url


# Naming convention for constraints
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=naming_convention)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    metadata = metadata


# Create async engine (Render-safe)
database_url = _normalize_async_database_url(settings.DATABASE_URL)

engine_kwargs = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,     # Avoid stale connections on Render
}

if database_url.startswith("sqlite"):
    engine = create_async_engine(
        database_url,
        **engine_kwargs,
    )
else:
    engine = create_async_engine(
        database_url,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_recycle=1800,      # Recycle connections every 30 min
        **engine_kwargs,
    )


# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        yield session
