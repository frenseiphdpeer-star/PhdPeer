"""
Institution Admin-only endpoints.
RBAC: Cohort aggregation — Admin only; data is aggregated and anonymized.
No document content or raw questionnaire answers; aggregation threshold applied.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.core.security import get_current_user, require_roles, Role
from app.models.user import User
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.services.institutional_analytics_service import InstitutionalAnalyticsService

router = APIRouter()


@router.get("/cohort")
async def get_cohort_aggregates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.INSTITUTION_ADMIN)),
):
    """
    Aggregated, anonymized cohort metrics. Admin only.
    No PII; counts and averages only.
    """
    snapshot_count = db.query(func.count(AnalyticsSnapshot.id)).scalar() or 0
    user_count = db.query(func.count(User.id)).filter(User.role == "researcher").scalar() or 0
    return {
        "anonymized": True,
        "total_researchers": user_count,
        "total_analytics_snapshots": snapshot_count,
        "metrics": {
            "researchers_with_analytics": snapshot_count,
            "description": "Aggregated cohort data; no individual identifiers.",
        },
    }


# ---------------------------------------------------------------------------
# Institutional analytics: aggregation only; no document/questionnaire content
# ---------------------------------------------------------------------------

@router.get("/analytics/continuity")
async def get_cohort_continuity_distribution(
    lookback_days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.INSTITUTION_ADMIN)),
):
    """
    Cohort continuity distribution (activity regularity). Aggregation only;
    cells below threshold are suppressed. No document or questionnaire content.
    """
    svc = InstitutionalAnalyticsService(db)
    return svc.cohort_continuity_distribution(lookback_days=lookback_days)


@router.get("/analytics/risk")
async def get_risk_segmentation_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.INSTITUTION_ADMIN)),
):
    """
    Risk segmentation summary (low/medium/high). Aggregation only;
    threshold applied. No document or questionnaire content.
    """
    svc = InstitutionalAnalyticsService(db)
    return svc.risk_segmentation_summary()


@router.get("/analytics/supervisor-engagement")
async def get_supervisor_engagement_averages(
    lookback_days: int = Query(45, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.INSTITUTION_ADMIN)),
):
    """
    Supervisor engagement averages (events per researcher, % with at least one).
    Event counts only; no content. Admin only.
    """
    svc = InstitutionalAnalyticsService(db)
    return svc.supervisor_engagement_averages(lookback_days=lookback_days)


@router.get("/analytics/stage-distribution")
async def get_stage_distribution_counts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.INSTITUTION_ADMIN)),
):
    """
    Stage distribution counts (by stage title). Aggregation only;
    threshold applied. No document or questionnaire content.
    """
    svc = InstitutionalAnalyticsService(db)
    return svc.stage_distribution_counts()


@router.get("/analytics/timeline-delay")
async def get_timeline_delay_frequency(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.INSTITUTION_ADMIN)),
):
    """
    Timeline delay frequency (distribution of timelines by overdue-milestone count).
    Aggregation only; threshold applied. No document content.
    """
    svc = InstitutionalAnalyticsService(db)
    return svc.timeline_delay_frequency()
