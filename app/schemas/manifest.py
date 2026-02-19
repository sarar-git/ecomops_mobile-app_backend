"""Manifest schemas."""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field

from app.core.enums import Marketplace, Carrier, FlowType, Shift, ManifestStatus


class ManifestStartRequest(BaseModel):
    """Request to start a new manifest."""
    warehouse_id: str
    manifest_date: date
    shift: Shift
    marketplace: Marketplace
    carrier: Carrier
    flow_type: FlowType


class ManifestResponse(BaseModel):
    """Manifest response schema."""
    id: str
    tenant_id: str
    warehouse_id: str
    manifest_date: date
    shift: Shift
    marketplace: Marketplace
    carrier: Carrier
    flow_type: FlowType
    status: ManifestStatus
    created_by: Optional[str] = None
    created_at_utc: datetime
    closed_at_utc: Optional[datetime] = None
    total_packets: int
    
    class Config:
        from_attributes = True


class ManifestListResponse(BaseModel):
    """List of manifests response."""
    manifests: List[ManifestResponse]
    total: int
    page: int
    page_size: int


class ManifestCloseResponse(BaseModel):
    """Response after closing a manifest."""
    id: str
    status: ManifestStatus
    closed_at_utc: datetime
    total_packets: int
