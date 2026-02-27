"""Manifest API tests."""
import pytest
from datetime import date
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manifest import Manifest
from app.core.enums import ManifestStatus, Marketplace, Carrier, FlowType, Shift


@pytest.mark.asyncio
async def test_start_manifest_success(
    client: AsyncClient,
    auth_headers: dict,
    test_warehouse,
):
    """Test starting a new manifest."""
    response = await client.post(
        "/api/v1/manifests/start",
        headers=auth_headers,
        json={
            "warehouse_id": test_warehouse.id,
            "manifest_date": str(date.today()),
            "shift": "MORNING",
            "marketplace": "AMAZON",
            "carrier": "DELHIVERY",
            "flow_type": "DISPATCH",
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "OPEN"
    assert data["marketplace"] == "AMAZON"
    assert data["carrier"] == "DELHIVERY"
    assert data["flow_type"] == "DISPATCH"


@pytest.mark.asyncio
async def test_start_manifest_resume_existing(
    client: AsyncClient,
    auth_headers: dict,
    test_warehouse,
):
    """Test that duplicate OPEN manifests resume the existing one."""
    manifest_data = {
        "warehouse_id": test_warehouse.id,
        "manifest_date": str(date.today()),
        "shift": "EVENING",
        "marketplace": "FLIPKART",
        "carrier": "EKART",
        "flow_type": "DISPATCH",
    }
    
    # First manifest should succeed
    response1 = await client.post(
        "/api/v1/manifests/start",
        headers=auth_headers,
        json=manifest_data
    )
    assert response1.status_code == 201
    manifest_id1 = response1.json()["id"]
    
    # Second manifest with same params should resume (return 201 and same ID)
    response2 = await client.post(
        "/api/v1/manifests/start",
        headers=auth_headers,
        json=manifest_data
    )
    assert response2.status_code == 201
    manifest_id2 = response2.json()["id"]
    assert manifest_id1 == manifest_id2


@pytest.mark.asyncio
async def test_close_manifest(
    client: AsyncClient,
    auth_headers: dict,
    test_warehouse,
):
    """Test closing a manifest."""
    # Create manifest
    create_response = await client.post(
        "/api/v1/manifests/start",
        headers=auth_headers,
        json={
            "warehouse_id": test_warehouse.id,
            "manifest_date": str(date.today()),
            "shift": "NIGHT",
            "marketplace": "MYNTRA",
            "carrier": "BLUEDART",
            "flow_type": "RETURN",
        }
    )
    manifest_id = create_response.json()["id"]
    
    # Close manifest
    close_response = await client.post(
        f"/api/v1/manifests/{manifest_id}/close",
        headers=auth_headers,
    )
    
    assert close_response.status_code == 200
    data = close_response.json()
    assert data["status"] == "CLOSED"
    assert data["closed_at_utc"] is not None


@pytest.mark.asyncio
async def test_close_already_closed_manifest(
    client: AsyncClient,
    auth_headers: dict,
    test_warehouse,
):
    """Test that closing an already closed manifest fails."""
    # Create and close manifest
    create_response = await client.post(
        "/api/v1/manifests/start",
        headers=auth_headers,
        json={
            "warehouse_id": test_warehouse.id,
            "manifest_date": str(date.today()),
            "shift": "MORNING",
            "marketplace": "JIOMART",
            "carrier": "SHADOWFAX",
            "flow_type": "DISPATCH",
        }
    )
    manifest_id = create_response.json()["id"]
    
    # First close
    await client.post(f"/api/v1/manifests/{manifest_id}/close", headers=auth_headers)
    
    # Second close should fail
    response = await client.post(
        f"/api/v1/manifests/{manifest_id}/close",
        headers=auth_headers,
    )
    
    assert response.status_code == 400
    assert "already closed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_manifests(
    client: AsyncClient,
    auth_headers: dict,
    test_warehouse,
):
    """Test listing manifests."""
    # Create some manifests
    for marketplace in ["AMAZON", "FLIPKART"]:
        await client.post(
            "/api/v1/manifests/start",
            headers=auth_headers,
            json={
                "warehouse_id": test_warehouse.id,
                "manifest_date": str(date.today()),
                "shift": "MORNING",
                "marketplace": marketplace,
                "carrier": "DELHIVERY",
                "flow_type": "DISPATCH",
            }
        )
    
    # List all manifests
    response = await client.get(
        "/api/v1/manifests",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert len(data["manifests"]) >= 2


@pytest.mark.asyncio
async def test_get_manifest_by_id(
    client: AsyncClient,
    auth_headers: dict,
    test_warehouse,
):
    """Test getting a specific manifest."""
    # Create manifest
    create_response = await client.post(
        "/api/v1/manifests/start",
        headers=auth_headers,
        json={
            "warehouse_id": test_warehouse.id,
            "manifest_date": str(date.today()),
            "shift": "EVENING",
            "marketplace": "MEESHO",
            "carrier": "AMAZON_SHIPPING",
            "flow_type": "RETURN",
        }
    )
    manifest_id = create_response.json()["id"]
    
    # Get manifest
    response = await client.get(
        f"/api/v1/manifests/{manifest_id}",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == manifest_id
    assert data["marketplace"] == "MEESHO"
