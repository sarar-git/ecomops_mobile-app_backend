"""Warehouse model."""
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.core.database import Base


class Warehouse(Base):
    """Warehouse model representing a physical location."""
    
    __tablename__ = "wh_warehouses"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
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
        Index("ix_warehouse_tenant_city", "tenant_id", "city"),
    )
