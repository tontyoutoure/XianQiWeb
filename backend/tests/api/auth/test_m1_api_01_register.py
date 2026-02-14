"""M1-API-01 contract test."""

from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

import pytest


def test_m1_api_01_register_returns_auth_session(
    register_payload: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: register returns auth session and persists user/session rows."""
    db_path = tmp_path / "m1_api_01.sqlite3"
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "api-01-test-secret-key-32-bytes-minimum")

    import app.main as app_main

    app_main = importlib.reload(app_main)

    app_main.startup()
    payload = app_main.register(app_main.RegisterRequest(**register_payload))

    assert {"access_token", "refresh_token", "expires_in", "refresh_expires_in", "user"} <= set(
        payload
    )
    assert payload["user"]["username"] == "Alice"
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        user_row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            ("Alice",),
        ).fetchone()
        assert user_row is not None
        assert user_row["password_hash"] != register_payload["password"]

        refresh_row = conn.execute(
            "SELECT user_id, token_hash, revoked_at FROM refresh_tokens WHERE user_id = ?",
            (user_row["id"],),
        ).fetchone()
        assert refresh_row is not None
        assert refresh_row["revoked_at"] is None
        assert refresh_row["token_hash"] != payload["refresh_token"]
    finally:
        conn.close()
