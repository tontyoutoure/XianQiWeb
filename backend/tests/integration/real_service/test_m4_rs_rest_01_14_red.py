"""Scaffold-only M4 real-service REST tests (API 01~14).

All tests are intentionally skipped until the user assigns concrete test IDs
for TDD implementation.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_01_get_state_success() -> None:
    """M4-API-01: GET /api/games/{id}/state success."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_02_get_state_forbidden_non_member() -> None:
    """M4-API-02: /state rejects non-member."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_03_get_state_game_not_found() -> None:
    """M4-API-03: /state returns GAME_NOT_FOUND for unknown game."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_04_post_actions_success_version_increments() -> None:
    """M4-API-04: /actions success and version increments."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_05_post_actions_version_conflict() -> None:
    """M4-API-05: /actions rejects stale client_version."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_06_post_actions_reject_non_turn_player() -> None:
    """M4-API-06: /actions rejects non-turn player."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_07_post_actions_reject_invalid_cover_list() -> None:
    """M4-API-07: /actions rejects invalid cover_list."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_08_post_actions_forbidden_non_member() -> None:
    """M4-API-08: /actions rejects non-member."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_09_post_actions_game_not_found() -> None:
    """M4-API-09: /actions returns GAME_NOT_FOUND for unknown game."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_10_get_settlement_phase_gate() -> None:
    """M4-API-10: /settlement phase gate."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_11_get_settlement_success() -> None:
    """M4-API-11: /settlement success in settlement/finished phase."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_12_ready_reset_after_settlement() -> None:
    """M4-API-12: ready flags are reset after settlement."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_13_all_ready_in_settlement_starts_new_game() -> None:
    """M4-API-13: all ready in settlement starts a new game."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_14_partial_ready_in_settlement_not_start() -> None:
    """M4-API-14: partial ready in settlement does not start a new game."""
    pass
