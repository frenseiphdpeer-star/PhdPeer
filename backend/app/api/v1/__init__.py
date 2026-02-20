"""API v1 router."""
from fastapi import APIRouter, Depends

from app.api.deps import require_roles
from app.models.user import UserRole
from app.api.v1.endpoints import analytics

api_router = APIRouter(
    dependencies=[
        Depends(
            require_roles(
                UserRole.RESEARCHER,
                UserRole.SUPERVISOR,
                UserRole.INSTITUTIONAL_ADMIN,
            )
        )
    ]
)

# Include endpoint routers
api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"]
)
