"""Sign in, refresh, and the signed-in user's own profile."""

from fastapi import APIRouter, Depends

from auth import get_current_user
from db import transaction
from models.entities import User
from models.schemas import LoginRequest, PasswordChange, ProfileUpdate, RefreshRequest
from services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login")
def login(body: LoginRequest):
    """Username (or email) and password -> access and refresh tokens."""
    with transaction() as db:
        return auth_service.login(db, body.username, body.password)


@router.post("/refresh")
def refresh(body: RefreshRequest):
    """A refresh token -> new tokens, so users stay signed in."""
    with transaction() as db:
        return auth_service.refresh(db, body.refresh_token)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    with transaction() as db:
        return auth_service.me(db, user)


@router.put("/me")
def update_me(body: ProfileUpdate, user: User = Depends(get_current_user)):
    """Everyone may change their own name and email (and nothing else here)."""
    with transaction() as db:
        return auth_service.update_profile(db, user, body)


@router.post("/change-password")
def change_password(body: PasswordChange, user: User = Depends(get_current_user)):
    with transaction() as db:
        return auth_service.change_password(db, user, body)
