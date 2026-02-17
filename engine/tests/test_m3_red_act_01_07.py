"""M3 Red tests: M3-ACT-01~07 action validation and acting-seat advancement."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_engine_class():
    try:
        from engine.core import XianqiGameEngine  # type: ignore
    except ModuleNotFoundError as exc:
        pytest.fail(f"M3-ACT: missing engine module/class: {exc}")
    return XianqiGameEngine


def _extract_state(engine: Any, output: Any) -> dict[str, Any]:
    if isinstance(output, dict):
        state = output.get("new_state")
        if isinstance(state, dict):
            return state
    dumped = engine.dump_state()
    if isinstance(dumped, dict) and dumped:
        return dumped
    pytest.fail("apply_action should expose state via output.new_state or dump_state()")


def _find_action_idx(legal_actions: dict[str, Any], action_type: str) -> int:
    actions = legal_actions.get("actions", [])
    for idx, action in enumerate(actions):
        if action.get("type") == action_type:
            return idx
    pytest.fail(f"missing expected action type {action_type} in legal actions: {actions}")


def _make_buckle_state(*, version: int = 12) -> dict[str, Any]:
    return {
        "version": version,
        "phase": "buckle_flow",
        "players": [
            {"seat": 0, "hand": {"R_SHI": 1, "B_NIU": 1}},
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
        "reveal": {"buckler_seat": None, "active_revealer_seat": None, "pending_order": [], "relations": []},
    }


def _make_in_round_cover_state(
    *,
    current_seat: int,
    round_kind: int,
    required_cover_hand: dict[str, int],
    winner_seat: int = 1,
    plays: list[dict[str, Any]] | None = None,
    version: int = 21,
) -> dict[str, Any]:
    if plays is None:
        plays = [
            {"seat": winner_seat, "power": 8, "cards": [{"type": "B_SHI", "count": round_kind}]},
        ]

    return {
        "version": version,
        "phase": "in_round",
        "players": [
            {"seat": 0, "hand": required_cover_hand if current_seat == 0 else {}},
            {"seat": 1, "hand": required_cover_hand if current_seat == 1 else {}},
            {"seat": 2, "hand": required_cover_hand if current_seat == 2 else {}},
        ],
        "turn": {
            "current_seat": current_seat,
            "round_index": 2,
            "round_kind": round_kind,
            "last_combo": {
                "power": 8,
                "cards": [{"type": "B_SHI", "count": round_kind}],
                "owner_seat": winner_seat,
            },
            "plays": plays,
        },
        "pillar_groups": [],
        "reveal": {"buckler_seat": None, "active_revealer_seat": None, "pending_order": [], "relations": []},
    }


def _make_reveal_state(*, version: int = 31) -> dict[str, Any]:
    return {
        "version": version,
        "phase": "buckle_flow",
        "players": [
            {"seat": 0, "hand": {"R_SHI": 1}},
            {"seat": 1, "hand": {"B_SHI": 1}},
            {"seat": 2, "hand": {"R_NIU": 1}},
        ],
        "turn": {
            "current_seat": 1,
            "round_index": 4,
            "round_kind": 0,
            "last_combo": None,
            "plays": [],
        },
        "pillar_groups": [],
        "reveal": {
            "buckler_seat": 0,
            "active_revealer_seat": None,
            "pending_order": [1, 2],
            "relations": [],
        },
    }


def test_m3_act_01_action_index_out_of_range() -> None:
    """M3-ACT-01: out-of-range action_idx should be rejected."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(_make_buckle_state(version=12))

    with pytest.raises(ValueError, match="ENGINE_INVALID_ACTION_INDEX"):
        engine.apply_action(action_idx=999, client_version=12)


def test_m3_act_02_client_version_conflict() -> None:
    """M3-ACT-02: stale client_version should be rejected."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(_make_buckle_state(version=12))

    with pytest.raises(ValueError, match="ENGINE_VERSION_CONFLICT"):
        engine.apply_action(action_idx=0, client_version=11)


def test_m3_act_03_non_cover_action_must_not_accept_cover_list() -> None:
    """M3-ACT-03: non-COVER actions must reject non-empty cover_list."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(_make_buckle_state(version=13))

    legal_actions = engine.get_legal_actions(0)
    buckle_idx = _find_action_idx(legal_actions, "BUCKLE")

    with pytest.raises(ValueError, match="ENGINE_INVALID_COVER_LIST"):
        engine.apply_action(
            action_idx=buckle_idx,
            cover_list=[{"type": "B_NIU", "count": 1}],
            client_version=13,
        )


def test_m3_act_04_cover_wrong_count_rejected() -> None:
    """M3-ACT-04: COVER with wrong total card count should be rejected."""

    Engine = _load_engine_class()
    engine = Engine()
    state = _make_in_round_cover_state(
        current_seat=0,
        round_kind=2,
        required_cover_hand={"B_NIU": 2},
        winner_seat=1,
        version=21,
    )
    engine.load_state(state)

    legal_actions = engine.get_legal_actions(0)
    cover_idx = _find_action_idx(legal_actions, "COVER")

    with pytest.raises(ValueError, match="ENGINE_INVALID_COVER_LIST"):
        engine.apply_action(
            action_idx=cover_idx,
            cover_list=[{"type": "B_NIU", "count": 1}],
            client_version=21,
        )


def test_m3_act_05_cover_with_unowned_cards_rejected() -> None:
    """M3-ACT-05: COVER must reject cards not present in actor hand."""

    Engine = _load_engine_class()
    engine = Engine()
    state = _make_in_round_cover_state(
        current_seat=0,
        round_kind=1,
        required_cover_hand={"B_NIU": 1},
        winner_seat=1,
        version=22,
    )
    engine.load_state(state)

    legal_actions = engine.get_legal_actions(0)
    cover_idx = _find_action_idx(legal_actions, "COVER")

    with pytest.raises(ValueError, match="ENGINE_INVALID_COVER_LIST"):
        engine.apply_action(
            action_idx=cover_idx,
            cover_list=[{"type": "R_SHI", "count": 1}],
            client_version=22,
        )


def test_m3_act_06_round_end_advances_current_seat_to_winner() -> None:
    """M3-ACT-06: after third play, current seat should advance to round winner."""

    Engine = _load_engine_class()
    engine = Engine()

    state = _make_in_round_cover_state(
        current_seat=0,
        round_kind=1,
        required_cover_hand={"B_NIU": 1},
        winner_seat=1,
        plays=[
            {"seat": 1, "power": 8, "cards": [{"type": "B_SHI", "count": 1}]},
            {"seat": 2, "power": -1, "cards": [{"type": "B_CHE", "count": 1}]},
        ],
        version=23,
    )
    engine.load_state(state)

    legal_actions = engine.get_legal_actions(0)
    cover_idx = _find_action_idx(legal_actions, "COVER")

    output = engine.apply_action(
        action_idx=cover_idx,
        cover_list=[{"type": "B_NIU", "count": 1}],
        client_version=23,
    )
    next_state = _extract_state(engine, output)

    turn = next_state.get("turn") or {}
    assert next_state.get("phase") == "buckle_flow"
    assert turn.get("current_seat") == 1


def test_m3_act_07_reveal_pending_order_and_current_seat_progress() -> None:
    """M3-ACT-07: reveal action should consume pending_order and move current seat."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(_make_reveal_state(version=31))

    legal_actions = engine.get_legal_actions(1)
    pass_idx = _find_action_idx(legal_actions, "PASS_REVEAL")

    output = engine.apply_action(action_idx=pass_idx, client_version=31)
    next_state = _extract_state(engine, output)

    reveal = next_state.get("reveal") or {}
    turn = next_state.get("turn") or {}

    assert next_state.get("phase") == "buckle_flow"
    assert reveal.get("pending_order") == [2]
    assert turn.get("current_seat") == 2
    assert int(next_state.get("version", 0)) == 32
