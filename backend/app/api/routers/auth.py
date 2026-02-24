"""Auth REST routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import Header

import app.runtime as runtime
from app.auth.models import LoginRequest
from app.auth.models import LogoutRequest
from app.auth.models import RefreshRequest
from app.auth.models import RegisterRequest
from app.auth.service import login_user
from app.auth.service import logout_user
from app.auth.service import refresh_user
from app.auth.service import register_user

from app.api.deps import me
from app.api.deps import require_current_user

router = APIRouter()


@router.post("/api/auth/register")
def register(payload: RegisterRequest) -> dict[str, object]:
    """Create user + auth session for MVP register flow."""
    return register_user(settings=runtime.settings, payload=payload)


@router.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, object]:
    """Authenticate user and issue a fresh auth session."""
    return login_user(settings=runtime.settings, payload=payload)


@router.post("/api/auth/refresh")
def refresh(payload: RefreshRequest) -> dict[str, object]:
    """Rotate refresh token and issue a new access/refresh pair."""
    return refresh_user(settings=runtime.settings, payload=payload)


@router.post("/api/auth/logout")
def logout(payload: LogoutRequest) -> dict[str, bool]:
    """Revoke the provided refresh token idempotently."""
    return logout_user(settings=runtime.settings, payload=payload)


@router.get("/api/auth/me")
def me_route(authorization: str | None = Header(default=None, alias="Authorization")) -> dict[str, object]:
    """HTTP wrapper for /api/auth/me Bearer auth."""
    return require_current_user(authorization)
