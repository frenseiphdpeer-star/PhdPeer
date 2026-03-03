"""Role-based access control middleware."""
from __future__ import annotations

from typing import Dict, Iterable, Set
from uuid import UUID

from jose import JWTError, jwt
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository


class RoleBasedAccessMiddleware(BaseHTTPMiddleware):
    """Enforce role-based access by URL prefix for protected route groups."""

    def __init__(self, app, role_rules: Dict[str, Iterable[UserRole]] | None = None) -> None:
        super().__init__(app)
        default_rules = {
            "/api/v1/researcher": {UserRole.RESEARCHER, UserRole.SUPERVISOR, UserRole.INSTITUTION_ADMIN, UserRole.ENTERPRISE_CLIENT},
            "/api/v1/supervisor": {UserRole.SUPERVISOR, UserRole.INSTITUTION_ADMIN},
            "/api/v1/institution": {UserRole.INSTITUTION_ADMIN},
            "/api/v1/enterprise": {UserRole.ENTERPRISE_CLIENT},
        }
        self.role_rules: Dict[str, Set[UserRole]] = {
            prefix: set(roles) for prefix, roles in (role_rules or default_rules).items()
        }

    async def dispatch(self, request: Request, call_next) -> Response:
        # Preflight OPTIONS must pass through so CORS middleware can add headers
        if request.method == "OPTIONS":
            return await call_next(request)

        # Temporary debug logging (remove after CORS is verified)
        print("METHOD:", request.method)
        print("PATH:", request.url.path)

        path = request.url.path
        required_roles = self._get_required_roles(path)

        if required_roles is None:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing bearer token"})

        token = auth_header.split(" ", 1)[1].strip()

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            subject = payload.get("sub")
            if not subject:
                raise ValueError("Missing sub claim")
            user_id = UUID(str(subject))
        except (JWTError, ValueError):
            return JSONResponse(status_code=401, content={"detail": "Invalid authentication token"})

        db: Session = SessionLocal()
        try:
            user_repository = UserRepository(db)
            user = user_repository.get_by_id(user_id)
            if not user or not user.is_active:
                return JSONResponse(status_code=401, content={"detail": "Invalid user"})

            if user.role not in required_roles:
                return JSONResponse(status_code=403, content={"detail": "Role not authorized for this route"})

            request.state.current_user_id = str(user.id)
            request.state.current_user_role = user.role.value
        finally:
            db.close()

        return await call_next(request)

    def _get_required_roles(self, path: str) -> Set[UserRole] | None:
        for prefix, roles in self.role_rules.items():
            if path.startswith(prefix):
                return roles
        return None
