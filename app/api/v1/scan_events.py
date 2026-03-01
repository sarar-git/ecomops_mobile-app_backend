"""Scan Events API endpoints."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query, BackgroundTasks
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
    background_tasks: BackgroundTasks,
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
    seen_barcodes = set()
    
    for event_data in request.events:
        manifest = manifests.get(event_data.manifest_id)
        barcode = event_data.barcode_value
        
        # Check manifest exists
        if manifest is None:
            results.append(BulkScanResult(
                barcode_value=barcode,
                success=False,
                error=f"Manifest {event_data.manifest_id} not found",
            ))
            error_count += 1
            continue
        
        # Check manifest is OPEN
        if manifest.status != ManifestStatus.OPEN:
            results.append(BulkScanResult(
                barcode_value=barcode,
                success=False,
                error=f"Manifest {event_data.manifest_id} is closed",
            ))
            error_count += 1
            continue

        # Check for duplicates WITHIN the same request
        if barcode in seen_barcodes:
            results.append(BulkScanResult(
                barcode_value=barcode,
                success=True,
                is_duplicate=True,
            ))
            duplicate_count += 1
            continue
        
        # Check for existing scan in DB (duplicate detection)
        # Optimization: We could do this in one query outside the loop if performance is an issue
        existing_result = await db.execute(
            select(ScanEvent.id)
            .where(
                ScanEvent.manifest_id == event_data.manifest_id,
                ScanEvent.barcode_value == barcode
            )
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            results.append(BulkScanResult(
                barcode_value=barcode,
                success=True,
                scan_event_id=existing,
                is_duplicate=True,
            ))
            duplicate_count += 1
            seen_barcodes.add(barcode)
            continue
        
        # Create new scan event
        try:
            # We use a sub-transaction (savepoint) for each insert to handle 
            # race conditions where a scan is inserted by another request 
            # between our check and our insert.
            async with db.begin_nested():
                scan_event = ScanEvent(
                    tenant_id=ctx.tenant_id,
                    warehouse_id=manifest.warehouse_id,
                    manifest_id=manifest.id,
                    flow_type=manifest.flow_type,
                    marketplace=manifest.marketplace,
                    carrier=manifest.carrier,
                    barcode_value=barcode,
                    barcode_type=event_data.barcode_type,
                    ocr_raw_text=event_data.ocr_raw_text,
                    extracted_order_id=event_data.extracted_order_id,
                    extracted_awb=event_data.extracted_awb,
                    scanned_at_utc=server_timestamp,
                    scanned_at_local=event_data.scanned_at_local,
                    device_id=event_data.device_id,
                    operator_id=ctx.user_id,
                    confidence_score=event_data.confidence_score,
                    sync_status=SyncStatus.SYNCED,
                )
                db.add(scan_event)
                await db.flush()
                
                results.append(BulkScanResult(
                    barcode_value=barcode,
                    success=True,
                    scan_event_id=scan_event.id,
                ))
                inserted_count += 1
                seen_barcodes.add(barcode)

        except Exception as e:
            # If sub-transaction fails (e.g. UniqueViolation), 
            # check if it was a duplicate that just appeared.
            if "UniqueViolation" in str(e) or "unique constraint" in str(e).lower():
                results.append(BulkScanResult(
                    barcode_value=barcode,
                    success=True,
                    is_duplicate=True,
                ))
                duplicate_count += 1
                seen_barcodes.add(barcode)
            else:
                logger.error(f"Error inserting scan {barcode}: {e}")
                results.append(BulkScanResult(
                    barcode_value=barcode,
                    success=False,
                    error=str(e),
                ))
                error_count += 1
    
    try:
        import time
        start_time = time.time()
        await db.commit()
        commit_duration = time.time() - start_time
        
        # Only sync successful scans (new or duplicates)
        successful_events = [
            e for e in request.events 
            if any(r.barcode_value == e.barcode_value and r.success for r in results)
        ]
        
        if not successful_events:
            logger.info("No successful scans to sync to bridge. Skipping.")
        else:
            # Trigger Bridge Sync to Main Backend
            from app.core.bridge import BridgeService
            # Get user email for better attribution in main backend
            user_email = ctx.user_email
            
            # Get the first available valid manifest to determine scan_type for the bridge
            valid_manifests = list(manifests.values())
            scan_type = valid_manifests[0].flow_type.value if valid_manifests else "DISPATCH"
            
            batch_data = {
                "batch_id": f"bulk-{server_timestamp.strftime('%Y%m%d%H%M%S')}-{ctx.user_id[:8]}",
                "batch_name": f"Mobile Bulk Sync - {server_timestamp.strftime('%H:%M')}",
                "scan_type": scan_type,
                "total_scans": len(successful_events),
                "inserted_scans": inserted_count,
                "created_at": server_timestamp.isoformat(),
                "operator_email": user_email,
                "scans": [
                    {
                        "scan_code": e.barcode_value,
                        "timestamp": e.scanned_at_local.isoformat() if hasattr(e.scanned_at_local, 'isoformat') else server_timestamp.isoformat(),
                        "meta_data": {
                            "packer": user_email,
                            "manifest_id": e.manifest_id,
                            "device_id": e.device_id
                        }
                    } for e in successful_events
                ]
            }

            # Trigger sync in background to prevent mobile timeout
            background_tasks.add_task(
                BridgeService.sync_batch_to_main_backend,
                batch_data,
                ctx.tenant_id
            )
            
            logger.info(f"Bulk scan committed (took {commit_duration:.2f}s). Bridge sync queued for {len(successful_events)} scans.")
            
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
    days: Optional[int] = Query(31, ge=1, le=365, description="Number of days of history to fetch"),
):
    """List scan events for the current operator across all manifests."""
    from datetime import timedelta
    
    # Calculate cutoff date if days is provided
    cutoff_date = None
    if days:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    filters = [
        ScanEvent.operator_id == ctx.user_id,
        ScanEvent.tenant_id == ctx.tenant_id
    ]
    if cutoff_date:
        filters.append(ScanEvent.scanned_at_utc >= cutoff_date)

    # Count total
    count_result = await db.execute(
        select(func.count(ScanEvent.id))
        .where(*filters)
    )
    total = count_result.scalar() or 0
    
    # Get events with pagination
    offset = (page - 1) * page_size
    events_result = await db.execute(
        select(ScanEvent)
        .where(*filters)
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
