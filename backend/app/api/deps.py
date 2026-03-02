"""Shared API dependencies for authentication and authorization."""
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
import app.models  # noqa: F401
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.services.auth_service import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve and return the authenticated user from a Bearer JWT (access tokens only)."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _CREDENTIALS_EXCEPTION

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise _CREDENTIALS_EXCEPTION

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError):
        raise _CREDENTIALS_EXCEPTION

    user = UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise _CREDENTIALS_EXCEPTION

    return user


def require_roles(*allowed_roles: UserRole):
    """Dependency factory that enforces one of the provided roles."""

    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role permissions",
            )
        return current_user

    return role_dependency
