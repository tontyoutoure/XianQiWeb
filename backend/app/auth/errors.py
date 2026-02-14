"""Auth-specific HTTP error helpers."""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException

from app.auth.http import api_error
from app.core.username import UsernameValidationError


def raise_validation_error(exc: UsernameValidationError) -> NoReturn:
    """Raise a unified username validation error."""
    raise HTTPException(
        status_code=400,
        detail=api_error(code="VALIDATION_ERROR", message=str(exc), detail={}),
    ) from exc


def raise_invalid_credentials() -> NoReturn:
    """Raise unified invalid-credentials response."""
    raise HTTPException(
        status_code=401,
        detail=api_error(
            code="AUTH_INVALID_CREDENTIALS",
            message="invalid username or password",
            detail={},
        ),
    )


def raise_username_conflict(exc: Exception) -> NoReturn:
    """Raise unified username-conflict response."""
    raise HTTPException(
        status_code=409,
        detail=api_error(
            code="AUTH_USERNAME_CONFLICT",
            message="username already exists",
            detail={},
        ),
    ) from exc


def raise_token_invalid() -> NoReturn:
    """Raise unified invalid-token response."""
    raise HTTPException(
        status_code=401,
        detail=api_error(
            code="AUTH_TOKEN_INVALID",
            message="invalid access token",
            detail={},
        ),
    )


def raise_token_expired() -> NoReturn:
    """Raise unified expired-token response."""
    raise HTTPException(
        status_code=401,
        detail=api_error(
            code="AUTH_TOKEN_EXPIRED",
            message="access token expired",
            detail={},
        ),
    )


def raise_refresh_rejected() -> NoReturn:
    """Raise unified refresh-token rejection response."""
    raise HTTPException(
        status_code=401,
        detail=api_error(
            code="AUTH_REFRESH_REVOKED",
            message="refresh token is invalid, revoked, or expired",
            detail={},
        ),
    )
