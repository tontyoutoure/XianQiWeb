"""M1-API-05 contract test (GREEN phase)."""

from __future__ import annotations

import importlib
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest


def test_m1_api_05_login_success_returns_new_token_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: POST /api/auth/login returns a fresh token pair."""
    db_path = tmp_path / "m1_api_05.sqlite3"
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "api-05-test-secret")

    import app.auth.session as auth_session
    import app.main as app_main

    fixed_now = datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(auth_session, "utc_now", lambda: fixed_now)

    app_main = importlib.reload(app_main)
    app_main.startup()

    register_result = app_main.register(app_main.RegisterRequest(username="Alice", password="123"))
    login_result = app_main.login(app_main.LoginRequest(username="Alice", password="123"))

    assert {"access_token", "refresh_token", "expires_in", "refresh_expires_in", "user"} <= set(login_result)
    assert login_result["user"]["id"] == register_result["user"]["id"]
    assert login_result["refresh_token"] != register_result["refresh_token"]
    assert login_result["access_token"] != register_result["access_token"]
