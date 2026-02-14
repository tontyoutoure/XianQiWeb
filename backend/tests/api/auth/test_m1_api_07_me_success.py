"""M1-API-07 contract test (GREEN phase)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_m1_api_07_me_requires_valid_bearer_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: GET /api/auth/me returns current user for valid access token."""
    db_path = tmp_path / "m1_api_07.sqlite3"
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "api-07-test-secret")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    register_result = app_main.register(app_main.RegisterRequest(username="Alice", password="123"))

    me_result = app_main.me(register_result["access_token"])
    assert me_result == {
        "id": register_result["user"]["id"],
        "username": "Alice",
        "created_at": register_result["user"]["created_at"],
    }
