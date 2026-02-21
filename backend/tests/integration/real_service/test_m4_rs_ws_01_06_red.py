"""Scaffold-only M4 real-service websocket tests (WS 01~06).

All tests are intentionally skipped until the user assigns concrete test IDs
for TDD implementation.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_ws_01_room_snapshot_without_game_only_room_update() -> None:
    """M4-WS-01: initial room snapshot without game sends ROOM_UPDATE only."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_ws_02_room_snapshot_with_game_ordered_events() -> None:
    """M4-WS-02: initial room snapshot with game follows ordered events."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_ws_03_action_pushes_game_public_state() -> None:
    """M4-WS-03: successful action pushes GAME_PUBLIC_STATE."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_ws_04_private_state_is_unicast_per_seat() -> None:
    """M4-WS-04: GAME_PRIVATE_STATE is unicast without leaking others."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_ws_05_enter_settlement_pushes_settlement_event() -> None:
    """M4-WS-05: entering settlement pushes SETTLEMENT event."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_ws_06_leave_during_playing_pushes_waiting_without_settlement() -> None:
    """M4-WS-06: leave during playing pushes waiting room update without settlement."""
    pass
