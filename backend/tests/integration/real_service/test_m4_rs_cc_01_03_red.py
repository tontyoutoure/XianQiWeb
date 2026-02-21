"""Scaffold-only M4 real-service concurrency tests (CC 01~03).

All tests are intentionally skipped until the user assigns concrete test IDs
for TDD implementation.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_cc_01_concurrent_actions_single_winner() -> None:
    """M4-CC-01: concurrent actions allow only one winner."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_cc_02_concurrent_ready_after_settlement_single_new_game() -> None:
    """M4-CC-02: concurrent ready after settlement creates one new game."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_cc_03_concurrent_third_ready_only_one_game_created() -> None:
    """M4-CC-03: concurrent third-ready edge creates one game only."""
    pass
