"""Authentication service – password hashing, JWT creation, token rotation, OAuth."""
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthResponse, RegisterRequest, UserOut

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

MICROSOFT_AUTH_URL_TEMPLATE = (
    "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
)
MICROSOFT_TOKEN_URL_TEMPLATE = (
    "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
)
MICROSOFT_USERINFO_URL = "https://graph.microsoft.com/v1.0/me"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    # bcrypt has a 72-byte limit; passlib/bcrypt 5.0+ raises if longer
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > 72:
        password = pwd_bytes[:72].decode("utf-8", errors="replace")
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + expires_delta
    to_encode["iat"] = datetime.utcnow()
    to_encode["jti"] = str(uuid.uuid4())
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user: User) -> str:
    return _create_token(
        {"sub": str(user.id), "type": "access", "role": user.role.value},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token_value() -> tuple[str, datetime]:
    """Return (opaque token string, expiry datetime)."""
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return token, expires_at


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def register(self, payload: RegisterRequest) -> AuthResponse:
        existing = self.user_repo.get_by_email(payload.email)
        if existing:
            raise ValueError("Email already registered")

        user = self.user_repo.create_user(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            role=payload.role,
            institution=payload.institution,
            field_of_study=payload.field_of_study,
        )
        return self._issue_tokens(user)

    def authenticate(self, email: str, password: str) -> AuthResponse:
        user = self.user_repo.get_by_email(email)
        if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid email or password")
        if not user.is_active:
            raise ValueError("Account is deactivated")
        return self._issue_tokens(user)

    def refresh(self, refresh_token_value: str) -> AuthResponse:
        token_record = (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token == refresh_token_value)
            .first()
        )
        if not token_record or not token_record.is_usable:
            raise ValueError("Invalid or expired refresh token")

        # Rotate: revoke old, issue new
        token_record.revoked = True

        user = self.user_repo.get_by_id(token_record.user_id)
        if not user or not user.is_active:
            self.db.commit()
            raise ValueError("User not found or inactive")

        new_token_value, expires_at = create_refresh_token_value()
        token_record.replaced_by = new_token_value

        new_refresh = RefreshToken(
            token=new_token_value,
            user_id=user.id,
            expires_at=expires_at,
        )
        self.db.add(new_refresh)
        self.db.commit()

        return AuthResponse(
            access_token=create_access_token(user),
            refresh_token=new_token_value,
            user=UserOut.model_validate(user),
        )

    def revoke_all_tokens(self, user_id) -> None:
        """Revoke every active refresh token for a user (logout-all)."""
        self.db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
        ).update({"revoked": True})
        self.db.commit()

    # ── OAuth helpers ────────────────────────────────────────────────

    def get_oauth_authorization_url(self, provider: str, redirect_uri: str) -> str:
        """Build the authorization URL the frontend should redirect to."""
        if provider == "google":
            if not settings.GOOGLE_CLIENT_ID:
                raise ValueError("Google OAuth is not configured")
            params = {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "access_type": "offline",
                "prompt": "select_account",
            }
            return f"{GOOGLE_AUTH_URL}?{httpx.QueryParams(params)}"

        if provider == "microsoft":
            if not settings.MICROSOFT_CLIENT_ID:
                raise ValueError("Microsoft OAuth is not configured")
            tenant = settings.MICROSOFT_TENANT_ID
            params = {
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile User.Read",
                "prompt": "select_account",
            }
            base = MICROSOFT_AUTH_URL_TEMPLATE.format(tenant=tenant)
            return f"{base}?{httpx.QueryParams(params)}"

        raise ValueError(f"Unsupported OAuth provider: {provider}")

    async def oauth_callback(self, provider: str, code: str, redirect_uri: str) -> AuthResponse:
        """Exchange an authorization code for tokens and log the user in (or register)."""
        if provider == "google":
            user_info = await self._google_exchange(code, redirect_uri)
        elif provider == "microsoft":
            user_info = await self._microsoft_exchange(code, redirect_uri)
        else:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        provider_id: str = user_info["id"]
        email: str = user_info["email"]
        full_name: str | None = user_info.get("name")

        user = self.user_repo.get_by_oauth(provider, provider_id)
        if user:
            return self._issue_tokens(user)

        user = self.user_repo.get_by_email(email)
        if user:
            user.oauth_provider = provider
            user.oauth_provider_id = provider_id
            if not user.full_name and full_name:
                user.full_name = full_name
            self.db.commit()
            self.db.refresh(user)
            return self._issue_tokens(user)

        user = self.user_repo.create_user(
            email=email,
            hashed_password=None,
            full_name=full_name,
            role=UserRole.RESEARCHER,
            oauth_provider=provider,
            oauth_provider_id=provider_id,
        )
        return self._issue_tokens(user)

    async def _google_exchange(self, code: str, redirect_uri: str) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()

            info_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            info_resp.raise_for_status()
            info = info_resp.json()

        return {"id": info["sub"], "email": info["email"], "name": info.get("name")}

    async def _microsoft_exchange(self, code: str, redirect_uri: str) -> dict[str, Any]:
        tenant = settings.MICROSOFT_TENANT_ID
        token_url = MICROSOFT_TOKEN_URL_TEMPLATE.format(tenant=tenant)

        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                token_url,
                data={
                    "code": code,
                    "client_id": settings.MICROSOFT_CLIENT_ID,
                    "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                    "scope": "openid email profile User.Read",
                },
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()

            info_resp = await client.get(
                MICROSOFT_USERINFO_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            info_resp.raise_for_status()
            info = info_resp.json()

        return {
            "id": info["id"],
            "email": info.get("mail") or info.get("userPrincipalName", ""),
            "name": info.get("displayName"),
        }

    # ── Token helpers ─────────────────────────────────────────────

    def _issue_tokens(self, user: User) -> AuthResponse:
        access = create_access_token(user)
        refresh_value, expires_at = create_refresh_token_value()

        refresh_record = RefreshToken(
            token=refresh_value,
            user_id=user.id,
            expires_at=expires_at,
        )
        self.db.add(refresh_record)
        self.db.commit()

        return AuthResponse(
            access_token=access,
            refresh_token=refresh_value,
            user=UserOut.model_validate(user),
        )
