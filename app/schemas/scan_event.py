"""Scan event schemas."""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field

from app.core.enums import FlowType, Marketplace, Carrier, BarcodeType, SyncStatus


class ScanEventCreate(BaseModel):
    """Schema for creating a single scan event."""
    manifest_id: str
    barcode_value: str = Field(..., min_length=1, max_length=500)
    barcode_type: BarcodeType = BarcodeType.UNKNOWN
    ocr_raw_text: Optional[str] = None
    extracted_order_id: Optional[str] = None
    extracted_awb: Optional[str] = None
    scanned_at_local: Optional[datetime] = None
    device_id: Optional[str] = None
    confidence_score: Optional[Decimal] = Field(None, ge=0, le=1)


class ScanEventBulkRequest(BaseModel):
    """Schema for bulk scan event creation."""
    events: List[ScanEventCreate] = Field(..., min_length=1, max_length=1000)


class ScanEventResponse(BaseModel):
    """Scan event response schema."""
    id: str
    tenant_id: str
    warehouse_id: str
    manifest_id: str
    flow_type: FlowType
    marketplace: Marketplace
    carrier: Carrier
    barcode_value: str
    barcode_type: BarcodeType
    ocr_raw_text: Optional[str] = None
    extracted_order_id: Optional[str] = None
    extracted_awb: Optional[str] = None
    scanned_at_utc: datetime
    scanned_at_local: Optional[datetime] = None
    device_id: Optional[str] = None
    operator_id: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    sync_status: SyncStatus
    
    class Config:
        from_attributes = True


class BulkScanResult(BaseModel):
    """Result for a single scan in bulk operation."""
    barcode_value: str
    success: bool
    scan_event_id: Optional[str] = None
    error: Optional[str] = None
    is_duplicate: bool = False


class BulkScanResponse(BaseModel):
    """Response for bulk scan operation."""
    total_received: int
    total_inserted: int
    total_duplicates: int
    total_errors: int
    results: List[BulkScanResult]


class ScanEventListResponse(BaseModel):
    """List of scan events response."""
    events: List[ScanEventResponse]
    total: int
