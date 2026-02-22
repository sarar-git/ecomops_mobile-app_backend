"""Authentication API endpoints."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    verify_password, create_access_token, create_refresh_token, 
    decode_token
)
from app.core.config import settings
from app.core.dependencies import CurrentUser, DbSession
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.auth import (
    LoginRequest, LoginResponse, TokenResponse, 
    UserResponse, RefreshTokenRequest
)


router = APIRouter()
logger = get_logger(__name__)


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: DbSession,
):
    """Authenticate user and return JWT tokens."""
    # Find user by email (across all tenants for login)
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()
    
    if user is None or not verify_password(request.password, user.hashed_password):
        logger.warning(f"Failed login attempt for email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    
    # Generate tokens
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role.value,
        warehouse_id=user.warehouse_id,
    )
    refresh_token = create_refresh_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role.value,
        warehouse_id=user.warehouse_id,
    )
    
    logger.info(f"User logged in: {user.id}, tenant: {user.tenant_id}")
    
    return LoginResponse(
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: DbSession,
):
    """Refresh access token using a valid refresh token."""
    payload = decode_token(request.refresh_token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    
    if payload.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Refresh token required.",
        )
    
    # Verify user still exists and is active
    result = await db.execute(
        select(User).where(User.id == payload.sub)
    )
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Generate new tokens
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role.value,
        warehouse_id=user.warehouse_id,
    )
    new_refresh_token = create_refresh_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role.value,
        warehouse_id=user.warehouse_id,
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser,
):
    """Get current authenticated user information."""
    return UserResponse.model_validate(current_user)
