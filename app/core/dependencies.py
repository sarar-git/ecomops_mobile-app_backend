"""Application dependencies for dependency injection."""
from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token, TokenPayload
from app.models.user import User
from app.models.tenant import Tenant


security = HTTPBearer()


async def get_current_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenPayload:
    """Validate and decode the JWT token from the Authorization header."""
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if payload.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Access token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload


async def get_current_user(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the current authenticated user with JIT provisioning."""
    result = await db.execute(
        select(User).where(User.id == token.sub)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        # JIT Provisioning: If user exists in Supabase but not locally, create it.
        # This is safe because we've already verified the Supabase JWT.
        from app.models.user import UserRole # Import here to avoid circular dependencies if any
        
        user = User(
            id=token.sub,
            email=token.email or token.user_metadata.get("email"),
            role=UserRole(token.role) if token.role else UserRole.MOBILE_USER,
            is_active=True,
            # Passwords are not stored for Supabase users in the mobile backend
            hashed_password="SUPABASE_AUTH" 
        )
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to provision user: {str(e)}"
            )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    
    return user


async def validate_tenant(
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Validate that the tenant is active."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == token.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    
    if tenant is None or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant not found or inactive",
        )
    
    return tenant


class TenantContext:
    """Context object containing tenant-scoped information."""
    
    def __init__(
        self,
        token: TokenPayload,
        user: User,
        tenant: Tenant,
    ):
        self.token = token
        self.user = user
        self.tenant = tenant
        self.tenant_id = token.tenant_id
        self.user_id = token.sub
        self.role = token.role
        self.warehouse_id = token.warehouse_id


async def get_tenant_context(
    token: TokenPayload = Depends(get_current_token),
    user: User = Depends(get_current_user),
    tenant: Tenant = Depends(validate_tenant),
) -> TenantContext:
    """Get the full tenant context for the current request."""
    return TenantContext(token=token, user=user, tenant=tenant)


# Type aliases for cleaner dependency injection
CurrentToken = Annotated[TokenPayload, Depends(get_current_token)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentTenant = Annotated[Tenant, Depends(validate_tenant)]
TenantCtx = Annotated[TenantContext, Depends(get_tenant_context)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


def require_role(*roles: str):
    """Dependency factory to require specific roles."""
    async def role_checker(ctx: TenantCtx) -> TenantContext:
        if ctx.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{ctx.role}' not authorized. Required: {roles}",
            )
        return ctx
    return role_checker
