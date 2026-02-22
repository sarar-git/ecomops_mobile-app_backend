"""Warehouse schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class WarehouseBase(BaseModel):
    """Base warehouse schema."""
    name: str
    city: str
    address: Optional[str] = None
    timezone: str = "Asia/Kolkata"


class WarehouseCreate(WarehouseBase):
    """Warehouse creation schema."""
    pass


class WarehouseResponse(BaseModel):
    """Warehouse response schema."""
    id: str
    tenant_id: str
    name: str
    city: str
    address: Optional[str] = None
    timezone: str
    created_at: datetime
    
    class Config:
        from_attributes = True
