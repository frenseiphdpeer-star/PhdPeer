"""API v1 router. RBAC: documents/analytics by role; supervisor/ admin have dedicated routes."""
from fastapi import APIRouter

from app.api.v1.endpoints import analytics, documents, supervisor, admin, events, engagement, intelligence, timeline_feedback

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["documents"]
)
api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"]
)
api_router.include_router(
    supervisor.router,
    prefix="/supervisor",
    tags=["supervisor"]
)
api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"]
)
api_router.include_router(
    events.router,
    prefix="/events",
    tags=["events", "audit"]
)
api_router.include_router(
    engagement.router,
    prefix="/engagement",
    tags=["engagement"]
)
api_router.include_router(
    intelligence.router,
    prefix="/intelligence",
    tags=["intelligence", "interpretability"]
)
api_router.include_router(
    timeline_feedback.router,
    prefix="/timeline-feedback",
    tags=["timeline_feedback"]
)
