"""Authentication API tests."""
import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.user import User


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user: User):
    """Test successful login."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert "tokens" in data
    assert data["user"]["email"] == "test@example.com"
    assert "access_token" in data["tokens"]
    assert "refresh_token" in data["tokens"]


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, test_user: User):
    """Test login with invalid password."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"}
    )
    
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_user_not_found(client: AsyncClient):
    """Test login with non-existent user."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "password"}
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, auth_headers: dict):
    """Test getting current user info when authenticated."""
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    """Test getting current user info without authentication."""
    response = await client.get("/api/v1/auth/me")
    
    assert response.status_code == 403  # No auth header


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, test_user: User):
    """Test token refresh."""
    # First login to get tokens
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpassword"}
    )
    refresh_token = login_response.json()["tokens"]["refresh_token"]
    
    # Refresh the token
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
