"""M1-UT-04 SQLite foreign key contract test (RED phase)."""

from __future__ import annotations

import sqlite3

import pytest

from app.core.db import create_sqlite_connection


CREATE_SCHEMA_SQL = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE refresh_tokens (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revoked_at TEXT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""


def test_m1_ut_04_sqlite_foreign_keys_enabled() -> None:
    """Input: insert orphan refresh_token.user_id -> Output: FK integrity error."""
    conn = create_sqlite_connection(":memory:")
    conn.executescript(CREATE_SCHEMA_SQL)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at, created_at, revoked_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (999, "hash-1", "2026-02-15T00:00:00Z", "2026-02-14T00:00:00Z", None),
        )
