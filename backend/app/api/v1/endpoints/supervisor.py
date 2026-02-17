"""
Supervisor-only endpoints.
RBAC: Student risk visibility — Supervisor sees only assigned students.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_current_user, require_roles, Role
from app.core.data_visibility import get_visible_student_ids
from app.models.user import User
from app.models.supervisor_assignment import SupervisorAssignment
from app.models.analytics_snapshot import AnalyticsSnapshot

router = APIRouter()


@router.get("/students")
async def list_assigned_students(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPERVISOR)),
):
    """
    List assigned students with minimal risk/visibility info.
    Supervisor sees only their assigned students (data visibility).
    Returns anonymized risk indicator when used for dashboards.
    """
    visible_ids = get_visible_student_ids(db, current_user)
    if not visible_ids:
        return {"students": [], "count": 0}
    # Resolve student users (id, email, full_name) and latest snapshot if any
    students = []
    for student_id in visible_ids:
        user = db.query(User).filter(User.id == student_id).first()
        if not user:
            continue
        latest = (
            db.query(AnalyticsSnapshot)
            .filter(AnalyticsSnapshot.user_id == student_id)
            .order_by(AnalyticsSnapshot.created_at.desc())
            .first()
        )
        risk_level = "unknown"
        if latest and isinstance(latest.summary_json, dict):
            risk_level = latest.summary_json.get("risk_level", "unknown")
        students.append({
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "risk_level": risk_level,
        })
    return {"students": students, "count": len(students)}
