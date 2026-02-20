"""M3 UT test: load_state should fail fast for non-canonical players order."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_engine_class():
    from engine.core import XianqiGameEngine  # type: ignore

    return XianqiGameEngine


def _make_valid_state() -> dict:
    return {
        "version": 1,
        "phase": "buckle_flow",
        "players": [
            {"seat": 0, "hand": {"R_SHI": 1}},
            {"seat": 1, "hand": {"B_SHI": 1}},
            {"seat": 2, "hand": {"R_NIU": 1}},
        ],
        "turn": {
            "current_seat": 0,
            "round_index": 0,
            "round_kind": 0,
            "last_combo": None,
            "plays": [],
        },
        "pillar_groups": [],
        "reveal": {
            "buckler_seat": None,
            "active_revealer_seat": None,
            "pending_order": [],
            "relations": [],
        },
    }


def test_m3_ut_08_load_state_asserts_players_index_matches_seat() -> None:
    """M3-UT-08: load_state should assert when players list is not seat-indexed."""

    Engine = _load_engine_class()
    engine = Engine()

    broken_state = _make_valid_state()
    broken_state["players"] = [
        {"seat": 1, "hand": {"R_SHI": 1}},
        {"seat": 0, "hand": {"B_SHI": 1}},
        {"seat": 2, "hand": {"R_NIU": 1}},
    ]

    with pytest.raises(AssertionError):
        engine.load_state(broken_state)


def test_m3_ssot_02_load_state_rejects_legacy_pillars_field() -> None:
    """M3-SSOT-02: load_state should fail fast when legacy pillars field exists."""

    Engine = _load_engine_class()
    engine = Engine()

    legacy_state = _make_valid_state()
    legacy_state["pillar_groups"] = [
        {
            "round_index": 0,
            "winner_seat": 1,
            "round_kind": 2,
            "plays": [],
            "pillars": [{"index": 0, "cards": [{"type": "R_SHI", "count": 3}]}],
        }
    ]

    with pytest.raises(AssertionError):
        engine.load_state(legacy_state)


def test_m3_cm_02_load_state_rejects_legacy_cards_array_shape() -> None:
    """M3-CM-02: load_state should reject legacy cards array in play entries."""

    Engine = _load_engine_class()
    engine = Engine()

    legacy_cards_state = _make_valid_state()
    legacy_cards_state["phase"] = "in_round"
    legacy_cards_state["turn"] = {
        "current_seat": 0,
        "round_index": 0,
        "round_kind": 1,
        "last_combo": {
            "power": 9,
            "cards": {"R_SHI": 1},
            "owner_seat": 0,
        },
        "plays": [
            {
                "seat": 0,
                "power": 9,
                "cards": [{"type": "R_SHI", "count": 1}],
            }
        ],
    }

    with pytest.raises(AssertionError):
        engine.load_state(legacy_cards_state)


def test_m3_ut_09_load_state_rejects_reveal_missing_active_revealer_seat() -> None:
    """M3-UT-09: load_state should reject reveal missing active_revealer_seat field."""

    Engine = _load_engine_class()
    engine = Engine()

    broken_state = _make_valid_state()
    broken_state["reveal"] = {
        "buckler_seat": None,
        "pending_order": [],
        "relations": [],
    }

    with pytest.raises(AssertionError):
        engine.load_state(broken_state)


def test_m3_ut_09_load_state_rejects_reveal_pending_order_duplicates() -> None:
    """M3-UT-09: load_state should reject reveal.pending_order with duplicate seats."""

    Engine = _load_engine_class()
    engine = Engine()

    broken_state = _make_valid_state()
    broken_state["reveal"]["pending_order"] = [1, 1]

    with pytest.raises(AssertionError):
        engine.load_state(broken_state)


def test_m3_ut_09_load_state_rejects_reveal_relation_non_boolean_flag() -> None:
    """M3-UT-09: load_state should reject reveal relation when enough-at-time flag is non-bool."""

    Engine = _load_engine_class()
    engine = Engine()

    broken_state = _make_valid_state()
    broken_state["reveal"]["relations"] = [
        {
            "revealer_seat": 1,
            "buckler_seat": 2,
            "revealer_enough_at_time": 1,
        }
    ]

    with pytest.raises(AssertionError):
        engine.load_state(broken_state)
