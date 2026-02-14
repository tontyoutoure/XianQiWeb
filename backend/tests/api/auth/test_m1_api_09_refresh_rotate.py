"""M1-API-09 contract test (RED phase)."""

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
    "path": "/api/auth/refresh",
    "headers": [],
    "query_string": b"",
}


def _build_http_request() -> Request:
    return Request(HTTP_SCOPE)


def _http_error_payload(app_main: object, exc: HTTPException) -> tuple[int, dict[str, object]]:
    response = asyncio.run(app_main.handle_http_exception(_build_http_request(), exc))
    return response.status_code, json.loads(response.body.decode("utf-8"))


def test_m1_api_09_refresh_rotates_refresh_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: /refresh returns new pair and revokes old refresh token immediately."""
    db_path = tmp_path / "m1_api_09.sqlite3"
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "api-09-test-secret")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    register_result = app_main.register(app_main.RegisterRequest(username="Alice", password="123"))
    old_refresh_token = register_result["refresh_token"]

    refresh_result = app_main.refresh(app_main.RefreshRequest(refresh_token=old_refresh_token))
    assert {"access_token", "expires_in", "refresh_token", "refresh_expires_in"} <= set(refresh_result)
    assert refresh_result["refresh_token"] != old_refresh_token

    with pytest.raises(HTTPException) as old_refresh_exc:
        app_main.refresh(app_main.RefreshRequest(refresh_token=old_refresh_token))
    status_code, payload = _http_error_payload(app_main, old_refresh_exc.value)
    assert status_code == 401
    assert payload["code"] in {"AUTH_REFRESH_REVOKED", "AUTH_TOKEN_INVALID"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT token_hash, revoked_at
            FROM refresh_tokens
            ORDER BY id ASC
            """
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 2
    assert rows[0]["token_hash"] == hash_refresh_token(old_refresh_token)
    assert rows[0]["revoked_at"] is not None
    assert rows[1]["token_hash"] == hash_refresh_token(refresh_result["refresh_token"])
    assert rows[1]["revoked_at"] is None
