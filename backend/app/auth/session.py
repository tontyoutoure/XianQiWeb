"""Session/token issuance for auth endpoints."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from app.auth.repository import create_refresh_token
from app.auth.repository import revoke_refresh_tokens_for_user
from app.core.config import Settings
from app.core.tokens import create_access_token


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def hash_refresh_token(plain_token: str) -> str:
    return hashlib.sha256(plain_token.encode("utf-8")).hexdigest()


def issue_auth_session(
    *,
    settings: Settings,
    user_id: int,
    username: str,
    created_at: str,
    include_user: bool = True,
    revoke_existing_refresh_tokens: bool = False,
) -> dict[str, object]:
    """Create access/refresh tokens and persist refresh hash."""
    now = utc_now()
    access_token = create_access_token(
        user_id=user_id,
        now=now,
        expires_in_seconds=settings.xqweb_access_token_expire_seconds,
    )
    refresh_token_plain = secrets.token_urlsafe(32)
    refresh_created_at = to_utc_iso(now)
    refresh_expires_at = to_utc_iso(
        now + timedelta(seconds=settings.xqweb_refresh_token_expire_seconds)
    )

    if revoke_existing_refresh_tokens:
        revoke_refresh_tokens_for_user(
            settings=settings,
            user_id=user_id,
            revoked_at=refresh_created_at,
        )

    create_refresh_token(
        settings=settings,
        user_id=user_id,
        token_hash=hash_refresh_token(refresh_token_plain),
        expires_at=refresh_expires_at,
        created_at=refresh_created_at,
    )

    response: dict[str, object] = {
        "access_token": access_token,
        "expires_in": settings.xqweb_access_token_expire_seconds,
        "refresh_token": refresh_token_plain,
        "refresh_expires_in": settings.xqweb_refresh_token_expire_seconds,
    }
    if include_user:
        response["user"] = {"id": user_id, "username": username, "created_at": created_at}
    return response
