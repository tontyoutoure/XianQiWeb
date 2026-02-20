"""M5 Red tests: M5-UT-13 black-opening reroll behavior."""

from __future__ import annotations

from pathlib import Path
import sys

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from m5_settlement_testkit import (
    find_black_opening_seed,
    load_engine_class,
)


def _has_black_hand(hand: dict[str, int]) -> bool:
    shi_xiang = hand.get("R_SHI", 0) + hand.get("B_SHI", 0) + hand.get("R_XIANG", 0) + hand.get("B_XIANG", 0)
    return shi_xiang == 0


def test_m5_ut_13_black_opening_seed_rerolls_to_playable_state() -> None:
    """M5-UT-13: black-opening seed should reroll to a non-black buckle_flow state."""

    Engine = load_engine_class()
    seed = find_black_opening_seed(max_seed=4096)

    engine = Engine()
    init_output = engine.init_game({"player_count": 3}, rng_seed=seed)
    state = init_output.get("new_state", {})
    players = state.get("players", [])

    assert state.get("phase") == "buckle_flow"
    assert len(players) == 3
    assert not any(_has_black_hand(player.get("hand", {})) for player in players)
