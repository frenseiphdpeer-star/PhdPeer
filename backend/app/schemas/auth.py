"""Authentication and authorization schemas."""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    role: UserRole = UserRole.RESEARCHER
    institution: Optional[str] = None
    field_of_study: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str]
    role: UserRole
    institution: Optional[str]
    field_of_study: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class OAuthCallbackRequest(BaseModel):
    code: str
    redirect_uri: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str
    type: str  # "access" | "refresh"
    role: str
    exp: int


AuthResponse.model_rebuild()
