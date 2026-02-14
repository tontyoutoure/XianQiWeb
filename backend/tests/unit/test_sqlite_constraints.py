"""M1-UT-04 SQLite foreign key contract test."""

from __future__ import annotations


def test_m1_ut_04_sqlite_foreign_keys_enabled(app_not_ready: None) -> None:
    """Contract: SQLite connection must enable PRAGMA foreign_keys=ON.

    Expected input:
    - insert refresh token row with non-existent user_id

    Expected output:
    - insert fails with foreign key constraint error
    """
