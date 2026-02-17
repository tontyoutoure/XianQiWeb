"""M5 Red tests: M5-UT-01~04 settlement baseline scenarios."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from m5_settlement_testkit import (
    assert_seat_delta,
    load_engine_class,
    make_state,
    settle_and_index,
)


def test_m5_ut_01_settle_rejects_non_settlement_phase() -> None:
    """M5-UT-01: settle should reject calls when phase is not settlement."""

    Engine = load_engine_class()
    engine = Engine()
    engine.load_state(make_state(phase="in_round", version=101))

    with pytest.raises(ValueError, match="ENGINE_INVALID_PHASE"):
        engine.settle()


def test_m5_ut_02_one_enough_two_not_enough() -> None:
    """M5-UT-02: with pillar counts 3/2/1, non-enough seats each pay one to enough seat."""

    Engine = load_engine_class()
    engine = Engine()
    engine.load_state(make_state(phase="settlement", version=102, pillar_counts=(3, 2, 1)))

    _, _, indexed = settle_and_index(engine)

    assert_seat_delta(indexed[0], delta=2, enough=2, reveal=0, ceramic=0)
    assert_seat_delta(indexed[1], delta=-1, enough=-1, reveal=0, ceramic=0)
    assert_seat_delta(indexed[2], delta=-1, enough=-1, reveal=0, ceramic=0)


def test_m5_ut_03_one_ceramic_two_not_enough() -> None:
    """M5-UT-03: with pillar counts 6/2/0, non-enough seats each pay three to ceramic seat."""

    Engine = load_engine_class()
    engine = Engine()
    engine.load_state(make_state(phase="settlement", version=103, pillar_counts=(6, 2, 0)))

    _, _, indexed = settle_and_index(engine)

    assert_seat_delta(indexed[0], delta=6, enough=0, reveal=0, ceramic=6)
    assert_seat_delta(indexed[1], delta=-3, enough=0, reveal=0, ceramic=-3)
    assert_seat_delta(indexed[2], delta=-3, enough=0, reveal=0, ceramic=-3)


def test_m5_ut_04_two_enough_one_not_enough() -> None:
    """M5-UT-04: with pillar counts 3/3/2, non-enough seat pays one to each enough seat."""

    Engine = load_engine_class()
    engine = Engine()
    engine.load_state(make_state(phase="settlement", version=104, pillar_counts=(3, 3, 2)))

    _, _, indexed = settle_and_index(engine)

    assert_seat_delta(indexed[0], delta=1, enough=1, reveal=0, ceramic=0)
    assert_seat_delta(indexed[1], delta=1, enough=1, reveal=0, ceramic=0)
    assert_seat_delta(indexed[2], delta=-2, enough=-2, reveal=0, ceramic=0)
