"""Application configuration."""
from functools import lru_cache
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App
    APP_NAME: str = "Logistics Scanning API"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    
    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Redis (REQUIRED in prod)
    REDIS_URL: Optional[str] = None

    # Bridge to Main Backend (optional)
    MAIN_BACKEND_URL: Optional[str] = None
    BRIDGE_API_KEY: Optional[str] = None
    
    # JWT (REQUIRED)
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"      # Local only
        case_sensitive = True
        extra = "ignore"      # Ignore unrelated env vars


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
