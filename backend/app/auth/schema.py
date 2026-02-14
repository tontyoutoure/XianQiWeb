"""Schema bootstrap for auth tables."""

from __future__ import annotations

from app.core.config import Settings
from app.core.db import create_sqlite_connection


CREATE_AUTH_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revoked_at TEXT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
"""


def init_auth_schema(settings: Settings) -> None:
    """Ensure auth tables/indexes exist."""
    conn = create_sqlite_connection(settings.xqweb_sqlite_path)
    try:
        conn.executescript(CREATE_AUTH_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
