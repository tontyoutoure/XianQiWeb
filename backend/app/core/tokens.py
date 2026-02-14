"""JWT access token helpers for M1 auth contracts."""

from __future__ import annotations

import os
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

import jwt

ALGORITHM = "HS256"


class AccessTokenError(ValueError):
    """Base access token error."""


class AccessTokenInvalidError(AccessTokenError):
    """Raised when an access token cannot be decoded or is malformed."""


class AccessTokenExpiredError(AccessTokenError):
    """Raised when an access token is expired."""


def _jwt_secret() -> str:
    # Keep tests runnable without external config; real env overrides this value.
    return os.getenv("XQWEB_JWT_SECRET", "xqweb-dev-secret-please-change-in-production")


def create_access_token(*, user_id: int, now: datetime, expires_in_seconds: int) -> str:
    """Create a JWT access token containing at least sub and exp."""
    exp = int((now + timedelta(seconds=expires_in_seconds)).timestamp())
    payload = {"sub": str(user_id), "exp": exp}
    return jwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str, *, now: datetime) -> dict[str, Any]:
    """Decode and validate an access token."""
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
    except jwt.InvalidTokenError as exc:
        raise AccessTokenInvalidError("invalid access token") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise AccessTokenInvalidError("missing or invalid exp")

    now_ts = int(now.astimezone(timezone.utc).timestamp())
    if now_ts >= exp:
        raise AccessTokenExpiredError("access token expired")

    return payload
