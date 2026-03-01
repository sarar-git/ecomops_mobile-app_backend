"""Fix types and renames

Revision ID: 002_fix_types_and_renames
Revises: 001_initial_schema
Create Date: 2026-03-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_fix_types_and_renames'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Helper to check if table exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Rename pd_scan_events to lgs_scan_events if it exists
    # If it's already lgs_scan_events, this will skip.
    if 'pd_scan_events' in existing_tables and 'lgs_scan_events' not in existing_tables:
        op.rename_table('pd_scan_events', 'lgs_scan_events')
        print("Renamed pd_scan_events to lgs_scan_events")
    elif 'scan_events' in existing_tables and 'lgs_scan_events' not in existing_tables:
        op.rename_table('scan_events', 'lgs_scan_events')
        print("Renamed scan_events to lgs_scan_events")

    # Refresh existing_tables after potential renames
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 2. Fix warehouse_id type in 'users'
    if 'users' in existing_tables:
        op.execute("ALTER TABLE users ALTER COLUMN warehouse_id TYPE INTEGER USING warehouse_id::integer")
        print("Altered users.warehouse_id to INTEGER")

    # 3. Fix warehouse_id type in 'manifests'
    if 'manifests' in existing_tables:
        op.execute("ALTER TABLE manifests ALTER COLUMN warehouse_id TYPE INTEGER USING warehouse_id::integer")
        print("Altered manifests.warehouse_id to INTEGER")

    # 4. Fix warehouse_id type in 'lgs_scan_events'
    if 'lgs_scan_events' in existing_tables:
        op.execute("ALTER TABLE lgs_scan_events ALTER COLUMN warehouse_id TYPE INTEGER USING warehouse_id::integer")
        print("Altered lgs_scan_events.warehouse_id to INTEGER")

    # 5. Clean up legacy 'warehouses' table if it exists alongside 'wh_warehouses'
    if 'warehouses' in existing_tables and 'wh_warehouses' in existing_tables:
        # Drop indices first to be clean
        try:
            op.drop_index('ix_warehouse_tenant_city', table_name='warehouses')
            op.drop_index('ix_warehouse_tenant_id', table_name='warehouses')
        except:
            pass
        op.drop_table('warehouses')
        print("Dropped legacy 'warehouses' table")


def downgrade() -> None:
    # Downgrade logic is to revert types to String if needed, 
    # but for this harmonization we stay with Integer.
    pass
