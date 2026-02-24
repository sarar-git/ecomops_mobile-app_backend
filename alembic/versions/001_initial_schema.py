"""Initial schema with all tables

Revision ID: 001_initial_schema
Revises: 
Create Date: 2024-01-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tenants table
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('plan', sa.Enum('FREE', 'BASIC', 'PRO', 'ENTERPRISE', name='tenantplan'), nullable=False, server_default='FREE'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Warehouses table
    op.create_table(
        'warehouses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('city', sa.String(100), nullable=False),
        sa.Column('address', sa.String(500), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Asia/Kolkata'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_warehouse_tenant_id', 'warehouses', ['tenant_id'])
    op.create_index('ix_warehouse_tenant_city', 'warehouses', ['tenant_id', 'city'])

    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id', ondelete='SET NULL'), nullable=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('role', sa.Enum('ADMIN', 'MANAGER', 'OPERATOR', 'MOBILE_USER', 'authenticated', name='userrole'), nullable=False, server_default='OPERATOR'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_user_tenant_id', 'users', ['tenant_id'])
    op.create_index('ix_user_warehouse_id', 'users', ['warehouse_id'])
    op.create_index('ix_user_tenant_email', 'users', ['tenant_id', 'email'], unique=True)

    # Manifests table
    op.create_table(
        'manifests',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('manifest_date', sa.Date(), nullable=False),
        sa.Column('shift', sa.Enum('MORNING', 'EVENING', 'NIGHT', name='shift'), nullable=False),
        sa.Column('marketplace', sa.Enum('AMAZON', 'FLIPKART', 'MYNTRA', 'JIOMART', 'MEESHO', 'AJIO', name='marketplace'), nullable=False),
        sa.Column('carrier', sa.Enum('DELHIVERY', 'EKART', 'SHADOWFAX', 'BLUEDART', 'AMAZON_SHIPPING', name='carrier'), nullable=False),
        sa.Column('flow_type', sa.Enum('DISPATCH', 'RETURN', name='flowtype'), nullable=False),
        sa.Column('status', sa.Enum('OPEN', 'CLOSED', name='manifeststatus'), nullable=False, server_default='OPEN'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at_utc', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('closed_at_utc', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_packets', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_manifest_tenant_id', 'manifests', ['tenant_id'])
    op.create_index('ix_manifest_warehouse_id', 'manifests', ['warehouse_id'])
    op.create_index('ix_manifest_tenant_date', 'manifests', ['tenant_id', 'manifest_date'])
    op.create_index('ix_manifest_status', 'manifests', ['status'])
    
    # Partial unique index for OPEN manifests
    op.execute("""
        CREATE UNIQUE INDEX ix_manifest_open_unique 
        ON manifests (tenant_id, warehouse_id, manifest_date, shift, marketplace, carrier, flow_type)
        WHERE status = 'OPEN'
    """)

    # Scan Events table
    op.create_table(
        'scan_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('warehouse_id', sa.String(36), sa.ForeignKey('warehouses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('manifest_id', sa.String(36), sa.ForeignKey('manifests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('flow_type', sa.Enum('DISPATCH', 'RETURN', name='flowtype', create_type=False), nullable=False),
        sa.Column('marketplace', sa.Enum('AMAZON', 'FLIPKART', 'MYNTRA', 'JIOMART', 'MEESHO', 'AJIO', name='marketplace', create_type=False), nullable=False),
        sa.Column('carrier', sa.Enum('DELHIVERY', 'EKART', 'SHADOWFAX', 'BLUEDART', 'AMAZON_SHIPPING', name='carrier', create_type=False), nullable=False),
        sa.Column('barcode_value', sa.String(500), nullable=False),
        sa.Column('barcode_type', sa.Enum('QR', 'CODE128', 'CODE39', 'EAN13', 'UNKNOWN', name='barcodetype'), nullable=False, server_default='UNKNOWN'),
        sa.Column('ocr_raw_text', sa.Text(), nullable=True),
        sa.Column('extracted_order_id', sa.String(100), nullable=True),
        sa.Column('extracted_awb', sa.String(100), nullable=True),
        sa.Column('scanned_at_utc', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('scanned_at_local', sa.DateTime(timezone=True), nullable=True),
        sa.Column('device_id', sa.String(100), nullable=True),
        sa.Column('operator_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('confidence_score', sa.Numeric(5, 4), nullable=True),
        sa.Column('sync_status', sa.Enum('PENDING', 'SYNCED', 'FAILED', name='syncstatus'), nullable=False, server_default='SYNCED'),
    )
    
    # Unique constraint for idempotent scans
    op.create_unique_constraint('uq_scan_manifest_barcode', 'scan_events', ['manifest_id', 'barcode_value'])
    
    # Performance indexes
    op.create_index('ix_scan_tenant_scanned', 'scan_events', ['tenant_id', 'scanned_at_utc'])
    op.create_index('ix_scan_tenant_manifest', 'scan_events', ['tenant_id', 'manifest_id'])
    op.create_index('ix_scan_awb', 'scan_events', ['extracted_awb'])
    op.create_index('ix_scan_order_id', 'scan_events', ['extracted_order_id'])


def downgrade() -> None:
    op.drop_table('scan_events')
    op.drop_table('manifests')
    op.drop_table('users')
    op.drop_table('warehouses')
    op.drop_table('tenants')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS syncstatus')
    op.execute('DROP TYPE IF EXISTS barcodetype')
    op.execute('DROP TYPE IF EXISTS manifeststatus')
    op.execute('DROP TYPE IF EXISTS flowtype')
    op.execute('DROP TYPE IF EXISTS carrier')
    op.execute('DROP TYPE IF EXISTS marketplace')
    op.execute('DROP TYPE IF EXISTS shift')
    op.execute('DROP TYPE IF EXISTS userrole')
    op.execute('DROP TYPE IF EXISTS tenantplan')
