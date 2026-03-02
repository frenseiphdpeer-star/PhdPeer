"""Tenant Middleware for FastAPI request processing and access control.

This middleware extracts user identity from requests, validates permissions,
and logs access attempts for audit trail.
"""
import logging
from functools import wraps
from typing import Any, Callable, Optional
from uuid import UUID

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.database import SessionLocal
from app.services.audit_logger import AuditLogger
from app.services.privacy_engine import PrivacyEngine, TenantIsolationError
from app.models.audit_log import AuditLog


logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware for tenant isolation and access control.

    Responsibilities:
    - Extract user_id and role from request (header or JWT token)
    - Attach them to request state
    - Log access attempts for audit trail
    - Provide hooks for permission validation
    """

    # Headers for user identity
    HEADER_USER_ID = "X-User-ID"
    HEADER_ROLE = "X-User-Role"
    HEADER_FORWARDED_FOR = "X-Forwarded-For"

    # Default role if not specified
    DEFAULT_ROLE = PrivacyEngine.ROLE_STUDENT

    # Paths that don't require authentication
    PUBLIC_PATHS = [
        "/",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/oauth",
    ]

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """
        Process incoming request.

        Extracts user identity, attaches to request state, and logs access.

        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain

        Returns:
            Response from downstream handlers
        """
        # Skip processing for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Extract user identity from request
        user_id = self._extract_user_id(request)
        role = self._extract_role(request)
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent")

        # Attach to request state for use in endpoints
        request.state.user_id = user_id
        request.state.role = role
        request.state.ip_address = ip_address
        request.state.user_agent = user_agent

        # Log access attempt (for authenticated requests)
        if user_id:
            try:
                self._log_request_access(
                    user_id=user_id,
                    role=role,
                    method=request.method,
                    path=request.url.path,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            except Exception as e:
                # Don't fail request if logging fails
                logger.warning(f"Failed to log access: {e}")

        # Continue with request
        try:
            response = await call_next(request)
            return response
        except TenantIsolationError as e:
            logger.warning(f"Tenant isolation error: {e}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Access denied: insufficient permissions"},
            )

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        for public_path in self.PUBLIC_PATHS:
            if path == public_path or path.startswith(f"{public_path}/"):
                return True
        return False

    def _extract_user_id(self, request: Request) -> Optional[UUID]:
        """
        Extract user ID from request.

        Checks in order:
        1. X-User-ID header
        2. JWT token in Authorization header
        3. Request state (if already set by auth middleware)
        """
        # Try header first
        user_id_header = request.headers.get(self.HEADER_USER_ID)
        if user_id_header:
            try:
                return UUID(user_id_header)
            except ValueError:
                logger.warning(f"Invalid user ID in header: {user_id_header}")

        # Try to get from existing state (set by auth middleware)
        if hasattr(request.state, "user_id") and request.state.user_id:
            return request.state.user_id

        # Try to extract from JWT token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            user_id = self._extract_user_id_from_jwt(auth_header[7:])
            if user_id:
                return user_id

        return None

    def _extract_role(self, request: Request) -> str:
        """
        Extract user role from request.

        Checks in order:
        1. X-User-Role header
        2. JWT token claims
        3. Request state
        4. Default role
        """
        # Try header first
        role_header = request.headers.get(self.HEADER_ROLE)
        if role_header and role_header in PrivacyEngine.VALID_ROLES:
            return role_header

        # Try to get from existing state
        if hasattr(request.state, "role") and request.state.role:
            return request.state.role

        # Try to extract from JWT token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            role = self._extract_role_from_jwt(auth_header[7:])
            if role:
                return role

        return self.DEFAULT_ROLE

    def _extract_user_id_from_jwt(self, token: str) -> Optional[UUID]:
        """Extract user ID from JWT token."""
        try:
            import jwt
            from app.config import settings

            # Decode without verification for ID extraction
            # (actual verification should happen in auth middleware)
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
                options={"verify_exp": False}
            )
            user_id = payload.get("sub") or payload.get("user_id")
            if user_id:
                return UUID(user_id)
        except Exception as e:
            logger.debug(f"JWT extraction failed: {e}")
        return None

    def _extract_role_from_jwt(self, token: str) -> Optional[str]:
        """Extract role from JWT token claims."""
        try:
            import jwt
            from app.config import settings

            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
                options={"verify_exp": False}
            )
            role = payload.get("role")
            if role and role in PrivacyEngine.VALID_ROLES:
                return role
        except Exception as e:
            logger.debug(f"JWT role extraction failed: {e}")
        return None

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Get client IP address, handling proxies."""
        # Check X-Forwarded-For header (set by proxies)
        forwarded_for = request.headers.get(self.HEADER_FORWARDED_FOR)
        if forwarded_for:
            # Take first IP (client)
            return forwarded_for.split(",")[0].strip()

        # Fall back to direct client
        if request.client:
            return request.client.host

        return None

    def _log_request_access(
        self,
        user_id: UUID,
        role: str,
        method: str,
        path: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> None:
        """Log request access to audit trail."""
        # Create a new session for logging (middleware can't use dependency injection)
        db = SessionLocal()
        try:
            audit_logger = AuditLogger(db)

            # Determine resource type from path
            resource_type = self._path_to_resource_type(path)

            # Only log significant access (not every request)
            if self._should_log_access(method, path):
                audit_logger.log_access(
                    user_id=user_id,
                    resource_type=resource_type,
                    action=method.lower(),
                    ip_address=ip_address,
                    user_agent=user_agent,
                    reason=f"{method} {path}",
                )
        finally:
            db.close()

    def _path_to_resource_type(self, path: str) -> str:
        """Map URL path to resource type for audit logging."""
        path_lower = path.lower()

        if "/document" in path_lower:
            return AuditLog.RESOURCE_DOCUMENT
        elif "/timeline" in path_lower:
            return AuditLog.RESOURCE_TIMELINE
        elif "/stage" in path_lower:
            return AuditLog.RESOURCE_STAGE
        elif "/milestone" in path_lower:
            return AuditLog.RESOURCE_MILESTONE
        elif "/assessment" in path_lower:
            return AuditLog.RESOURCE_ASSESSMENT
        elif "/feedback" in path_lower:
            return AuditLog.RESOURCE_FEEDBACK
        elif "/progress" in path_lower:
            return AuditLog.RESOURCE_PROGRESS
        elif "/analytics" in path_lower:
            return AuditLog.RESOURCE_ANALYTICS
        elif "/user" in path_lower:
            return AuditLog.RESOURCE_USER
        else:
            return "api"

    def _should_log_access(self, method: str, path: str) -> bool:
        """Determine if this request should be logged."""
        # Log all write operations
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            return True

        # Log sensitive data access
        sensitive_paths = [
            "/export",
            "/assessment",
            "/analytics",
            "/feedback",
            "/user",
        ]
        for sensitive in sensitive_paths:
            if sensitive in path.lower():
                return True

        # Don't log routine GET requests to reduce noise
        return False


# Dependency functions for FastAPI endpoints

def get_current_user_id(request: Request) -> Optional[UUID]:
    """
    Get current user ID from request state.

    Use as FastAPI dependency:
        @app.get("/endpoint")
        def endpoint(user_id: UUID = Depends(get_current_user_id)):
            ...
    """
    return getattr(request.state, "user_id", None)


def get_current_role(request: Request) -> str:
    """
    Get current user role from request state.

    Use as FastAPI dependency:
        @app.get("/endpoint")
        def endpoint(role: str = Depends(get_current_role)):
            ...
    """
    return getattr(request.state, "role", PrivacyEngine.ROLE_STUDENT)


def require_permission(
    resource_user_id_param: str = "user_id",
) -> Callable:
    """
    Decorator to require permission to access another user's data.

    Args:
        resource_user_id_param: Name of the path/query parameter containing
                                 the target user ID

    Usage:
        @app.get("/users/{user_id}/data")
        @require_permission("user_id")
        def get_user_data(user_id: UUID, request: Request, db: Session = Depends(get_db)):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request from kwargs
            request = kwargs.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found",
                )

            # Get current user info
            current_user_id = getattr(request.state, "user_id", None)
            current_role = getattr(request.state, "role", PrivacyEngine.ROLE_STUDENT)
            ip_address = getattr(request.state, "ip_address", None)

            if not current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Get target user ID from path/query params
            resource_user_id = kwargs.get(resource_user_id_param)
            if not resource_user_id:
                # Try to get from path params
                resource_user_id = request.path_params.get(resource_user_id_param)

            if resource_user_id:
                # Convert to UUID if string
                if isinstance(resource_user_id, str):
                    resource_user_id = UUID(resource_user_id)

                # Get db session
                db = kwargs.get("db")
                if not db:
                    db = SessionLocal()
                    should_close = True
                else:
                    should_close = False

                try:
                    privacy_engine = PrivacyEngine(db)
                    privacy_engine.enforce_tenant_isolation(
                        user_id=current_user_id,
                        resource_user_id=resource_user_id,
                        role=current_role,
                        resource_type="api",
                        ip_address=ip_address,
                    )
                except TenantIsolationError:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: insufficient permissions",
                    )
                finally:
                    if should_close:
                        db.close()

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_role(*allowed_roles: str) -> Callable:
    """
    Decorator to require specific role(s) for an endpoint.

    Usage:
        @app.get("/admin/endpoint")
        @require_role("admin", "supervisor")
        def admin_endpoint(request: Request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request from kwargs
            request = kwargs.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found",
                )

            current_role = getattr(request.state, "role", None)

            if not current_role or current_role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: requires role(s) {', '.join(allowed_roles)}",
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator
