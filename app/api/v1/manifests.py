"""Manifest API endpoints."""
from datetime import datetime, timezone, date
from typing import Optional
from io import StringIO
import csv

from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.core.dependencies import TenantCtx, DbSession
from app.core.enums import ManifestStatus, Marketplace, Carrier, FlowType, Shift
from app.core.logging import get_logger
from app.models.manifest import Manifest
from app.models.warehouse import Warehouse
from app.models.scan_event import ScanEvent
from app.schemas.manifest import (
    ManifestStartRequest, ManifestResponse, ManifestListResponse,
    ManifestCloseResponse
)


router = APIRouter()
logger = get_logger(__name__)


@router.post("/start", response_model=ManifestResponse, status_code=status.HTTP_201_CREATED)
async def start_manifest(
    request: ManifestStartRequest,
    ctx: TenantCtx,
    db: DbSession,
):
    """Start a new manifest or resume an existing OPEN one."""
    try:
        # Verify warehouse belongs to tenant
        warehouse_result = await db.execute(
            select(Warehouse)
            .where(
                Warehouse.id == request.warehouse_id,
                Warehouse.tenant_id == ctx.tenant_id
            )
        )
        warehouse = warehouse_result.scalar_one_or_none()
        
        if warehouse is None:
            # Shift to 400 to distinguish from route 404 (shadowing)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Selected warehouse '{request.warehouse_id}' not found for your tenant.",
            )
        
        # Check for existing OPEN manifest with same combination
        existing_result = await db.execute(
            select(Manifest)
            .where(
                Manifest.tenant_id == ctx.tenant_id,
                Manifest.warehouse_id == request.warehouse_id,
                Manifest.manifest_date == request.manifest_date,
                Manifest.shift == request.shift,
                Manifest.marketplace == request.marketplace,
                Manifest.carrier == request.carrier,
                Manifest.flow_type == request.flow_type,
                Manifest.status == ManifestStatus.OPEN
            )
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            logger.info(f"Resuming existing manifest: {existing.id} for user {ctx.user_id}")
            return ManifestResponse.model_validate(existing)
        
        # Create new manifest
        manifest = Manifest(
            tenant_id=ctx.tenant_id,
            warehouse_id=request.warehouse_id,
            manifest_date=request.manifest_date,
            shift=request.shift,
            marketplace=request.marketplace,
            carrier=request.carrier,
            flow_type=request.flow_type,
            status=ManifestStatus.OPEN,
            created_by=ctx.user_id,
        )
        
        db.add(manifest)
        await db.commit()
        await db.refresh(manifest)
        
        logger.info(f"Manifest started: {manifest.id}, tenant: {ctx.tenant_id}")
        
        return ManifestResponse.model_validate(manifest)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unhandled error in start_manifest: {e}")
        error_msg = f"{type(e).__name__}: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start manifest: {error_msg}"
        )


@router.post("/{manifest_id}/close", response_model=ManifestCloseResponse)
async def close_manifest(
    manifest_id: str,
    ctx: TenantCtx,
    db: DbSession,
):
    """Close a manifest, locking it from further writes."""
    result = await db.execute(
        select(Manifest)
        .where(
            Manifest.id == manifest_id,
            Manifest.tenant_id == ctx.tenant_id
        )
    )
    manifest = result.scalar_one_or_none()
    
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manifest not found",
        )
    
    if manifest.status == ManifestStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manifest is already closed",
        )
    
    try:
        # Count total packets
        count_result = await db.execute(
            select(func.count(ScanEvent.id))
            .where(ScanEvent.manifest_id == manifest_id)
        )
        total_packets = count_result.scalar() or 0
        
        # Close the manifest
        manifest.status = ManifestStatus.CLOSED
        manifest.closed_at_utc = datetime.now(timezone.utc)
        manifest.total_packets = total_packets
        
        await db.commit()
        await db.refresh(manifest)
        
        logger.info(f"Manifest closed: {manifest_id}, packets: {total_packets}")
        
        return ManifestCloseResponse(
            id=manifest.id,
            status=manifest.status,
            closed_at_utc=manifest.closed_at_utc,
            total_packets=manifest.total_packets,
        )
    except Exception as e:
        logger.exception(f"Error closing manifest {manifest_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close manifest: {type(e).__name__}: {str(e)}"
        )


@router.get("", response_model=ManifestListResponse)
async def list_manifests(
    ctx: TenantCtx,
    db: DbSession,
    warehouse_id: Optional[str] = None,
    status_filter: Optional[ManifestStatus] = Query(None, alias="status"),
    marketplace: Optional[Marketplace] = None,
    carrier: Optional[Carrier] = None,
    flow_type: Optional[FlowType] = None,
    shift: Optional[Shift] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List manifests with optional filters."""
    query = select(Manifest).where(Manifest.tenant_id == ctx.tenant_id)
    count_query = select(func.count(Manifest.id)).where(Manifest.tenant_id == ctx.tenant_id)
    
    # Apply filters
    if warehouse_id:
        query = query.where(Manifest.warehouse_id == warehouse_id)
        count_query = count_query.where(Manifest.warehouse_id == warehouse_id)
    if status_filter:
        query = query.where(Manifest.status == status_filter)
        count_query = count_query.where(Manifest.status == status_filter)
    if marketplace:
        query = query.where(Manifest.marketplace == marketplace)
        count_query = count_query.where(Manifest.marketplace == marketplace)
    if carrier:
        query = query.where(Manifest.carrier == carrier)
        count_query = count_query.where(Manifest.carrier == carrier)
    if flow_type:
        query = query.where(Manifest.flow_type == flow_type)
        count_query = count_query.where(Manifest.flow_type == flow_type)
    if shift:
        query = query.where(Manifest.shift == shift)
        count_query = count_query.where(Manifest.shift == shift)
    if date_from:
        query = query.where(Manifest.manifest_date >= date_from)
        count_query = count_query.where(Manifest.manifest_date >= date_from)
    if date_to:
        query = query.where(Manifest.manifest_date <= date_to)
        count_query = count_query.where(Manifest.manifest_date <= date_to)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Manifest.created_at_utc.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    manifests = result.scalars().all()
    
    return ManifestListResponse(
        manifests=[ManifestResponse.model_validate(m) for m in manifests],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{manifest_id}", response_model=ManifestResponse)
async def get_manifest(
    manifest_id: str,
    ctx: TenantCtx,
    db: DbSession,
):
    """Get a specific manifest by ID."""
    result = await db.execute(
        select(Manifest)
        .where(
            Manifest.id == manifest_id,
            Manifest.tenant_id == ctx.tenant_id
        )
    )
    manifest = result.scalar_one_or_none()
    
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manifest not found",
        )
    
    return ManifestResponse.model_validate(manifest)


@router.get("/{manifest_id}/export.csv")
async def export_manifest_csv(
    manifest_id: str,
    ctx: TenantCtx,
    db: DbSession,
):
    """Export manifest scan events as CSV."""
    # Verify manifest exists and belongs to tenant
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
    
    # Get all scan events for the manifest
    events_result = await db.execute(
        select(ScanEvent)
        .where(ScanEvent.manifest_id == manifest_id)
        .order_by(ScanEvent.scanned_at_utc)
    )
    events = events_result.scalars().all()
    
    # Generate CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "barcode_value", "barcode_type", "extracted_order_id", "extracted_awb",
        "scanned_at_utc", "scanned_at_local", "device_id", "operator_id",
        "confidence_score", "flow_type", "marketplace", "carrier"
    ])
    
    # Data rows
    for event in events:
        writer.writerow([
            event.barcode_value,
            event.barcode_type.value,
            event.extracted_order_id or "",
            event.extracted_awb or "",
            event.scanned_at_utc.isoformat() if event.scanned_at_utc else "",
            event.scanned_at_local.isoformat() if event.scanned_at_local else "",
            event.device_id or "",
            event.operator_id or "",
            str(event.confidence_score) if event.confidence_score else "",
            event.flow_type.value,
            event.marketplace.value,
            event.carrier.value,
        ])
    
    output.seek(0)
    
    filename = f"manifest_{manifest_id}_{manifest.manifest_date}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
