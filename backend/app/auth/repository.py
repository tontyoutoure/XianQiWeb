"""Persistence helpers for auth workflows."""

from __future__ import annotations

import sqlite3

from app.core.config import Settings
from app.core.db import create_sqlite_connection

UserAuthRow = tuple[int, str, str, str]
UserProfileRow = tuple[int, str, str]


def create_user(
    *,
    settings: Settings,
    username: str,
    password_hash: str,
    created_at: str,
) -> int:
    """Insert a user and return its id."""
    conn = create_sqlite_connection(settings.xqweb_sqlite_path)
    try:
        conn.execute("BEGIN")
        cursor = conn.execute(
            """
            INSERT INTO users (username, password_hash, created_at)
            VALUES (?, ?, ?)
            """,
            (username, password_hash, created_at),
        )
        user_id = int(cursor.lastrowid)
        conn.commit()
        return user_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user_auth_row(*, settings: Settings, username: str) -> UserAuthRow | None:
    """Fetch the fields needed by login/auth session issuance."""
    conn = create_sqlite_connection(settings.xqweb_sqlite_path)
    try:
        row = conn.execute(
            """
            SELECT id, username, password_hash, created_at
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()
        if row is None:
            return None
        user_id, user_name, password_hash, created_at = row
        return (int(user_id), str(user_name), str(password_hash), str(created_at))
    finally:
        conn.close()


def create_refresh_token(
    *,
    settings: Settings,
    user_id: int,
    token_hash: str,
    expires_at: str,
    created_at: str,
) -> None:
    """Insert one refresh token row."""
    conn = create_sqlite_connection(settings.xqweb_sqlite_path)
    try:
        conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at, created_at, revoked_at)
            VALUES (?, ?, ?, ?, NULL)
            """,
            (user_id, token_hash, expires_at, created_at),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_profile_by_id(*, settings: Settings, user_id: int) -> UserProfileRow | None:
    """Fetch user profile returned by /api/auth/me."""
    conn = create_sqlite_connection(settings.xqweb_sqlite_path)
    try:
        row = conn.execute(
            """
            SELECT id, username, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        uid, username, created_at = row
        return (int(uid), str(username), str(created_at))
    finally:
        conn.close()
