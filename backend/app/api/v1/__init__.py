# app/api/v1/__init__.py
from fastapi import APIRouter, Depends
from app.api.deps import require_roles
from app.models.user import UserRole
from app.api.v1.endpoints import analytics, documents

api_router = APIRouter()  # No global dependency here

role_dep = Depends(require_roles(
    UserRole.RESEARCHER,
    UserRole.SUPERVISOR,
    UserRole.INSTITUTIONAL_ADMIN,
))

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[role_dep]
)

api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["documents"],
    dependencies=[role_dep]
)