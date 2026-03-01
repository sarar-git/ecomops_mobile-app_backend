"""Warehouse schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class WarehouseBase(BaseModel):
    """Base warehouse schema."""
    name: str
    location: Optional[str] = None
    type: str = "INTERNAL"


class WarehouseCreate(WarehouseBase):
    """Warehouse creation schema."""
    pass


class WarehouseResponse(BaseModel):
    """Warehouse response schema."""
    id: int
    tenant_id: str
    name: str
    location: Optional[str] = None
    type: str = "INTERNAL"
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
