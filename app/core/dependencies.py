"""Application dependencies for dependency injection."""
from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token, TokenPayload
from app.core.logging import get_logger
from app.models.user import User
from app.models.tenant import Tenant
from app.models.warehouse import Warehouse


security = HTTPBearer()
logger = get_logger(__name__)


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
    try:
        result = await db.execute(
            select(User).where(User.id == token.sub)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            # JIT Provisioning
            from app.models.user import UserRole
            
            # CRITICAL: We need a tenant_id. Try to get from token, or first tenant in DB
            tenant_id = token.tenant_id
            if not tenant_id:
                tenant_result = await db.execute(select(Tenant).limit(1))
                first_tenant = tenant_result.scalar_one_or_none()
                if not first_tenant:
                    # Create default tenant if none exists (MVP strategy)
                    first_tenant = Tenant(name="Default Tenant")
                    db.add(first_tenant)
                    await db.commit()
                    
                    # Also create a default warehouse for this new tenant
                    default_wh = Warehouse(
                        tenant_id=first_tenant.id,
                        name="Main Warehouse",
                        city="Indore",
                        address="Default Address"
                    )
                    db.add(default_wh)
                    await db.commit()
                    
                tenant_id = first_tenant.id

            # Safe Role Selection
            target_role = UserRole.MOBILE_USER
            if token.role:
                try:
                    target_role = UserRole(token.role)
                except ValueError:
                    logger.warning(f"Unknown role in token: {token.role}, defaulting to MOBILE_USER")

            user = User(
                id=token.sub,
                tenant_id=tenant_id,
                email=token.email or token.user_metadata.get("email") or "unknown@ecomops.com",
                role=target_role,
                is_active=True,
                hashed_password="SUPABASE_AUTH" 
            )
            db.add(user)
            await db.commit()
            logger.info(f"JIT Provisioned user: {user.id}, tenant: {tenant_id}")

        # DEFENSIVE: Ensure the tenant has at least one warehouse
        # This prevents the "disabled dropdown" in the mobile app.
        wh_check = await db.execute(
            select(Warehouse.id).where(Warehouse.tenant_id == user.tenant_id).limit(1)
        )
        if not wh_check.scalar():
            logger.warning(f"Tenant {user.tenant_id} had no warehouses. Creating default.")
            default_wh = Warehouse(
                tenant_id=user.tenant_id,
                name="Main Warehouse",
                city="Indore",
                address="Auto-provisioned"
            )
            db.add(default_wh)
            await db.commit()
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive",
            )
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in get_current_user check/provisioning: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication secondary check failed: {type(e).__name__}: {str(e)}"
        )


async def validate_tenant(
    user: User = Depends(get_current_user),
    token: TokenPayload = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Validate that the tenant is active."""
    try:
        # User has a tenant_id locally even if JWT is missing it
        tenant_id = token.tenant_id or user.tenant_id
        
        result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if tenant is None or not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant not found or inactive",
            )
        
        return tenant
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in validate_tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate tenant context"
        )


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
        self.tenant_id = tenant.id
        self.user_id = user.id
        self.role = user.role.value if hasattr(user.role, 'value') else str(user.role)
        self.warehouse_id = user.warehouse_id # Prioritize DB over token


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
