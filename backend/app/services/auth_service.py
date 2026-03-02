"""Authentication service – password hashing, JWT creation, token rotation."""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthResponse, RegisterRequest, UserOut

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
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
        if not user or not verify_password(password, user.hashed_password):
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
