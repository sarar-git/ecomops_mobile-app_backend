"""Scan API endpoints - Guide compliant batch scanning."""
from datetime import datetime, timezone
from typing import Optional
import uuid

from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select

from app.core.dependencies import TenantCtx, DbSession
from app.core.enums import ManifestStatus, SyncStatus, Shift, Marketplace, Carrier
from app.core.logging import get_logger
from app.models.manifest import Manifest
from app.models.scan_event import ScanEvent
from app.schemas.scan import (
    BatchScanRequest, BatchScanResponse, BatchScanResult, 
    BatchScanStatusResponse
)


router = APIRouter()
logger = get_logger(__name__)

# In-memory batch registry (in production, use Redis or DB)
batch_registry = {}


@router.post("/batch", response_model=BatchScanResponse, status_code=status.HTTP_201_CREATED)
async def batch_scan(
    request: BatchScanRequest,
    ctx: TenantCtx,
    db: DbSession,
):
    """
    Guide-compliant batch scanning endpoint.
    
    Accepts AWB/Order ID scans with optional metadata.
    Automatically creates or reuses manifest based on scan_type.
    
    Args:
        request: Batch scan request with scan items
        ctx: Tenant context from JWT token
        db: Database session
        
    Returns:
        BatchScanResponse with batch_id, matched_orders count, and results
    """
    batch_id = str(uuid.uuid4())
    results = []
    inserted_count = 0
    duplicate_count = 0
    error_count = 0
    
    try:
        # Get or create manifest for this batch
        # Manifests are organized by tenant, warehouse, flow_type, and manifest_date
        # For batch API, we'll use the operator's warehouse and today's date
        
        today = datetime.now(timezone.utc).date()
        
        # Get user's warehouse (required for batch operation)
        if not ctx.warehouse_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must be assigned to a warehouse to perform scans",
            )
        
        # Look for existing OPEN manifest for this flow_type today
        manifest_result = await db.execute(
            select(Manifest).where(
                Manifest.tenant_id == ctx.tenant_id,
                Manifest.warehouse_id == ctx.warehouse_id,
                Manifest.manifest_date == today,
                Manifest.flow_type == request.scan_type,
                Manifest.status == ManifestStatus.OPEN
            )
        )
        manifest = manifest_result.scalar_one_or_none()
        
        # If no manifest exists, create one
        if manifest is None:
            # For batch API, we use default values for marketplace/carrier/shift
            # In a full implementation, these could be configurable or passed in request
            manifest = Manifest(
                tenant_id=ctx.tenant_id,
                warehouse_id=ctx.warehouse_id,
                manifest_date=today,
                shift=Shift.MORNING,  # Default shift
                marketplace=Marketplace.AMAZON,  # Default marketplace
                carrier=Carrier.DELHIVERY,  # Default carrier
                flow_type=request.scan_type,
                status=ManifestStatus.OPEN,
                created_by=ctx.user_id,
            )
            db.add(manifest)
            await db.flush()
        
        # Process each scan
        server_timestamp = datetime.now(timezone.utc)
        
        for scan_item in request.scans:
            try:
                # Check for existing scan (duplicate detection)
                existing_result = await db.execute(
                    select(ScanEvent.id).where(
                        ScanEvent.manifest_id == manifest.id,
                        ScanEvent.barcode_value == scan_item.scan_code
                    )
                )
                existing_scan = existing_result.scalar_one_or_none()
                
                if existing_scan:
                    results.append(BatchScanResult(
                        scan_code=scan_item.scan_code,
                        success=True,
                        is_duplicate=True,
                    ))
                    duplicate_count += 1
                    continue
                
                # Create new scan event
                scan_event = ScanEvent(
                    tenant_id=ctx.tenant_id,
                    warehouse_id=manifest.warehouse_id,
                    manifest_id=manifest.id,
                    flow_type=manifest.flow_type,
                    marketplace=manifest.marketplace,
                    carrier=manifest.carrier,
                    barcode_value=scan_item.scan_code,
                    ocr_raw_text=scan_item.scan_code,  # Store as OCR text
                    scanned_at_utc=server_timestamp,  # Server timestamp
                    scanned_at_local=scan_item.timestamp,  # Client timestamp
                    device_id=scan_item.meta_data.device if scan_item.meta_data else None,
                    operator_id=ctx.user_id,
                    sync_status=SyncStatus.SYNCED,
                )
                db.add(scan_event)
                await db.flush()
                
                results.append(BatchScanResult(
                    scan_code=scan_item.scan_code,
                    success=True,
                ))
                inserted_count += 1
                
            except Exception as e:
                logger.error(f"Error processing scan {scan_item.scan_code}: {str(e)}")
                results.append(BatchScanResult(
                    scan_code=scan_item.scan_code,
                    success=False,
                    error=str(e),
                ))
                error_count += 1
        
        # Update manifest total packets count
        manifest.total_packets = inserted_count + duplicate_count
        
        # Commit all changes
        await db.commit()
        
        # Register batch in memory (for optional batch status tracking)
        batch_registry[batch_id] = {
            "batch_name": request.batch_name,
            "scan_type": request.scan_type.value,
            "manifest_id": manifest.id,
            "total_scans": len(request.scans),
            "inserted_scans": inserted_count,
            "duplicate_scans": duplicate_count,
            "error_scans": error_count,
            "matched_orders": inserted_count,  # Matched = inserted (no order matching logic yet)
            "created_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "status": "completed",
            "scans": [s.model_dump() for s in request.scans]
        }
        
        logger.info(
            f"Batch scan completed: batch_id={batch_id}, "
            f"inserted={inserted_count}, duplicates={duplicate_count}, "
            f"errors={error_count}, tenant={ctx.tenant_id}"
        )
        
        # Trigger Sync to Main Backend (Background Task would be better, but awaiting for now)
        from app.core.bridge import BridgeService
        await BridgeService.sync_batch_to_main_backend(
            batch_data=batch_registry[batch_id],
            tenant_id=ctx.tenant_id
        )
        
        return BatchScanResponse(
            message="Batch processed successfully",
            batch_id=batch_id,
            total_scans=len(request.scans),
            matched_orders=inserted_count,  # Count of successfully inserted scans
            results=results,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch scan error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch processing failed: {str(e)}",
        )


@router.get("/batch/{batch_id}", response_model=BatchScanStatusResponse)
async def get_batch_status(
    batch_id: str,
    ctx: TenantCtx,
):
    """
    Get status of a previously submitted batch.
    
    Args:
        batch_id: The batch identifier from previous batch submission
        ctx: Tenant context
        
    Returns:
        BatchScanStatusResponse with current status and counts
    """
    if batch_id not in batch_registry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found",
        )
    
    batch_info = batch_registry[batch_id]
    
    return BatchScanStatusResponse(
        batch_id=batch_id,
        batch_name=batch_info.get("batch_name"),
        scan_type=batch_info["scan_type"],
        total_scans=batch_info["total_scans"],
        processed_scans=batch_info["inserted_scans"] + batch_info["duplicate_scans"],
        matched_orders=batch_info["matched_orders"],
        created_at=batch_info["created_at"],
        status=batch_info.get("status", "completed"),
    )
