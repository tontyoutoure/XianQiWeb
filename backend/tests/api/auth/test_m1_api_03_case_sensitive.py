"""M1-API-03 contract test (GREEN phase)."""

from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

import pytest


def test_m1_api_03_username_is_case_sensitive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: Tom and tom can both register as different users."""
    db_path = tmp_path / "m1_api_03.sqlite3"
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "api-03-test-secret")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()

    tom_upper = app_main.register(app_main.RegisterRequest(username="Tom", password="123"))
    tom_lower = app_main.register(app_main.RegisterRequest(username="tom", password="456"))

    assert tom_upper["user"]["username"] == "Tom"
    assert tom_lower["user"]["username"] == "tom"
    assert tom_upper["user"]["id"] != tom_lower["user"]["id"]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, username
            FROM users
            WHERE username IN (?, ?)
            ORDER BY id ASC
            """,
            ("Tom", "tom"),
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 2
    assert [row["username"] for row in rows] == ["Tom", "tom"]
