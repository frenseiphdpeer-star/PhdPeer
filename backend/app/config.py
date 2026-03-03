"""Application configuration management."""
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env from backend directory so it works regardless of process CWD
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


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
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()


def is_llm_configured() -> bool:
    """Return True if a real LLM API key is set (not empty or placeholder)."""
    key = (settings.LLM_API_KEY or "").strip()
    if not key:
        return False
    if "your_groq_api_key" in key.lower() or key.startswith("gsk_your_"):
        return False
    return True
