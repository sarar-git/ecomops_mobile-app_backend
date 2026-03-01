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
    if 'pd_scan_events' in existing_tables and 'lgs_scan_events' not in existing_tables:
        op.rename_table('pd_scan_events', 'lgs_scan_events')
        print("Renamed pd_scan_events to lgs_scan_events")
    elif 'scan_events' in existing_tables and 'lgs_scan_events' not in existing_tables:
        op.rename_table('scan_events', 'lgs_scan_events')
        print("Renamed scan_events to lgs_scan_events")

    # Refresh inspector after potential renames
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # FUNCTION: Drop FK if exists
    def drop_fk_safely(table_name, fk_name):
        try:
            op.drop_constraint(fk_name, table_name, type_='foreignkey')
            print(f"Dropped FK {fk_name} from {table_name}")
        except Exception:
            pass # Ignore if doesn't exist

    # 2. Drop existing FK constraints that might block type conversion
    # These point to the legacy 'warehouses' table which has VARCHAR 'id'
    fks_to_drop = [
        ('users', 'fk_users_warehouse_id_warehouses'),
        ('users', 'users_warehouse_id_fkey'),
        ('manifests', 'fk_manifests_warehouse_id_warehouses'),
        ('manifests', 'manifests_warehouse_id_fkey'),
        ('lgs_scan_events', 'pd_scan_events_warehouse_id_fkey'),
        ('lgs_scan_events', 'lgs_scan_events_warehouse_id_fkey'),
        ('lgs_scan_events', 'fk_scan_events_warehouse_id_warehouses'),
    ]
    for table, fk in fks_to_drop:
        if table in existing_tables:
            drop_fk_safely(table, fk)

    # 3. Alter columns to INTEGER
    if 'users' in existing_tables:
        op.execute("ALTER TABLE users ALTER COLUMN warehouse_id TYPE INTEGER USING warehouse_id::integer")
        print("Altered users.warehouse_id to INTEGER")

    if 'manifests' in existing_tables:
        op.execute("ALTER TABLE manifests ALTER COLUMN warehouse_id TYPE INTEGER USING warehouse_id::integer")
        print("Altered manifests.warehouse_id to INTEGER")

    if 'lgs_scan_events' in existing_tables:
        op.execute("ALTER TABLE lgs_scan_events ALTER COLUMN warehouse_id TYPE INTEGER USING warehouse_id::integer")
        print("Altered lgs_scan_events.warehouse_id to INTEGER")

    # 4. Re-add FK constraints pointing to THE CORRECT 'wh_warehouses' table
    if 'wh_warehouses' in existing_tables:
        op.create_foreign_key(
            'fk_users_warehouse_id_wh_warehouses', 
            'users', 'wh_warehouses', ['warehouse_id'], ['id'], ondelete='SET NULL'
        )
        op.create_foreign_key(
            'fk_manifests_warehouse_id_wh_warehouses', 
            'manifests', 'wh_warehouses', ['warehouse_id'], ['id'], ondelete='CASCADE'
        )
        op.create_foreign_key(
            'fk_lgs_scan_events_warehouse_id_wh_warehouses', 
            'lgs_scan_events', 'wh_warehouses', ['warehouse_id'], ['id'], ondelete='CASCADE'
        )
        print("Re-created foreign keys pointing to wh_warehouses")

    # 5. Final cleanup of legacy table
    if 'warehouses' in existing_tables:
        op.execute("DROP TABLE IF EXISTS warehouses CASCADE")
        print("Dropped legacy 'warehouses' table with CASCADE")


def downgrade() -> None:
    # Downgrade logic is to revert types to String if needed, 
    # but for this harmonization we stay with Integer.
    pass
