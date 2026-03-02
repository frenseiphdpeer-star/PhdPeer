# app/api/v1/__init__.py
from fastapi import APIRouter, Depends
from app.api.deps import require_roles
from app.models.user import UserRole
from app.api.v1.endpoints import analytics, documents, baselines, timeline, timeline_feedback

api_router = APIRouter()

role_dep = Depends(require_roles(
    UserRole.RESEARCHER,
    UserRole.SUPERVISOR,
    UserRole.INSTITUTION_ADMIN,
    UserRole.ENTERPRISE_CLIENT,
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

api_router.include_router(
    baselines.router,
    prefix="/baselines",
    tags=["baselines"],
    dependencies=[role_dep]
)

api_router.include_router(
    timeline.router,
    prefix="/timeline",
    tags=["timeline"],
    dependencies=[role_dep]
)

api_router.include_router(
    timeline_feedback.router,
    prefix="/timeline",
    tags=["timeline-feedback"],
    dependencies=[role_dep]
)
