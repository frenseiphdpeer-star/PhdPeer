"""
Data visibility rules for RBAC.

- Researcher: only own data.
- Supervisor: only assigned students (via SupervisorAssignment).
- Institution Admin: all data (aggregated/anonymized where required).
"""

from uuid import UUID
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.supervisor_assignment import SupervisorAssignment
from app.core.security import Role, _role_from_string


def can_access_user_data(
    db: Session,
    current_user: User,
    target_user_id: UUID,
) -> bool:
    """
    Return True if current_user is allowed to see target_user_id's data.
    - Researcher: only self.
    - Supervisor: only assigned students.
    - Admin: anyone.
    """
    if current_user.id == target_user_id:
        return True
    role = getattr(current_user, "role", None) or Role.RESEARCHER
    if isinstance(role, str):
        role = _role_from_string(role)
    if role == Role.INSTITUTION_ADMIN:
        return True
    if role == Role.SUPERVISOR:
        assigned = db.query(SupervisorAssignment).filter(
            SupervisorAssignment.supervisor_id == current_user.id,
            SupervisorAssignment.student_id == target_user_id,
        ).first()
        return assigned is not None
    return False


def get_visible_student_ids(db: Session, current_user: User) -> list[UUID] | None:
    """
    Return list of user IDs that current_user is allowed to see.
    - Researcher: [current_user.id]
    - Supervisor: [assigned student ids]
    - Admin: None (means "all" for aggregation).
    """
    role = getattr(current_user, "role", None) or Role.RESEARCHER
    if isinstance(role, str):
        role = _role_from_string(role)
    if role == Role.RESEARCHER:
        return [current_user.id]
    if role == Role.SUPERVISOR:
        rows = db.query(SupervisorAssignment.student_id).filter(
            SupervisorAssignment.supervisor_id == current_user.id,
        ).all()
        return [r[0] for r in rows]
    if role == Role.INSTITUTION_ADMIN:
        return None  # all
    return [current_user.id]
