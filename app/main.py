"""Main FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from sqlalchemy import text, inspect
from app.core.database import engine, Base
from app.api.v1 import router as v1_router
from app.models import user, tenant, warehouse, manifest, scan_event  # Force models to register with Base


# Setup logging
setup_logging(settings.DEBUG)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Logistics Scanning API")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    # Failsafe: Ensure tables exist on startup
    try:
        logger.info("Checking database schema integrity...")
        async with engine.begin() as conn:
            # 1. Check if 'users' table exists
            def has_users_table(sync_conn):
                return inspect(sync_conn).has_table("users")
            
            has_users = await conn.run_sync(has_users_table)
            
            if not has_users:
                logger.warning("relation 'users' does not exist! Attempting self-healing...")
                
                # 2. Check for stale alembic marker
                def has_alembic_marker(sync_conn):
                    return inspect(sync_conn).has_table("alembic_version_mobile")
                
                has_marker = await conn.run_sync(has_alembic_marker)
                if has_marker:
                    logger.info("Stale alembic marker found. Clearing to allow re-migration.")
                    await conn.execute(text("DROP TABLE alembic_version_mobile"))

                # 3. Create Tables
                logger.info("Running metadata.create_all (failsafe)...")
                try:
                    await conn.run_sync(Base.metadata.create_all)
                except Exception as sync_err:
                    # Specific handling for Enum collisions (pg_type_typname_nsp_index)
                    if "already exists" in str(sync_err).lower():
                        logger.info(f"Schema sync encountered existing types: {sync_err}. Continuing...")
                    else:
                        raise sync_err
                
                logger.info("Self-healing complete. Schema should now be valid.")
            else:
                logger.info("Database integrity check passed.")

    except Exception as e:
        logger.error(f"Failsafe setup failed: {e}")
        # Not raising here to prevent boot-loop if DB is reachable but slightly weird

    yield
    logger.info("Shutting down Logistics Scanning API")
    await engine.dispose()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Production-ready API for mobile logistics scanning SaaS",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(v1_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": settings.APP_NAME}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/api/docs",
    }
