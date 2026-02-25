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
    
    # Failsafe: Ensure tables exist on startup and have correct columns
    try:
        logger.info("Checking database schema integrity...")
        async with engine.begin() as conn:
            def verify_integrity(sync_conn):
                inspector = inspect(sync_conn)
                existing_tables = inspector.get_table_names()
                
                # Check for critical manifest_id column in scan_events
                if "scan_events" in existing_tables:
                    columns = [c["name"] for c in inspector.get_columns("scan_events")]
                    if "manifest_id" not in columns:
                        logger.error("DANGER: 'scan_events' table is missing 'manifest_id' column!")
                        return "REPAIR_SCANS"
                
                # Check if basic tables exist
                required_tables = ["users", "tenants", "warehouses", "manifests", "scan_events"]
                missing = [t for t in required_tables if t not in existing_tables]
                if missing:
                    logger.warning(f"Missing tables: {missing}")
                    return "SYNC_REQUIRED"
                
                return "OK"
            
            integrity_status = await conn.run_sync(verify_integrity)
            
            if integrity_status != "OK":
                logger.warning(f"Integrity check failed ({integrity_status}). Attempting self-healing...")
                
                if integrity_status == "REPAIR_SCANS":
                    logger.info("Dropping broken 'scan_events' table...")
                    await conn.execute(text("DROP TABLE IF EXISTS scan_events"))
                
                # Clear alembic marker to force a "fresh" start if critical tables missing
                if integrity_status in ["SYNC_REQUIRED", "REPAIR_SCANS"]:
                    try:
                        await conn.execute(text("DROP TABLE IF EXISTS alembic_version_mobile"))
                        logger.info("Cleared alembic_version_mobile to force clean migration.")
                    except Exception as e:
                        logger.warning(f"Could not clear alembic marker: {e}")

                # Run metadata.create_all
                logger.info("Running metadata.create_all (failsafe)...")
                try:
                    await conn.run_sync(Base.metadata.create_all)
                except Exception as sync_err:
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
