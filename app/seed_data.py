"""Seed data script to populate initial test data."""
import asyncio
import uuid
from datetime import datetime, timezone, date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, engine, Base
from app.core.security import get_password_hash
from app.core.enums import TenantPlan, UserRole, Marketplace, Carrier, FlowType, Shift
from app.models.tenant import Tenant
from app.models.warehouse import Warehouse
from app.models.user import User


async def seed_data():
    """Seed initial data for testing."""
    async with async_session_maker() as session:
        # Check if data already exists
        result = await session.execute(select(Tenant).limit(1))
        if result.scalar_one_or_none():
            print("Data already seeded. Skipping...")
            return
        
        # Create tenant
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name="Demo Logistics Co",
            plan=TenantPlan.PRO,
            is_active=True,
        )
        session.add(tenant)
        await session.flush()
        
        print(f"Created tenant: {tenant.name} (ID: {tenant.id})")
        
        # Create warehouses
        warehouses_data = [
            {"name": "Mumbai Central Hub", "city": "Mumbai"},
            {"name": "Delhi NCR Facility", "city": "Delhi"},
            {"name": "Bangalore Tech Park", "city": "Bangalore"},
        ]
        
        warehouses = []
        for wh_data in warehouses_data:
            warehouse = Warehouse(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                **wh_data
            )
            session.add(warehouse)
            warehouses.append(warehouse)
        
        await session.flush()
        print(f"Created {len(warehouses)} warehouses")
        
        # Create users
        users_data = [
            {
                "email": "admin@demo.com",
                "password": "admin123",
                "full_name": "Admin User",
                "role": UserRole.ADMIN,
                "warehouse_id": None,
            },
            {
                "email": "manager@demo.com",
                "password": "manager123",
                "full_name": "Warehouse Manager",
                "role": UserRole.MANAGER,
                "warehouse_id": warehouses[0].id,
            },
            {
                "email": "operator@demo.com",
                "password": "operator123",
                "full_name": "Scan Operator",
                "role": UserRole.OPERATOR,
                "warehouse_id": warehouses[0].id,
            },
        ]
        
        for user_data in users_data:
            password = user_data.pop("password")
            user = User(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                hashed_password=get_password_hash(password),
                **user_data
            )
            session.add(user)
            print(f"Created user: {user.email} (Role: {user.role.value})")
        
        await session.commit()
        print("\n✅ Seed data created successfully!")
        print("\n📝 Test Credentials:")
        print("   Admin:    admin@demo.com / admin123")
        print("   Manager:  manager@demo.com / manager123")
        print("   Operator: operator@demo.com / operator123")


async def main():
    """Main entry point."""
    # Create tables if they don't exist (for local development)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await seed_data()


if __name__ == "__main__":
    asyncio.run(main())
