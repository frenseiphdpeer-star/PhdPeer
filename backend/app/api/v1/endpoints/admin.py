"""
Institution Admin-only endpoints.
RBAC: Cohort aggregation — Admin only; data is aggregated and anonymized.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.core.security import get_current_user, require_roles, Role
from app.models.user import User
from app.models.analytics_snapshot import AnalyticsSnapshot

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
    # Anonymized counts and simple aggregates
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
