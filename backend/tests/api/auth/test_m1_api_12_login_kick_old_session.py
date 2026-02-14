"""M1-API-12 contract test (RED phase)."""

from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request


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


def test_m1_api_12_login_kicks_old_session_refresh_but_old_access_still_works_until_expiry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: second login invalidates previous refresh but not previous access token."""
    db_path = tmp_path / "m1_api_12.sqlite3"
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "api-12-test-secret")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    register_result = app_main.register(app_main.RegisterRequest(username="Alice", password="123"))

    old_login = app_main.login(app_main.LoginRequest(username="Alice", password="123"))
    new_login = app_main.login(app_main.LoginRequest(username="Alice", password="123"))

    assert old_login["user"]["id"] == new_login["user"]["id"] == register_result["user"]["id"]
    assert old_login["refresh_token"] != new_login["refresh_token"]

    with pytest.raises(HTTPException) as old_refresh_exc:
        app_main.refresh(app_main.RefreshRequest(refresh_token=old_login["refresh_token"]))
    status_code, _ = _http_error_payload(app_main, old_refresh_exc.value)
    assert status_code == 401

    rotated_from_new = app_main.refresh(app_main.RefreshRequest(refresh_token=new_login["refresh_token"]))
    assert {"access_token", "expires_in", "refresh_token", "refresh_expires_in"} <= set(rotated_from_new)

    profile = app_main.me(old_login["access_token"])
    assert profile["id"] == register_result["user"]["id"]
    assert profile["username"] == "Alice"
