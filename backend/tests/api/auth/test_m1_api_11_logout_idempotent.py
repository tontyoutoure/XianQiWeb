"""M1-API-11 contract test (RED phase)."""

from __future__ import annotations

import asyncio
import importlib
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.auth.session import hash_refresh_token


HTTP_SCOPE = {
    "type": "http",
    "method": "POST",
    "path": "/api/auth/logout",
    "headers": [],
    "query_string": b"",
}


def _build_http_request() -> Request:
    return Request(HTTP_SCOPE)


def _http_error_payload(app_main: object, exc: HTTPException) -> tuple[int, dict[str, object]]:
    response = asyncio.run(app_main.handle_http_exception(_build_http_request(), exc))
    return response.status_code, json.loads(response.body.decode("utf-8"))


def test_m1_api_11_logout_revokes_specified_refresh_token_idempotently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: /logout is idempotent and refresh token becomes unusable."""
    db_path = tmp_path / "m1_api_11.sqlite3"
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "api-11-test-secret-key-32-bytes-minimum")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    register_result = app_main.register(app_main.RegisterRequest(username="Alice", password="123"))
    refresh_token = register_result["refresh_token"]

    first_logout = app_main.logout(app_main.LogoutRequest(refresh_token=refresh_token))
    second_logout = app_main.logout(app_main.LogoutRequest(refresh_token=refresh_token))
    assert first_logout == {"ok": True}
    assert second_logout == {"ok": True}

    with pytest.raises(HTTPException) as refresh_exc:
        app_main.refresh(app_main.RefreshRequest(refresh_token=refresh_token))
    status_code, payload = _http_error_payload(app_main, refresh_exc.value)
    assert status_code == 401
    assert set(payload) == {"code", "message", "detail"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT revoked_at FROM refresh_tokens WHERE token_hash = ?",
            (hash_refresh_token(refresh_token),),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["revoked_at"] is not None
