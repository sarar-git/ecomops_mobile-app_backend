"""Tenant schemas."""
from datetime import datetime
from pydantic import BaseModel

from app.core.enums import TenantPlan


class TenantBase(BaseModel):
    """Base tenant schema."""
    name: str
    plan: TenantPlan = TenantPlan.FREE


class TenantResponse(BaseModel):
    """Tenant response schema."""
    id: str
    name: str
    plan: TenantPlan
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
