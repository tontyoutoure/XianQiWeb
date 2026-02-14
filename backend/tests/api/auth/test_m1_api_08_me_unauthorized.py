"""M1-API-08 contract test (RED phase)."""

from __future__ import annotations

import asyncio
import importlib
import json
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.tokens import create_access_token


HTTP_SCOPE = {
    "type": "http",
    "method": "GET",
    "path": "/api/auth/me",
    "headers": [],
    "query_string": b"",
}


def _build_http_request() -> Request:
    return Request(HTTP_SCOPE)


def _http_error_payload(app_main: object, exc: HTTPException) -> tuple[int, dict[str, object]]:
    response = asyncio.run(app_main.handle_http_exception(_build_http_request(), exc))
    return response.status_code, json.loads(response.body.decode("utf-8"))


def test_m1_api_08_me_rejects_missing_invalid_and_expired_access_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: GET /api/auth/me returns 401 when access token is missing/invalid/expired."""
    db_path = tmp_path / "m1_api_08.sqlite3"
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "api-08-test-secret-key-32-bytes-minimum")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    register_result = app_main.register(app_main.RegisterRequest(username="Alice", password="123"))

    with pytest.raises(HTTPException) as missing_token_exc:
        app_main.me_route(None)
    status_code, payload = _http_error_payload(app_main, missing_token_exc.value)
    assert status_code == 401
    assert payload == {
        "code": "AUTH_TOKEN_INVALID",
        "message": "invalid access token",
        "detail": {},
    }

    with pytest.raises(HTTPException) as forged_token_exc:
        app_main.me("not-a-jwt")
    status_code, payload = _http_error_payload(app_main, forged_token_exc.value)
    assert status_code == 401
    assert payload == {
        "code": "AUTH_TOKEN_INVALID",
        "message": "invalid access token",
        "detail": {},
    }

    now = datetime(2026, 2, 14, tzinfo=timezone.utc)
    expired_access_token = create_access_token(
        user_id=register_result["user"]["id"],
        now=now - timedelta(hours=2),
        expires_in_seconds=3600,
    )
    with pytest.raises(HTTPException) as expired_token_exc:
        app_main.me(expired_access_token)
    status_code, payload = _http_error_payload(app_main, expired_token_exc.value)
    assert status_code == 401
    assert payload == {
        "code": "AUTH_TOKEN_EXPIRED",
        "message": "access token expired",
        "detail": {},
    }
