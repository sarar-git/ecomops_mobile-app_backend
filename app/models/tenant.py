"""Tenant model for multi-tenancy."""
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.core.database import Base
from app.core.enums import TenantPlan


class Tenant(Base):
    """Tenant model representing a company/organization."""
    
    __tablename__ = "tenants"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[TenantPlan] = mapped_column(
        SQLEnum(TenantPlan),
        default=TenantPlan.FREE,
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # Relationships
    warehouses = relationship("Warehouse", back_populates="tenant", cascade="all, delete-orphan")
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    manifests = relationship("Manifest", back_populates="tenant", cascade="all, delete-orphan")
    scan_events = relationship("ScanEvent", back_populates="tenant", cascade="all, delete-orphan")
