from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Database URL (Separate DB for Customer Service)
    DATABASE_URL: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "RS256"

    # JWT Settings (Must match Auth Service)
    JWT_ISSUER: Optional[str] = "https://auth.brainchat.cloud"
    JWT_AUDIENCE: str = "mission-auth"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWKS_URL: Optional[str]

    # Redis Configuration
    REDIS_URL: str
    REDIS_DB: int = 1

    # Frontend URLs for CORS
    LOCAL_FRONTEND_URL: Optional[str] = None
    STUDIO_FRONTEND_URL: Optional[str] = None
    FRONTEND_URL: Optional[str] = None

    # Meta Graph API Configuration
    META_GRAPH_API_VERSION: str = "v21.0"
    META_GRAPH_API_BASE_URL: str = "https://graph.facebook.com"

    # Pydantic Config
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
