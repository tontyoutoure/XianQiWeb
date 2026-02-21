"""Scaffold scenario builders for M4 real-service tests.

This module intentionally contains signatures only.
Implement scenario bodies after specific M4 test IDs are assigned.
"""

from __future__ import annotations

from typing import Any


def setup_three_players_and_start_game(*, base_url: str, room_id: int = 0) -> dict[str, Any]:
    """Create 3 users, join one room, set all ready, and return scenario context."""
    raise NotImplementedError("M4 scaffold only; scenario body pending")


def drive_game_with_fixed_script(
    *,
    base_url: str,
    game_id: int,
    player_tokens_by_seat: dict[int, str],
    script_name: str,
) -> dict[str, Any]:
    """Advance one game with a fixed script and return resulting state snapshot."""
    raise NotImplementedError("M4 scaffold only; scenario body pending")


def drive_game_to_settlement(
    *,
    base_url: str,
    game_id: int,
    player_tokens_by_seat: dict[int, str],
) -> dict[str, Any]:
    """Advance one game to settlement phase using fixed script data."""
    raise NotImplementedError("M4 scaffold only; scenario body pending")


def run_concurrent_action_race(
    *,
    base_url: str,
    game_id: int,
    actor_a_token: str,
    actor_b_token: str,
    action_idx: int,
    client_version: int,
) -> dict[str, Any]:
    """Submit two concurrent actions for race-condition assertions."""
    raise NotImplementedError("M4 scaffold only; scenario body pending")


def run_concurrent_ready_after_settlement(
    *,
    base_url: str,
    room_id: int,
    player_tokens: list[str],
) -> dict[str, Any]:
    """Submit concurrent ready actions after settlement for one room."""
    raise NotImplementedError("M4 scaffold only; scenario body pending")
