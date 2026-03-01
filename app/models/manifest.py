"""Manifest model."""
from datetime import datetime, timezone, date
from sqlalchemy import (
    String, Integer, DateTime, Date, ForeignKey, 
    Enum as SQLEnum, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.core.database import Base
from app.core.enums import Marketplace, Carrier, FlowType, Shift, ManifestStatus


class Manifest(Base):
    """Manifest model representing a scanning session/batch."""
    
    __tablename__ = "manifests"
    
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
    warehouse_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("wh_warehouses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    manifest_date: Mapped[date] = mapped_column(Date, nullable=False)
    shift: Mapped[Shift] = mapped_column(SQLEnum(Shift), nullable=False)
    marketplace: Mapped[Marketplace] = mapped_column(SQLEnum(Marketplace), nullable=False)
    carrier: Mapped[Carrier] = mapped_column(SQLEnum(Carrier), nullable=False)
    flow_type: Mapped[FlowType] = mapped_column(SQLEnum(FlowType), nullable=False)
    status: Mapped[ManifestStatus] = mapped_column(
        SQLEnum(ManifestStatus),
        default=ManifestStatus.OPEN,
        nullable=False
    )
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    closed_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    total_packets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="manifests")
    warehouse = relationship("Warehouse", back_populates="manifests")
    created_by_user = relationship("User", back_populates="created_manifests")
    scan_events = relationship("ScanEvent", back_populates="manifest", cascade="all, delete-orphan")
    
    __table_args__ = (
        # Only one OPEN manifest per combination
        Index(
            "ix_manifest_open_unique",
            "tenant_id", "warehouse_id", "manifest_date", 
            "shift", "marketplace", "carrier", "flow_type",
            unique=True,
            postgresql_where="status = 'OPEN'"
        ),
        Index("ix_manifest_tenant_date", "tenant_id", "manifest_date"),
        Index("ix_manifest_status", "status"),
    )
