"""Scan API schemas for guide-compliant batch scanning."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.core.enums import FlowType


class ScanMetadata(BaseModel):
    """Metadata for a scan."""
    device: Optional[str] = None
    packer: Optional[str] = None
    location: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None


class BatchScanItem(BaseModel):
    """Single scan item in batch request."""
    scan_code: str = Field(..., min_length=1, max_length=500, description="AWB or Order ID")
    timestamp: Optional[datetime] = None
    meta_data: Optional[ScanMetadata] = None


class BatchScanRequest(BaseModel):
    """Guide-compliant batch scan request."""
    batch_name: Optional[str] = Field(None, max_length=255, description="Optional batch identifier")
    scan_type: FlowType = Field(..., description="DISPATCH or RETURN")
    scans: List[BatchScanItem] = Field(..., min_length=1, max_length=1000, description="Array of scans")


class BatchScanResult(BaseModel):
    """Result for a single scan in batch."""
    scan_code: str
    success: bool
    error: Optional[str] = None
    is_duplicate: bool = False


class BatchScanResponse(BaseModel):
    """Guide-compliant response for batch scan operation."""
    message: str
    batch_id: str = Field(..., description="Unique batch identifier")
    total_scans: int
    matched_orders: int = Field(default=0, description="Number of successfully processed scans")
    results: Optional[List[BatchScanResult]] = None


class BatchScanStatusResponse(BaseModel):
    """Response for batch status check."""
    batch_id: str
    batch_name: Optional[str]
    scan_type: FlowType
    total_scans: int
    processed_scans: int
    matched_orders: int
    created_at: datetime
    status: str = Field(default="completed", description="completed, processing, or failed")
