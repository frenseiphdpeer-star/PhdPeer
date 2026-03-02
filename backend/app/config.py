"""Application configuration management."""
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "PhD Timeline Intelligence Platform"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # Database
    DATABASE_URL: str
    DATABASE_ECHO: bool = False
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # OAuth – Google
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # OAuth – Microsoft
    MICROSOFT_CLIENT_ID: Optional[str] = None
    MICROSOFT_CLIENT_SECRET: Optional[str] = None
    MICROSOFT_TENANT_ID: str = "common"

    # CORS
    FRONTEND_URL: str
    
    # API
    API_V1_PREFIX: str = "/api/v1"

    # Documentation exposure
    PUBLIC_DOCS_ENABLED: bool = True
    PUBLIC_OPENAPI_ENABLED: bool = True

    # LLM / Groq
    LLM_PROVIDER: str = "groq"
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_TEMPERATURE: float = 0.15
    LLM_MAX_TOKENS: int = 4096
    LLM_TIMEOUT_SECONDS: int = 60
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
