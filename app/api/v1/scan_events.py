"""Scan Events API endpoints."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.dependencies import TenantCtx, DbSession
from app.core.enums import ManifestStatus, SyncStatus
from app.core.logging import get_logger
from app.models.manifest import Manifest
from app.models.scan_event import ScanEvent
from app.schemas.scan_event import (
    ScanEventBulkRequest, ScanEventResponse, BulkScanResponse, 
    BulkScanResult, ScanEventListResponse
)


router = APIRouter()
logger = get_logger(__name__)


@router.post("/bulk", response_model=BulkScanResponse, status_code=status.HTTP_201_CREATED)
async def bulk_create_scan_events(
    request: ScanEventBulkRequest,
    ctx: TenantCtx,
    db: DbSession,
):
    """
    Bulk create scan events.
    - Idempotent: duplicates on (manifest_id, barcode_value) are skipped.
    - Server generates scanned_at_utc timestamp.
    - All events must belong to an OPEN manifest.
    """
    results = []
    inserted_count = 0
    duplicate_count = 0
    error_count = 0
    
    # Group events by manifest_id
    manifest_ids = set(e.manifest_id for e in request.events)
    
    # Verify all manifests exist, belong to tenant, and are OPEN
    manifests_result = await db.execute(
        select(Manifest)
        .where(
            Manifest.id.in_(manifest_ids),
            Manifest.tenant_id == ctx.tenant_id
        )
    )
    manifests = {m.id: m for m in manifests_result.scalars().all()}
    
    # Process each event
    server_timestamp = datetime.now(timezone.utc)
    
    for event_data in request.events:
        manifest = manifests.get(event_data.manifest_id)
        
        # Check manifest exists
        if manifest is None:
            results.append(BulkScanResult(
                barcode_value=event_data.barcode_value,
                success=False,
                error=f"Manifest {event_data.manifest_id} not found",
            ))
            error_count += 1
            continue
        
        # Check manifest is OPEN
        if manifest.status != ManifestStatus.OPEN:
            results.append(BulkScanResult(
                barcode_value=event_data.barcode_value,
                success=False,
                error=f"Manifest {event_data.manifest_id} is closed",
            ))
            error_count += 1
            continue
        
        # Check for existing scan (duplicate detection)
        existing_result = await db.execute(
            select(ScanEvent.id)
            .where(
                ScanEvent.manifest_id == event_data.manifest_id,
                ScanEvent.barcode_value == event_data.barcode_value
            )
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            results.append(BulkScanResult(
                barcode_value=event_data.barcode_value,
                success=True,
                scan_event_id=existing,
                is_duplicate=True,
            ))
            duplicate_count += 1
            continue
        
        # Create new scan event
        try:
            scan_event = ScanEvent(
                tenant_id=ctx.tenant_id,
                warehouse_id=manifest.warehouse_id,
                manifest_id=manifest.id,
                flow_type=manifest.flow_type,
                marketplace=manifest.marketplace,
                carrier=manifest.carrier,
                barcode_value=event_data.barcode_value,
                barcode_type=event_data.barcode_type,
                ocr_raw_text=event_data.ocr_raw_text,
                extracted_order_id=event_data.extracted_order_id,
                extracted_awb=event_data.extracted_awb,
                scanned_at_utc=server_timestamp,  # Server timestamp, ignore client
                scanned_at_local=event_data.scanned_at_local,
                device_id=event_data.device_id,
                operator_id=ctx.user_id,
                confidence_score=event_data.confidence_score,
                sync_status=SyncStatus.SYNCED,
            )
            db.add(scan_event)
            await db.flush()  # Get the ID
            
            results.append(BulkScanResult(
                barcode_value=event_data.barcode_value,
                success=True,
                scan_event_id=scan_event.id,
            ))
            inserted_count += 1
            
        except Exception as e:
            results.append(BulkScanResult(
                barcode_value=event_data.barcode_value,
                success=False,
                error=str(e),
            ))
            error_count += 1
    
    try:
        await db.commit()
        # Trigger Bridge Sync to Main Backend
        try:
            from app.core.bridge import BridgeService
            # Get user email for better attribution in main backend
            user_email = ctx.user_email if hasattr(ctx, 'user_email') else "mobile_user"
            
            batch_data = {
                "batch_id": f"bulk-{server_timestamp.strftime('%Y%m%d%H%M%S')}-{ctx.user_id[:8]}",
                "batch_name": f"Mobile Bulk Sync - {server_timestamp.strftime('%H:%M')}",
                "scan_type": manifests[list(manifest_ids)[0]].flow_type.value if manifest_ids else "DISPATCH",
                "total_scans": len(request.events),
                "inserted_scans": inserted_count,
                "created_at": server_timestamp.isoformat(),
                "operator_email": user_email,
                "scans": [
                    {
                        "scan_code": e.barcode_value,
                        "timestamp": server_timestamp.isoformat(),
                        "meta_data": {
                            "packer": user_email,
                            "manifest_id": e.manifest_id,
                            "device": e.device_id
                        }
                    } for e in request.events
                ]
            }
            await BridgeService.sync_batch_to_main_backend(batch_data, ctx.tenant_id)
        except Exception as bridge_err:
            logger.error(f"Bridge sync failed but local commit succeeded: {bridge_err}")
            
    except Exception as e:
        logger.exception(f"Failed to commit bulk scan events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database commit failed: {type(e).__name__}: {str(e)}"
        )
    
    logger.info(
        f"Bulk scan: received={len(request.events)}, inserted={inserted_count}, "
        f"duplicates={duplicate_count}, errors={error_count}, tenant={ctx.tenant_id}"
    )
    
    return BulkScanResponse(
        total_received=len(request.events),
        total_inserted=inserted_count,
        total_duplicates=duplicate_count,
        total_errors=error_count,
        results=results,
    )


@router.get("", response_model=ScanEventListResponse)
async def list_scan_events(
    ctx: TenantCtx,
    db: DbSession,
    manifest_id: str = Query(..., description="Filter by manifest ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
):
    """List scan events for a specific manifest."""
    # Verify manifest belongs to tenant
    manifest_result = await db.execute(
        select(Manifest)
        .where(
            Manifest.id == manifest_id,
            Manifest.tenant_id == ctx.tenant_id
        )
    )
    manifest = manifest_result.scalar_one_or_none()
    
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manifest not found",
        )
    
    # Count total
    count_result = await db.execute(
        select(func.count(ScanEvent.id))
        .where(ScanEvent.manifest_id == manifest_id)
    )
    total = count_result.scalar() or 0
    
    # Get events with pagination
    offset = (page - 1) * page_size
    events_result = await db.execute(
        select(ScanEvent)
        .where(ScanEvent.manifest_id == manifest_id)
        .order_by(ScanEvent.scanned_at_utc.desc())
        .offset(offset)
        .limit(page_size)
    )
    events = events_result.scalars().all()
    
    return ScanEventListResponse(
        events=[ScanEventResponse.model_validate(e) for e in events],
        total=total,
    )


@router.get("/me", response_model=ScanEventListResponse)
async def list_my_scan_events(
    ctx: TenantCtx,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """List scan events for the current operator across all manifests."""
    # Count total
    count_result = await db.execute(
        select(func.count(ScanEvent.id))
        .where(
            ScanEvent.operator_id == ctx.user_id,
            ScanEvent.tenant_id == ctx.tenant_id
        )
    )
    total = count_result.scalar() or 0
    
    # Get events with pagination
    offset = (page - 1) * page_size
    events_result = await db.execute(
        select(ScanEvent)
        .where(
            ScanEvent.operator_id == ctx.user_id,
            ScanEvent.tenant_id == ctx.tenant_id
        )
        .order_by(ScanEvent.scanned_at_utc.desc())
        .offset(offset)
        .limit(page_size)
    )
    events = events_result.scalars().all()
    
    return ScanEventListResponse(
        events=[ScanEventResponse.model_validate(e) for e in events],
        total=total,
    )


@router.get("/{scan_event_id}", response_model=ScanEventResponse)
async def get_scan_event(
    scan_event_id: str,
    ctx: TenantCtx,
    db: DbSession,
):
    """Get a specific scan event by ID."""
    result = await db.execute(
        select(ScanEvent)
        .where(
            ScanEvent.id == scan_event_id,
            ScanEvent.tenant_id == ctx.tenant_id
        )
    )
    event = result.scalar_one_or_none()
    
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan event not found",
        )
    
    return ScanEventResponse.model_validate(event)
