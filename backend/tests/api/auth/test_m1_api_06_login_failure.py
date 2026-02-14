"""M1-API-06 contract test (RED phase)."""

from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request


def _build_http_request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [],
            "query_string": b"",
        }
    )


def test_m1_api_06_login_failure_returns_401_with_unified_error_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: invalid credentials return 401 + {code,message,detail}."""
    db_path = tmp_path / "m1_api_06.sqlite3"
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "api-06-test-secret-key-32-bytes-minimum")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    app_main.register(app_main.RegisterRequest(username="Alice", password="123"))

    attempts = [
        app_main.LoginRequest(username="Alice", password="wrong-password"),
        app_main.LoginRequest(username="Bob", password="123"),
    ]
    for payload in attempts:
        with pytest.raises(HTTPException) as exc_info:
            app_main.login(payload)

        response = asyncio.run(
            app_main.handle_http_exception(_build_http_request("/api/auth/login"), exc_info.value)
        )
        body = json.loads(response.body.decode("utf-8"))

        assert response.status_code == 401
        assert body == {
            "code": "AUTH_INVALID_CREDENTIALS",
            "message": "invalid username or password",
            "detail": {},
        }
