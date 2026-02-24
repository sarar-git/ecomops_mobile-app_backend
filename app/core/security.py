"""Security utilities for JWT and password handling."""
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel
import uuid

from app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenPayload(BaseModel):
    """JWT token payload compliant with Supabase JWT."""
    sub: str  # user_id
    email: Optional[str] = None
    role: Optional[str] = None # Custom claim in app_metadata
    tenant_id: Optional[str] = None # Custom claim in app_metadata
    warehouse_id: Optional[str] = None # Custom claim in app_metadata
    type: Optional[str] = "access" 
    exp: datetime
    iat: datetime
    aud: Optional[str] = None
    iss: Optional[str] = None
    app_metadata: dict = {}
    user_metadata: dict = {}

    class Config:
        extra = "allow"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plain password."""
    return pwd_context.hash(password)


def create_access_token(
    user_id: str,
    tenant_id: str,
    role: str,
    warehouse_id: Optional[str] = None,
) -> str:
    """Create a new access token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "warehouse_id": warehouse_id,
        "type": "access",
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    user_id: str,
    tenant_id: str,
    role: str,
    warehouse_id: Optional[str] = None,
) -> str:
    """Create a new refresh token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "warehouse_id": warehouse_id,
        "type": "refresh",
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[TokenPayload]:
    """Decode and validate a Supabase JWT token."""
    try:
        # Note: We use the Supabase JWT Secret here
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False} # Same as web backend configuration
        )
        
        # Extract custom claims from app_metadata (common in Supabase Admin API setups)
        # or from root if custom encoded.
        app_meta = payload.get("app_metadata", {})
        user_meta = payload.get("user_metadata", {})
        
        payload.setdefault("role", app_meta.get("role") or user_meta.get("role"))
        payload.setdefault("tenant_id", app_meta.get("tenant_id") or user_meta.get("tenant_id"))
        payload.setdefault("warehouse_id", app_meta.get("warehouse_id") or user_meta.get("warehouse_id"))
        
        return TokenPayload(**payload)
    except Exception as e:
        print(f"Token decode error: {e}")
        return None
