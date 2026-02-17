"""M5 Red tests: M5-UT-09~12 settlement scenarios."""

from __future__ import annotations

from pathlib import Path
import sys

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from m5_settlement_testkit import (
    assert_seat_delta,
    extract_new_state,
    load_engine_class,
    make_state,
    settle_and_index,
)


def test_m5_ut_09_reveal_penalty_not_triggered_when_revealer_was_enough_at_time() -> None:
    """M5-UT-09: no reveal penalty when revealer_enough_at_time is true."""

    Engine = load_engine_class()
    engine = Engine()
    engine.load_state(
        make_state(
            phase="settlement",
            version=109,
            pillar_counts=(2, 2, 2),
            reveal_relations=[
                {
                    "revealer_seat": 0,
                    "buckler_seat": 1,
                    "revealer_enough_at_time": True,
                }
            ],
        )
    )

    _, _, indexed = settle_and_index(engine)

    assert_seat_delta(indexed[0], delta=0, enough=0, reveal=0, ceramic=0)
    assert_seat_delta(indexed[1], delta=0, enough=0, reveal=0, ceramic=0)
    assert_seat_delta(indexed[2], delta=0, enough=0, reveal=0, ceramic=0)


def test_m5_ut_10_multiple_reveal_relations_should_accumulate() -> None:
    """M5-UT-10: reveal deltas should accumulate across multiple valid reveal relations."""

    Engine = load_engine_class()
    engine = Engine()
    engine.load_state(
        make_state(
            phase="settlement",
            version=110,
            pillar_counts=(2, 2, 2),
            reveal_relations=[
                {
                    "revealer_seat": 0,
                    "buckler_seat": 1,
                    "revealer_enough_at_time": False,
                },
                {
                    "revealer_seat": 0,
                    "buckler_seat": 2,
                    "revealer_enough_at_time": False,
                },
            ],
        )
    )

    _, _, indexed = settle_and_index(engine)

    assert_seat_delta(indexed[0], delta=-2, enough=0, reveal=-2, ceramic=0)
    assert_seat_delta(indexed[1], delta=1, enough=0, reveal=1, ceramic=0)
    assert_seat_delta(indexed[2], delta=1, enough=0, reveal=1, ceramic=0)


def test_m5_ut_11_enough_at_reveal_and_final_non_ceramic_wins_no_enough_chips() -> None:
    """M5-UT-11: revealer already-enough and finally non-ceramic should not receive enough winnings."""

    Engine = load_engine_class()
    engine = Engine()
    engine.load_state(
        make_state(
            phase="settlement",
            version=111,
            pillar_counts=(3, 3, 2),
            reveal_relations=[
                {
                    "revealer_seat": 0,
                    "buckler_seat": 1,
                    "revealer_enough_at_time": True,
                }
            ],
        )
    )

    _, _, indexed = settle_and_index(engine)

    assert_seat_delta(indexed[0], delta=0, enough=0, reveal=0, ceramic=0)
    assert_seat_delta(indexed[1], delta=1, enough=1, reveal=0, ceramic=0)
    assert_seat_delta(indexed[2], delta=-1, enough=-1, reveal=0, ceramic=0)


def test_m5_ut_12_settle_advances_to_finished_and_returns_contract_payload() -> None:
    """M5-UT-12: settle should move state to finished and return settlement payload contract."""

    Engine = load_engine_class()
    engine = Engine()
    initial_version = 112
    engine.load_state(
        make_state(
            phase="settlement",
            version=initial_version,
            pillar_counts=(2, 2, 2),
            reveal_relations=[],
        )
    )

    output, settlement, indexed = settle_and_index(engine)
    new_state = extract_new_state(output)

    assert new_state["phase"] == "finished"
    assert int(new_state["version"]) == initial_version + 1

    final_state = settlement.get("final_state")
    assert isinstance(final_state, dict)
    assert isinstance(settlement.get("chip_delta_by_seat"), list)
    assert_seat_delta(indexed[0], delta=0, enough=0, reveal=0, ceramic=0)
    assert_seat_delta(indexed[1], delta=0, enough=0, reveal=0, ceramic=0)
    assert_seat_delta(indexed[2], delta=0, enough=0, reveal=0, ceramic=0)

