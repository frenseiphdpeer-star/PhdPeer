# app/api/v1/__init__.py
from fastapi import APIRouter, Depends
from app.api.deps import require_roles
from app.models.user import UserRole
from app.api.v1.endpoints import analytics, documents, baselines, timeline, timeline_feedback, predictions, writing_coherence, research_novelty, dropout_risk, opportunity_matching, collaboration_network, fusion_engine, research_twin, publisher_readiness

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

api_router.include_router(
    predictions.router,
    prefix="/predictions",
    tags=["predictions"],
    dependencies=[role_dep]
)

api_router.include_router(
    writing_coherence.router,
    prefix="/writing-coherence",
    tags=["writing-coherence"],
    dependencies=[role_dep]
)

api_router.include_router(
    research_novelty.router,
    prefix="/research-novelty",
    tags=["research-novelty"],
    dependencies=[role_dep]
)

api_router.include_router(
    dropout_risk.router,
    prefix="/dropout-risk",
    tags=["dropout-risk"],
    dependencies=[role_dep]
)

api_router.include_router(
    opportunity_matching.router,
    prefix="/opportunity-matching",
    tags=["opportunity-matching"],
    dependencies=[role_dep]
)

api_router.include_router(
    collaboration_network.router,
    prefix="/collaboration-network",
    tags=["collaboration-network"],
    dependencies=[role_dep]
)

api_router.include_router(
    fusion_engine.router,
    prefix="/fusion",
    tags=["fusion-engine"],
    dependencies=[role_dep]
)

api_router.include_router(
    research_twin.router,
    prefix="/research-twin",
    tags=["research-twin"],
    dependencies=[role_dep]
)

api_router.include_router(
    publisher_readiness.router,
    prefix="/publisher-readiness",
    tags=["publisher-readiness"],
    dependencies=[role_dep]
)
