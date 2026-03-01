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
    print(f"DEBUG: Existing tables: {existing_tables}")

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

    # 2. Fix missing columns in 'wh_warehouses'
    if 'wh_warehouses' in existing_tables:
        cols = [c['name'] for c in inspector.get_columns('wh_warehouses')]
        if 'tenant_id' not in cols:
            op.add_column('wh_warehouses', sa.Column('tenant_id', sa.String(36), index=True, nullable=True))
            print("Added 'tenant_id' to 'wh_warehouses'")
        if 'code' not in cols:
            op.add_column('wh_warehouses', sa.Column('code', sa.String(50), index=True, nullable=True))
            # Set a default code for existing rows to avoid null constraints if we add them later
            op.execute("UPDATE wh_warehouses SET code = 'WH-' || id WHERE code IS NULL")
            print("Added 'code' to 'wh_warehouses'")
        if 'location' not in cols:
            op.add_column('wh_warehouses', sa.Column('location', sa.String(255), nullable=True))
            print("Added 'location' to 'wh_warehouses'")

    # FUNCTION: Dynamically find and drop ALL foreign keys on a column
    def drop_all_fks_on_column(table_name, col_name):
        if table_name not in existing_tables:
            return
            
        print(f"DEBUG: Discovering constraints for {table_name}.{col_name}")
        query = sa.text(f"""
            SELECT
                tc.constraint_name
            FROM
                information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' 
              AND tc.table_name = '{table_name}' 
              AND kcu.column_name = '{col_name}';
        """)
        
        try:
            result = conn.execute(query)
            for row in result:
                fk_name = row[0]
                print(f"DEBUG: Found FK {fk_name} on {table_name}.{col_name}. Dropping...")
                op.execute(sa.text(f'ALTER TABLE "{table_name}" DROP CONSTRAINT "{fk_name}" CASCADE'))
                print(f"SUCCESS: Dropped {fk_name}")
        except Exception as e:
            print(f"WARN: Error discovering/dropping constraints on {table_name}: {e}")

    # 3. Force drop ALL warehouse_id foreign keys before type alteration
    print("Discovering and dropping all warehouse_id foreign keys...")
    drop_all_fks_on_column('users', 'warehouse_id')
    drop_all_fks_on_column('manifests', 'warehouse_id')
    drop_all_fks_on_column('lgs_scan_events', 'warehouse_id')

    # 4. Alter columns to INTEGER
    print("Altering columns to INTEGER...")
    if 'users' in existing_tables:
        op.execute(sa.text('ALTER TABLE "users" ALTER COLUMN "warehouse_id" TYPE INTEGER USING "warehouse_id"::integer'))
        print("Altered users.warehouse_id")

    if 'manifests' in existing_tables:
        op.execute(sa.text('ALTER TABLE "manifests" ALTER COLUMN "warehouse_id" TYPE INTEGER USING "warehouse_id"::integer'))
        print("Altered manifests.warehouse_id")

    if 'lgs_scan_events' in existing_tables:
        op.execute(sa.text('ALTER TABLE "lgs_scan_events" ALTER COLUMN "warehouse_id" TYPE INTEGER USING "warehouse_id"::integer'))
        print("Altered lgs_scan_events.warehouse_id")

    # 5. Re-add FK constraints pointing to THE CORRECT 'wh_warehouses' table
    print("Re-creating foreign keys pointing to wh_warehouses...")
    if 'wh_warehouses' in existing_tables:
        try:
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
        except Exception as e:
            print(f"WARN: Error re-creating foreign keys: {e}")

    # 6. Final cleanup of legacy table
    if 'warehouses' in existing_tables:
        try:
            op.execute(sa.text('DROP TABLE IF EXISTS "warehouses" CASCADE'))
            print("Dropped legacy 'warehouses' table with CASCADE")
        except Exception as e:
            print(f"WARN: Error dropping legacy warehouses table: {e}")


def downgrade() -> None:
    # Downgrade logic is to revert types to String if needed, 
    # but for this harmonization we stay with Integer.
    pass
