"""M5 Red tests: M5-UT-13 black-chess settlement path."""

from __future__ import annotations

from pathlib import Path
import sys

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from m5_settlement_testkit import (
    assert_seat_delta,
    find_black_seed,
    load_engine_class,
    settle_and_index,
)


def test_m5_ut_13_black_chess_settlement_all_deltas_zero() -> None:
    """M5-UT-13: black-chess path should settle with zero deltas for all seats."""

    Engine = load_engine_class()
    seed = find_black_seed(Engine, max_seed=4096)

    engine = Engine()
    init_output = engine.init_game({"player_count": 3}, rng_seed=seed)
    state = init_output.get("new_state", {})
    assert state.get("phase") == "settlement"

    _, _, indexed = settle_and_index(engine)

    assert_seat_delta(indexed[0], delta=0, enough=0, reveal=0, ceramic=0)
    assert_seat_delta(indexed[1], delta=0, enough=0, reveal=0, ceramic=0)
    assert_seat_delta(indexed[2], delta=0, enough=0, reveal=0, ceramic=0)

