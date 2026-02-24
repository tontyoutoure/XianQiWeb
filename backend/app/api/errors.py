"""HTTP error mapping helpers for API routes."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.auth.http import api_error


def raise_api_error(
    *,
    status_code: int,
    code: str,
    message: str,
    detail: dict[str, Any],
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=api_error(code=code, message=message, detail=detail),
    )
