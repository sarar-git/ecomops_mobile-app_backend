"""Bulk scan ingestion tests."""
import pytest
from datetime import date
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_bulk_scan_success(
    client: AsyncClient,
    auth_headers: dict,
    test_warehouse,
):
    """Test successful bulk scan creation."""
    # Create manifest first
    manifest_response = await client.post(
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
    manifest_id = manifest_response.json()["id"]
    
    # Bulk create scans
    response = await client.post(
        "/api/v1/scan-events/bulk",
        headers=auth_headers,
        json={
            "events": [
                {"manifest_id": manifest_id, "barcode_value": "BARCODE001"},
                {"manifest_id": manifest_id, "barcode_value": "BARCODE002"},
                {"manifest_id": manifest_id, "barcode_value": "BARCODE003"},
            ]
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["total_received"] == 3
    assert data["total_inserted"] == 3
    assert data["total_duplicates"] == 0
    assert data["total_errors"] == 0


@pytest.mark.asyncio
async def test_bulk_scan_idempotent(
    client: AsyncClient,
    auth_headers: dict,
    test_warehouse,
):
    """Test that duplicate scans are handled idempotently."""
    # Create manifest
    manifest_response = await client.post(
        "/api/v1/manifests/start",
        headers=auth_headers,
        json={
            "warehouse_id": test_warehouse.id,
            "manifest_date": str(date.today()),
            "shift": "EVENING",
            "marketplace": "FLIPKART",
            "carrier": "EKART",
            "flow_type": "RETURN",
        }
    )
    manifest_id = manifest_response.json()["id"]
    
    # First bulk create
    await client.post(
        "/api/v1/scan-events/bulk",
        headers=auth_headers,
        json={
            "events": [
                {"manifest_id": manifest_id, "barcode_value": "DUP001"},
                {"manifest_id": manifest_id, "barcode_value": "DUP002"},
            ]
        }
    )
    
    # Second bulk create with duplicates
    response = await client.post(
        "/api/v1/scan-events/bulk",
        headers=auth_headers,
        json={
            "events": [
                {"manifest_id": manifest_id, "barcode_value": "DUP001"},  # duplicate
                {"manifest_id": manifest_id, "barcode_value": "DUP002"},  # duplicate
                {"manifest_id": manifest_id, "barcode_value": "NEW001"},  # new
            ]
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["total_received"] == 3
    assert data["total_inserted"] == 1
    assert data["total_duplicates"] == 2


@pytest.mark.asyncio
async def test_bulk_scan_closed_manifest(
    client: AsyncClient,
    auth_headers: dict,
    test_warehouse,
):
    """Test that scans to closed manifest are rejected."""
    # Create and close manifest
    manifest_response = await client.post(
        "/api/v1/manifests/start",
        headers=auth_headers,
        json={
            "warehouse_id": test_warehouse.id,
            "manifest_date": str(date.today()),
            "shift": "NIGHT",
            "marketplace": "MYNTRA",
            "carrier": "BLUEDART",
            "flow_type": "DISPATCH",
        }
    )
    manifest_id = manifest_response.json()["id"]
    
    # Close the manifest
    await client.post(
        f"/api/v1/manifests/{manifest_id}/close",
        headers=auth_headers,
    )
    
    # Try to add scans to closed manifest
    response = await client.post(
        "/api/v1/scan-events/bulk",
        headers=auth_headers,
        json={
            "events": [
                {"manifest_id": manifest_id, "barcode_value": "CLOSED001"},
            ]
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["total_errors"] == 1
    assert "closed" in data["results"][0]["error"]


@pytest.mark.asyncio
async def test_bulk_scan_with_metadata(
    client: AsyncClient,
    auth_headers: dict,
    test_warehouse,
):
    """Test bulk scan with additional metadata."""
    # Create manifest
    manifest_response = await client.post(
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
    manifest_id = manifest_response.json()["id"]
    
    # Bulk create with metadata
    response = await client.post(
        "/api/v1/scan-events/bulk",
        headers=auth_headers,
        json={
            "events": [
                {
                    "manifest_id": manifest_id,
                    "barcode_value": "META001",
                    "barcode_type": "QR",
                    "extracted_order_id": "ORD123",
                    "extracted_awb": "AWB456",
                    "device_id": "DEVICE001",
                    "confidence_score": 0.95,
                },
            ]
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["total_inserted"] == 1


@pytest.mark.asyncio
async def test_list_scan_events(
    client: AsyncClient,
    auth_headers: dict,
    test_warehouse,
):
    """Test listing scan events for a manifest."""
    # Create manifest and add scans
    manifest_response = await client.post(
        "/api/v1/manifests/start",
        headers=auth_headers,
        json={
            "warehouse_id": test_warehouse.id,
            "manifest_date": str(date.today()),
            "shift": "EVENING",
            "marketplace": "AJIO",
            "carrier": "DELHIVERY",
            "flow_type": "RETURN",
        }
    )
    manifest_id = manifest_response.json()["id"]
    
    # Add scans
    await client.post(
        "/api/v1/scan-events/bulk",
        headers=auth_headers,
        json={
            "events": [
                {"manifest_id": manifest_id, "barcode_value": f"LIST{i}"} 
                for i in range(5)
            ]
        }
    )
    
    # List scans
    response = await client.get(
        f"/api/v1/scan-events?manifest_id={manifest_id}",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["events"]) == 5
