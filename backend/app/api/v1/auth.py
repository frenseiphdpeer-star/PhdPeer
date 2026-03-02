"""Authentication endpoints – register, login, refresh, logout, me, OAuth."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    OAuthCallbackRequest,
    RefreshRequest,
    RegisterRequest,
    UserOut,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    svc = AuthService(db)
    try:
        return svc.register(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    svc = AuthService(db)
    try:
        return svc.authenticate(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post("/refresh", response_model=AuthResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    svc = AuthService(db)
    try:
        return svc.refresh(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = AuthService(db)
    svc.revoke_all_tokens(current_user.id)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


# ── OAuth ────────────────────────────────────────────────────────

@router.get("/oauth/{provider}/url")
def oauth_authorize_url(
    provider: str,
    redirect_uri: str = Query(...),
    db: Session = Depends(get_db),
):
    """Return the provider's authorization URL for the frontend to redirect to."""
    svc = AuthService(db)
    try:
        url = svc.get_oauth_authorization_url(provider, redirect_uri)
        return {"authorization_url": url}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/oauth/{provider}/callback", response_model=AuthResponse)
async def oauth_callback(
    provider: str,
    payload: OAuthCallbackRequest,
    db: Session = Depends(get_db),
):
    """Exchange an OAuth authorization code for an access/refresh token pair."""
    svc = AuthService(db)
    try:
        return await svc.oauth_callback(provider, payload.code, payload.redirect_uri)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to authenticate with the OAuth provider",
        )
