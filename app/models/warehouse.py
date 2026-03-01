"""Warehouse model."""
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.core.database import Base


class Warehouse(Base):
    """Warehouse model representing a physical location."""
    
    __tablename__ = "wh_warehouses"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # Relationships
    tenant = relationship("Tenant", back_populates="warehouses")
    users = relationship("User", back_populates="warehouse")
    manifests = relationship("Manifest", back_populates="warehouse")
    scan_events = relationship("ScanEvent", back_populates="warehouse")
    
    __table_args__ = (
        Index("ix_warehouse_tenant_location", "tenant_id", "location"),
    )
