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
            
            if integrity_status == "REPAIR_SCANS":
                logger.warning("Integrity check failed (REPAIR_SCANS). Attempting surgical repair of internal table...")
                logger.info("Dropping broken 'scan_events' table...")
                await conn.execute(text("DROP TABLE IF EXISTS scan_events"))
                
                try:
                    await conn.execute(text("DROP TABLE IF EXISTS alembic_version_mobile"))
                    logger.info("Cleared alembic_version_mobile to force clean migration.")
                except Exception as e:
                    logger.warning(f"Could not clear alembic marker: {e}")

                # Note: We do NOT run create_all here anymore. 
                # Instead, we rely on the next alembic migration or manual repair
                # to avoid wiping shared tables like 'users' or 'profiles'.
                logger.info("Internal repair command sent. Please restart or check Alembic logs.")
            elif integrity_status == "SYNC_REQUIRED":
                logger.error("DANGER: Database is missing critical tables! Mobile app may not function.")
                logger.info("Please run migrations from the main backend or check DATABASE_URL.")
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


from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Log validation errors for debugging 422s."""
    logger.error(f"Validation error: {exc.errors()}")
    logger.error(f"Failed body: {await request.body()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(await request.body())},
    )


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
