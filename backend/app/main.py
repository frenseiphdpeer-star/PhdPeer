"""Main FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.deps import get_current_user
from app.api.v1 import api_router
from app.middleware.role_access import RoleBasedAccessMiddleware
from app.models.user import User
from app.api.v1.auth import router as auth_router

openapi_url = "/openapi.json" if getattr(settings, "PUBLIC_OPENAPI_ENABLED", True) else None
docs_url = "/docs" if getattr(settings, "PUBLIC_DOCS_ENABLED", True) and getattr(settings, "PUBLIC_OPENAPI_ENABLED", True) else None
redoc_url = "/redoc" if getattr(settings, "PUBLIC_DOCS_ENABLED", True) and getattr(settings, "PUBLIC_OPENAPI_ENABLED", True) else None
if settings.ENVIRONMENT.lower() in {"development", "dev", "local"}:
    cors_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
else:
    cors_origins = [settings.FRONTEND_URL]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup: Initialize resources
    yield
    # Shutdown: Clean up resources


# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=openapi_url,
    docs_url=docs_url,
    redoc_url=redoc_url,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(RoleBasedAccessMiddleware)


@app.get("/")
async def root(current_user: User = Depends(get_current_user)):
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "user_id": str(current_user.id),
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
    }


# Include API v1 router
# Include auth FIRST, no auth dependency on it
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

# Then the protected routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
