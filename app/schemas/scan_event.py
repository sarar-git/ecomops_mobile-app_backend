"""Scan event schemas."""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

from app.core.enums import FlowType, Marketplace, Carrier, BarcodeType, SyncStatus


from typing import Optional, List, Union, Any

class ScanEventCreate(BaseModel):
    """Schema for creating a single scan event."""
    manifest_id: str
    barcode_value: str
    barcode_type: Any = "UNKNOWN"
    ocr_raw_text: Optional[str] = None
    extracted_order_id: Optional[str] = None
    extracted_awb: Optional[str] = None
    scanned_at_local: Any = None
    device_id: Optional[str] = None
    confidence_score: Any = None

    class Config:
        extra = "ignore"

    @field_validator("barcode_type", mode="before")
    @classmethod
    def validate_barcode_type(cls, v: Any) -> str:
        if not v: return "UNKNOWN"
        v_str = str(v).upper()
        if "QR" in v_str: return "QR"
        if "128" in v_str: return "CODE128"
        if "39" in v_str: return "CODE39"
        if "EAN13" in v_str: return "EAN13"
        return v_str if v_str in ["QR", "CODE128", "CODE39", "EAN13", "UNKNOWN"] else "UNKNOWN"

    @field_validator("scanned_at_local", mode="before")
    @classmethod
    def validate_scanned_at(cls, v: Any) -> Optional[datetime]:
        if not v: return None
        if isinstance(v, datetime): return v
        try:
            return datetime.fromisoformat(str(v).replace('Z', '+00:00'))
        except: return None


class ScanEventBulkRequest(BaseModel):
    """Schema for bulk scan event creation."""
    events: List[ScanEventCreate] = Field(..., min_length=1, max_length=1000)


class ScanEventResponse(BaseModel):
    """Scan event response schema."""
    id: str
    tenant_id: str
    warehouse_id: int
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
