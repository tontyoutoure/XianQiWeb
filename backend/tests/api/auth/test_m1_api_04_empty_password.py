"""M1-API-04 contract test (GREEN phase)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_m1_api_04_empty_password_is_allowed_in_mvp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: register/login accepts empty password in MVP."""
    db_path = tmp_path / "m1_api_04.sqlite3"
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "api-04-test-secret")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()

    register_payload = app_main.RegisterRequest(username="Alice", password="")
    register_result = app_main.register(register_payload)
    assert register_result["user"]["username"] == "Alice"

    login_payload = app_main.LoginRequest(username="Alice", password="")
    login_result = app_main.login(login_payload)
    assert register_result["user"]["id"] == login_result["user"]["id"]
