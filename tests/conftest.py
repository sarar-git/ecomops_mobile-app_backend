"""Test configuration and fixtures."""
import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.core.enums import TenantPlan, UserRole
from app.models.tenant import Tenant
from app.models.warehouse import Warehouse
from app.models.user import User
import uuid


# Test database URL (use SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create database session for tests."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database override."""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    """Create test tenant."""
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name="Test Tenant",
        plan=TenantPlan.PRO,
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def test_warehouse(db_session: AsyncSession, test_tenant: Tenant) -> Warehouse:
    """Create test warehouse."""
    warehouse = Warehouse(
        id=str(uuid.uuid4()),
        tenant_id=test_tenant.id,
        name="Test Warehouse",
        city="Mumbai",
        address="Test Address",
    )
    db_session.add(warehouse)
    await db_session.commit()
    await db_session.refresh(warehouse)
    return warehouse


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_tenant: Tenant, test_warehouse: Warehouse) -> User:
    """Create test user."""
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=test_tenant.id,
        warehouse_id=test_warehouse.id,
        email="test@example.com",
        hashed_password=get_password_hash("testpassword"),
        full_name="Test User",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict:
    """Create authorization headers with valid token."""
    token = create_access_token(
        user_id=test_user.id,
        tenant_id=test_user.tenant_id,
        role=test_user.role.value,
        warehouse_id=test_user.warehouse_id,
    )
    return {"Authorization": f"Bearer {token}"}
