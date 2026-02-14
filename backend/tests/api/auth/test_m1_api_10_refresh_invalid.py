"""M1-API-10 contract test (RED phase)."""

from __future__ import annotations

import asyncio
import importlib
import json
import secrets
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


def test_m1_api_10_refresh_rejects_revoked_expired_or_random_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: revoked/expired/random refresh token must all return 401."""
    db_path = tmp_path / "m1_api_10.sqlite3"
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "api-10-test-secret")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    register_result = app_main.register(app_main.RegisterRequest(username="Alice", password="123"))
    refresh_token = register_result["refresh_token"]
    refresh_hash = hash_refresh_token(refresh_token)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE refresh_tokens SET revoked_at = ? WHERE token_hash = ?",
            ("2026-02-14T00:00:00Z", refresh_hash),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(HTTPException) as revoked_exc:
        app_main.refresh(app_main.RefreshRequest(refresh_token=refresh_token))
    status_code, _ = _http_error_payload(app_main, revoked_exc.value)
    assert status_code == 401

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = NULL, expires_at = ?
            WHERE token_hash = ?
            """,
            ("1970-01-01T00:00:00Z", refresh_hash),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(HTTPException) as expired_exc:
        app_main.refresh(app_main.RefreshRequest(refresh_token=refresh_token))
    status_code, _ = _http_error_payload(app_main, expired_exc.value)
    assert status_code == 401

    with pytest.raises(HTTPException) as random_exc:
        app_main.refresh(app_main.RefreshRequest(refresh_token=secrets.token_urlsafe(32)))
    status_code, payload = _http_error_payload(app_main, random_exc.value)
    assert status_code == 401
    assert set(payload) == {"code", "message", "detail"}
