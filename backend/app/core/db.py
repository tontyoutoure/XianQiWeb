"""SQLite connection helpers for backend persistence."""

from __future__ import annotations

import sqlite3


def create_sqlite_connection(path: str) -> sqlite3.Connection:
    """Create a SQLite connection with foreign key enforcement enabled."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
