"""HTTP helpers for unified auth errors."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import JSONResponse


def api_error(*, code: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a unified API error payload."""
    return {"code": code, "message": message, "detail": detail or {}}


async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
    """Unify HTTP errors to {code,message,detail} payload."""
    if isinstance(exc.detail, dict) and {"code", "message", "detail"} <= set(exc.detail):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
            headers=exc.headers,
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=api_error(
            code="HTTP_ERROR",
            message=str(exc.detail),
            detail={},
        ),
        headers=exc.headers,
    )
