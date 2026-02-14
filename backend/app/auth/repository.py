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


def revoke_refresh_tokens_for_user(*, settings: Settings, user_id: int, revoked_at: str) -> None:
    """Revoke all currently active refresh tokens for a user."""
    conn = create_sqlite_connection(settings.xqweb_sqlite_path)
    try:
        conn.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = ?
            WHERE user_id = ? AND revoked_at IS NULL
            """,
            (revoked_at, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def consume_refresh_token(
    *,
    settings: Settings,
    token_hash: str,
    now_iso: str,
    revoked_at: str,
) -> int | None:
    """Validate and revoke one refresh token, returning the bound user id."""
    conn = create_sqlite_connection(settings.xqweb_sqlite_path)
    try:
        conn.execute("BEGIN")
        row = conn.execute(
            """
            SELECT id, user_id, expires_at, revoked_at
            FROM refresh_tokens
            WHERE token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
        if row is None:
            conn.rollback()
            return None

        token_id, user_id, expires_at, existing_revoked_at = row
        if existing_revoked_at is not None or str(expires_at) <= now_iso:
            conn.rollback()
            return None

        conn.execute(
            "UPDATE refresh_tokens SET revoked_at = ? WHERE id = ?",
            (revoked_at, token_id),
        )
        conn.commit()
        return int(user_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def revoke_refresh_token_by_hash(*, settings: Settings, token_hash: str, revoked_at: str) -> None:
    """Revoke one refresh token idempotently."""
    conn = create_sqlite_connection(settings.xqweb_sqlite_path)
    try:
        conn.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = COALESCE(revoked_at, ?)
            WHERE token_hash = ?
            """,
            (revoked_at, token_hash),
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
