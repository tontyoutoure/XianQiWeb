"""Dependency helpers shared by API routers."""

from __future__ import annotations

from fastapi import Header

import app.runtime as runtime
from app.auth.errors import raise_token_invalid
from app.auth.service import me_user


def me(access_token: str) -> dict[str, object]:
    """Return current user profile for a valid access token."""
    return me_user(settings=runtime.settings, access_token=access_token)


def require_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    """Read and validate Bearer access token from Authorization header."""
    if authorization is None:
        raise_token_invalid()

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise_token_invalid()
    return me(token)
