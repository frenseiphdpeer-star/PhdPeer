"""Main FastAPI application entry point."""
import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlalchemy.exc import OperationalError, InterfaceError, ProgrammingError, SQLAlchemyError

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
    # Allow any localhost/127.0.0.1 port (e.g. 3001, 3002)
    cors_origin_regex = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
else:
    cors_origins = [settings.FRONTEND_URL]
    cors_origin_regex = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup: warn if LLM is not configured (timeline will use fallback only)
    try:
        from app.config import is_llm_configured
        if not is_llm_configured():
            import logging
            logging.getLogger("uvicorn.error").warning(
                "LLM_API_KEY is not set or is placeholder. "
                "Timeline generation will use generic stages. "
                "Set a Groq key in backend/.env (https://console.groq.com) for AI-powered timelines."
            )
    except Exception:
        pass
    # Startup: Initialize resources
    import app.models  # noqa: F401 – ensure all models are registered with Base
    from app.database import init_db
    init_db()
    yield
    # Shutdown: clean up resources


# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=openapi_url,
    docs_url=docs_url,
    redoc_url=redoc_url,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

def _cors_allowed_origin(origin: str | None) -> str | None:
    """Return origin if it is allowed for CORS, else None."""
    if not origin:
        return None
    if origin in cors_origins:
        return origin
    if cors_origin_regex and re.match(cors_origin_regex, origin):
        return origin
    return None


class EnsureCORSHeadersMiddleware(BaseHTTPMiddleware):
    """Development: ensure every response has CORS headers so GET/OPTIONS never fail with CORS."""

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        allowed = _cors_allowed_origin(origin)

        if request.method == "OPTIONS":
            # Preflight: return 200 with CORS headers so browser allows the actual request
            headers = {}
            if allowed:
                headers["Access-Control-Allow-Origin"] = allowed
                headers["Access-Control-Allow-Credentials"] = "true"
                headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
                headers["Access-Control-Allow-Headers"] = "*"
            return Response(status_code=200, headers=headers)

        response = await call_next(request)
        if allowed and "Access-Control-Allow-Origin" not in response.headers:
            response.headers["Access-Control-Allow-Origin"] = allowed
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response


# 1) Custom middleware first (runs after CORS in the stack)
app.add_middleware(RoleBasedAccessMiddleware)
# 2) Starlette CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
# 3) CORS safety net LAST so it runs FIRST: handle OPTIONS and ensure headers on all responses
app.add_middleware(EnsureCORSHeadersMiddleware)


def _db_error_detail() -> str:
    return (
        "Database unavailable or schema not applied. "
        "Ensure PostgreSQL is running (e.g. docker compose up -d postgres), "
        "then run: cd backend && alembic upgrade head"
    )


@app.exception_handler(OperationalError)
@app.exception_handler(InterfaceError)
@app.exception_handler(ProgrammingError)
@app.exception_handler(SQLAlchemyError)
def handle_db_errors(request, exc):
    detail = _db_error_detail()
    if settings.ENVIRONMENT.lower() in {"development", "dev", "local"}:
        detail += f" [{type(exc).__name__}: {str(exc)[:200]}]"
    return JSONResponse(
        status_code=503,
        content={"detail": detail, "error": "database_unavailable"},
    )


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


@app.options("/{full_path:path}")
async def preflight_handler(full_path: str) -> Response:
    """Respond to OPTIONS preflight so CORS middleware can add headers; route deps are not run."""
    return Response(status_code=200)


@app.get("/health")
async def health_check():
    """Health check endpoint. Includes LLM status for timeline AI features."""
    from app.config import is_llm_configured
    llm_configured = is_llm_configured()
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "llm_configured": llm_configured,
        "llm_message": None if llm_configured else (
            "Set LLM_API_KEY in backend/.env for AI-powered timeline generation. "
            "Get a free key at https://console.groq.com"
        ),
    }


# Include API v1 router
# Include auth FIRST, no auth dependency on it
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

# Then the protected routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
