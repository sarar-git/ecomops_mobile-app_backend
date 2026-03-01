"""ScanEvent model."""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    String, DateTime, ForeignKey, Enum as SQLEnum, 
    Index, UniqueConstraint, Numeric, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.core.database import Base
from app.core.enums import FlowType, Marketplace, Carrier, BarcodeType, SyncStatus


class ScanEvent(Base):
    """ScanEvent model representing a single barcode scan."""
    
    __tablename__ = "lgs_scan_events"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("wh_warehouses.id", ondelete="CASCADE"),
        nullable=False
    )
    manifest_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("manifests.id", ondelete="CASCADE"),
        nullable=False
    )
    flow_type: Mapped[FlowType] = mapped_column(SQLEnum(FlowType), nullable=False)
    marketplace: Mapped[Marketplace] = mapped_column(SQLEnum(Marketplace), nullable=False)
    carrier: Mapped[Carrier] = mapped_column(SQLEnum(Carrier), nullable=False)
    barcode_value: Mapped[str] = mapped_column(String(500), nullable=False)
    barcode_type: Mapped[BarcodeType] = mapped_column(
        SQLEnum(BarcodeType),
        default=BarcodeType.UNKNOWN,
        nullable=False
    )
    ocr_raw_text: Mapped[str] = mapped_column(Text, nullable=True)
    extracted_order_id: Mapped[str] = mapped_column(String(100), nullable=True)
    extracted_awb: Mapped[str] = mapped_column(String(100), nullable=True)
    scanned_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    scanned_at_local: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    device_id: Mapped[str] = mapped_column(String(100), nullable=True)
    operator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=True
    )
    sync_status: Mapped[SyncStatus] = mapped_column(
        SQLEnum(SyncStatus),
        default=SyncStatus.SYNCED,
        nullable=False
    )
    
    # Relationships
    tenant = relationship("Tenant", back_populates="scan_events")
    warehouse = relationship("Warehouse", back_populates="scan_events")
    manifest = relationship("Manifest", back_populates="scan_events")
    operator = relationship("User", back_populates="scan_events")
    
    __table_args__ = (
        # Unique constraint on manifest + barcode (idempotent scans)
        UniqueConstraint("manifest_id", "barcode_value", name="uq_scan_manifest_barcode"),
        # Performance indexes
        Index("ix_scan_tenant_scanned", "tenant_id", "scanned_at_utc"),
        Index("ix_scan_tenant_manifest", "tenant_id", "manifest_id"),
        Index("ix_scan_awb", "extracted_awb"),
        Index("ix_scan_order_id", "extracted_order_id"),
    )
