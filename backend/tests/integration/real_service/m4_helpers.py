"""Scaffold helpers for M4 real-service REST tests.

This module intentionally contains signatures only.
Implement helpers after specific M4 test IDs are assigned.
"""

from __future__ import annotations

from typing import Any


def build_auth_headers(access_token: str) -> dict[str, str]:
    """Build standard Bearer auth headers."""
    return {"Authorization": f"Bearer {access_token}"}


def assert_error_payload(*, response: Any, expected_status: int) -> dict[str, object]:
    """Assert unified error payload for REST APIs."""
    raise NotImplementedError("M4 scaffold only; helper body pending")


def register_user(*, base_url: str, username: str, password: str = "123") -> tuple[int, str]:
    """Register one user and return (user_id, access_token)."""
    raise NotImplementedError("M4 scaffold only; helper body pending")


def join_room(*, base_url: str, access_token: str, room_id: int) -> dict[str, Any]:
    """Join one room and return room detail payload."""
    raise NotImplementedError("M4 scaffold only; helper body pending")


def set_room_ready(*, base_url: str, access_token: str, room_id: int, ready: bool) -> dict[str, Any]:
    """Set room ready flag and return room detail payload."""
    raise NotImplementedError("M4 scaffold only; helper body pending")


def get_room_detail(*, base_url: str, access_token: str, room_id: int) -> dict[str, Any]:
    """Fetch room detail payload."""
    raise NotImplementedError("M4 scaffold only; helper body pending")


def get_game_state(*, base_url: str, access_token: str, game_id: int) -> dict[str, Any]:
    """Fetch game state payload."""
    raise NotImplementedError("M4 scaffold only; helper body pending")


def post_game_action(
    *,
    base_url: str,
    access_token: str,
    game_id: int,
    action_idx: int,
    client_version: int,
    cover_list: dict[str, int] | None = None,
) -> int:
    """Submit one game action and return HTTP status code."""
    raise NotImplementedError("M4 scaffold only; helper body pending")


def get_game_settlement(*, base_url: str, access_token: str, game_id: int) -> dict[str, Any]:
    """Fetch game settlement payload."""
    raise NotImplementedError("M4 scaffold only; helper body pending")
