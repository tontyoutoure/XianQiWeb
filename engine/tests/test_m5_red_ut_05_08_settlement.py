"""M5 Red tests: M5-UT-05~08 settlement scenarios."""

from __future__ import annotations

from pathlib import Path
import sys

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from m5_settlement_testkit import (
    assert_seat_delta,
    load_engine_class,
    make_state,
    settle_and_index,
)


def test_m5_ut_05_all_not_enough_zero_delta() -> None:
    """M5-UT-05: with pillar counts 2/2/2 and no reveal relation, all deltas are zero."""

    Engine = load_engine_class()
    engine = Engine()
    engine.load_state(make_state(phase="settlement", version=105, pillar_counts=(2, 2, 2)))

    _, _, indexed = settle_and_index(engine)

    assert_seat_delta(indexed[0], delta=0, enough=0, reveal=0, ceramic=0)
    assert_seat_delta(indexed[1], delta=0, enough=0, reveal=0, ceramic=0)
    assert_seat_delta(indexed[2], delta=0, enough=0, reveal=0, ceramic=0)


def test_m5_ut_06_enough_and_ceramic_boundaries() -> None:
    """M5-UT-06: boundary identities for 2/3/5/6 should map to expected payments."""

    cases = [
        {
            "pillar_counts": (2, 3, 3),
            "expected": {
                0: (-2, -2, 0, 0),
                1: (1, 1, 0, 0),
                2: (1, 1, 0, 0),
            },
        },
        {
            "pillar_counts": (5, 2, 1),
            "expected": {
                0: (2, 2, 0, 0),
                1: (-1, -1, 0, 0),
                2: (-1, -1, 0, 0),
            },
        },
        {
            "pillar_counts": (6, 1, 1),
            "expected": {
                0: (6, 0, 0, 6),
                1: (-3, 0, 0, -3),
                2: (-3, 0, 0, -3),
            },
        },
    ]

    Engine = load_engine_class()
    for idx, case in enumerate(cases):
        engine = Engine()
        engine.load_state(
            make_state(
                phase="settlement",
                version=106 + idx,
                pillar_counts=case["pillar_counts"],
            )
        )

        _, _, indexed = settle_and_index(engine)
        for seat in (0, 1, 2):
            delta, enough, reveal, ceramic = case["expected"][seat]
            assert_seat_delta(indexed[seat], delta=delta, enough=enough, reveal=reveal, ceramic=ceramic)


def test_m5_ut_07_reveal_penalty_triggers_when_revealer_not_enough() -> None:
    """M5-UT-07: reveal penalty applies when revealer was-not-enough and remains not-enough."""

    Engine = load_engine_class()
    engine = Engine()
    engine.load_state(
        make_state(
            phase="settlement",
            version=107,
            pillar_counts=(2, 2, 2),
            reveal_relations=[
                {
                    "revealer_seat": 0,
                    "buckler_seat": 1,
                    "revealer_enough_at_time": False,
                }
            ],
        )
    )

    _, _, indexed = settle_and_index(engine)

    assert_seat_delta(indexed[0], delta=-1, enough=0, reveal=-1, ceramic=0)
    assert_seat_delta(indexed[1], delta=1, enough=0, reveal=1, ceramic=0)
    assert_seat_delta(indexed[2], delta=0, enough=0, reveal=0, ceramic=0)


def test_m5_ut_08_reveal_penalty_not_triggered_when_revealer_finally_enough() -> None:
    """M5-UT-08: no reveal penalty when revealer was-not-enough but finally reaches enough."""

    Engine = load_engine_class()
    engine = Engine()
    engine.load_state(
        make_state(
            phase="settlement",
            version=108,
            pillar_counts=(3, 2, 1),
            reveal_relations=[
                {
                    "revealer_seat": 0,
                    "buckler_seat": 1,
                    "revealer_enough_at_time": False,
                }
            ],
        )
    )

    _, _, indexed = settle_and_index(engine)

    assert_seat_delta(indexed[0], delta=2, enough=2, reveal=0, ceramic=0)
    assert_seat_delta(indexed[1], delta=-1, enough=-1, reveal=0, ceramic=0)
    assert_seat_delta(indexed[2], delta=-1, enough=-1, reveal=0, ceramic=0)
