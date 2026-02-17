"""
Role-based access control (RBAC) and permissions.

Roles:
- PhD Researcher: own timeline editing, own analytics.
- Supervisor: view assigned students' risk/analytics only.
- Institution Admin: cohort aggregation, anonymized data, all visibility.

Permissions:
- timeline_edit: Create/edit/commit own timeline (Researcher only).
- student_risk_visibility: See student risk/analytics (Supervisor, Admin).
- cohort_aggregation: See aggregated cohort data (Admin only).
"""

from enum import Enum
from typing import Set
from uuid import UUID
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User


class Role(str, Enum):
    """Platform roles."""

    RESEARCHER = "researcher"           # PhD Researcher
    SUPERVISOR = "supervisor"           # Supervisor
    INSTITUTION_ADMIN = "institution_admin"  # Institution Admin


class Permission(str, Enum):
    """Permission flags for RBAC."""

    TIMELINE_EDIT = "timeline_edit"
    STUDENT_RISK_VISIBILITY = "student_risk_visibility"
    COHORT_AGGREGATION = "cohort_aggregation"


# Role -> set of permissions
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.RESEARCHER: {
        Permission.TIMELINE_EDIT,
    },
    Role.SUPERVISOR: {
        Permission.STUDENT_RISK_VISIBILITY,
    },
    Role.INSTITUTION_ADMIN: {
        Permission.STUDENT_RISK_VISIBILITY,
        Permission.COHORT_AGGREGATION,
    },
}


def get_role_permissions(role: Role) -> Set[Permission]:
    """Return set of permissions for a role."""
    return ROLE_PERMISSIONS.get(role, set())


def _role_from_string(value: str) -> Role:
    """Parse role from string; default to RESEARCHER if invalid."""
    try:
        return Role(value)
    except ValueError:
        return Role.RESEARCHER


def get_current_user(
    x_user_id: str | None = Header(None, alias="X-User-Id"),
    x_user_role: str | None = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve current user from headers (and DB).
    In production replace with JWT validation.
    Headers: X-User-Id (UUID), X-User-Role (researcher | supervisor | institution_admin).
    """
    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="Missing X-User-Id header",
        )
    try:
        user_uuid = UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid X-User-Id format",
        )
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User is inactive",
        )
    # Override role from header if provided (for dev); else use DB role (string)
    if x_user_role:
        user.role = _role_from_string(x_user_role).value
    elif isinstance(getattr(user, "role", None), str):
        pass
    else:
        user.role = Role.RESEARCHER.value
    return user


def require_permission(permission: Permission):
    """
    Dependency factory: require the current user to have the given permission.
    Use: Depends(require_permission(Permission.TIMELINE_EDIT))
    """

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        role = getattr(current_user, "role", None) or Role.RESEARCHER
        if isinstance(role, str):
            role = _role_from_string(role)
        allowed = get_role_permissions(role)
        if permission not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission.value} required",
            )
        return current_user

    return _dependency


def require_roles(*roles: Role):
    """
    Dependency: require current user to have one of the given roles.
    Use: Depends(require_roles(Role.SUPERVISOR, Role.INSTITUTION_ADMIN))
    """

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        user_role = getattr(current_user, "role", None) or Role.RESEARCHER
        if isinstance(user_role, str):
            user_role = _role_from_string(user_role)
        if user_role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role required: one of {[r.value for r in roles]}",
            )
        return current_user

    return _dependency
