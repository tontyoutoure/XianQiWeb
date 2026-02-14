"""Auth business logic for M1 register/login."""

from __future__ import annotations

import sqlite3

from app.auth.errors import raise_invalid_credentials
from app.auth.errors import raise_refresh_rejected
from app.auth.errors import raise_token_expired
from app.auth.errors import raise_token_invalid
from app.auth.errors import raise_username_conflict
from app.auth.errors import raise_validation_error
from app.auth.models import LogoutRequest
from app.auth.models import LoginRequest
from app.auth.models import RefreshRequest
from app.auth.models import RegisterRequest
from app.auth.repository import consume_refresh_token
from app.auth.repository import create_user
from app.auth.repository import get_user_auth_row
from app.auth.repository import get_user_profile_by_id
from app.auth.repository import revoke_refresh_token_by_hash
from app.auth.schema import init_auth_schema
from app.auth.session import hash_refresh_token
from app.auth.session import issue_auth_session
from app.auth.session import to_utc_iso
from app.auth.session import utc_now
from app.core.config import Settings
from app.core.password import hash_password
from app.core.password import verify_password
from app.core.tokens import AccessTokenExpiredError
from app.core.tokens import AccessTokenInvalidError
from app.core.tokens import decode_access_token
from app.core.username import UsernameValidationError
from app.core.username import normalize_and_validate_username


def _normalize_username(raw_username: str) -> str:
    try:
        return normalize_and_validate_username(raw_username)
    except UsernameValidationError as exc:
        raise_validation_error(exc)


def startup_auth_schema(settings: Settings) -> None:
    """Ensure M1 auth tables exist before handling traffic."""
    init_auth_schema(settings)


def register_user(*, settings: Settings, payload: RegisterRequest) -> dict[str, object]:
    """Create user + auth session for MVP register flow."""
    normalized_username = _normalize_username(payload.username)
    created_at = to_utc_iso(utc_now())
    password_hash = hash_password(payload.password)

    try:
        user_id = create_user(
            settings=settings,
            username=normalized_username,
            password_hash=password_hash,
            created_at=created_at,
        )
    except sqlite3.IntegrityError as exc:
        raise_username_conflict(exc)

    return issue_auth_session(
        settings=settings,
        user_id=user_id,
        username=normalized_username,
        created_at=created_at,
        revoke_existing_refresh_tokens=True,
    )


def login_user(*, settings: Settings, payload: LoginRequest) -> dict[str, object]:
    """Authenticate user and issue a fresh auth session."""
    normalized_username = _normalize_username(payload.username)
    row = get_user_auth_row(settings=settings, username=normalized_username)

    if row is None:
        raise_invalid_credentials()

    user_id, username, password_hash, created_at = row
    if not verify_password(payload.password, password_hash):
        raise_invalid_credentials()

    return issue_auth_session(
        settings=settings,
        user_id=user_id,
        username=username,
        created_at=created_at,
        revoke_existing_refresh_tokens=True,
    )


def me_user(*, settings: Settings, access_token: str) -> dict[str, object]:
    """Return current user profile for a valid access token."""
    now = utc_now()
    try:
        payload = decode_access_token(access_token, now=now)
    except AccessTokenExpiredError:
        raise_token_expired()
    except AccessTokenInvalidError:
        raise_token_invalid()

    sub = payload.get("sub")
    try:
        user_id = int(str(sub))
    except (TypeError, ValueError):
        raise_token_invalid()

    row = get_user_profile_by_id(settings=settings, user_id=user_id)
    if row is None:
        raise_token_invalid()

    uid, username, created_at = row
    return {"id": uid, "username": username, "created_at": created_at}


def refresh_user(*, settings: Settings, payload: RefreshRequest) -> dict[str, object]:
    """Rotate refresh token and return a fresh token pair."""
    now = utc_now()
    now_iso = to_utc_iso(now)
    user_id = consume_refresh_token(
        settings=settings,
        token_hash=hash_refresh_token(payload.refresh_token),
        now_iso=now_iso,
        revoked_at=now_iso,
    )
    if user_id is None:
        raise_refresh_rejected()

    user_row = get_user_profile_by_id(settings=settings, user_id=user_id)
    if user_row is None:
        raise_refresh_rejected()

    _, username, created_at = user_row
    return issue_auth_session(
        settings=settings,
        user_id=user_id,
        username=username,
        created_at=created_at,
        include_user=False,
    )


def logout_user(*, settings: Settings, payload: LogoutRequest) -> dict[str, bool]:
    """Revoke one refresh token idempotently."""
    revoke_refresh_token_by_hash(
        settings=settings,
        token_hash=hash_refresh_token(payload.refresh_token),
        revoked_at=to_utc_iso(utc_now()),
    )
    return {"ok": True}
