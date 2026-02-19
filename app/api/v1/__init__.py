"""API v1 router."""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.warehouses import router as warehouses_router
from app.api.v1.manifests import router as manifests_router
from app.api.v1.scan_events import router as scan_events_router
from app.api.v1.scans import router as scans_router


router = APIRouter(prefix="/v1")

router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
router.include_router(warehouses_router, prefix="/warehouses", tags=["Warehouses"])
router.include_router(manifests_router, prefix="/manifests", tags=["Manifests"])
router.include_router(scan_events_router, prefix="/scan-events", tags=["Scan Events"])
router.include_router(scans_router, prefix="/scans", tags=["Batch Scanning"])
