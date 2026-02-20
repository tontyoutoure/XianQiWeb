"""M3 Red tests: buckle_flow reveal-buckle transition coverage (M3-BF-01~11)."""

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
        pytest.fail(f"M3-BF: missing engine module/class: {exc}")
    return XianqiGameEngine


def _find_action_idx(legal_actions: dict[str, Any], action_type: str) -> int:
    actions = legal_actions.get("actions", [])
    for idx, action in enumerate(actions):
        if action.get("type") == action_type:
            return idx
    pytest.fail(f"missing expected action type {action_type} in legal actions: {actions}")


def _extract_state(engine: Any, output: Any) -> dict[str, Any]:
    if isinstance(output, dict):
        state = output.get("new_state")
        if isinstance(state, dict):
            return state
    dumped = engine.dump_state()
    if isinstance(dumped, dict) and dumped:
        return dumped
    pytest.fail("apply_action should expose state via output.new_state or dump_state()")


def _make_buckle_flow_state(
    *,
    current_seat: int = 0,
    pending_order: list[int] | None = None,
    buckler_seat: int | None = None,
    active_revealer_seat: int | None = None,
    relations: list[dict[str, Any]] | None = None,
    version: int = 50,
) -> dict[str, Any]:
    if pending_order is None:
        pending_order = []
    if relations is None:
        relations = []
    return {
        "version": version,
        "phase": "buckle_flow",
        "players": [
            {"seat": 0, "hand": {"R_SHI": 1, "B_NIU": 1}},
            {"seat": 1, "hand": {"B_SHI": 1, "R_NIU": 1}},
            {"seat": 2, "hand": {"R_XIANG": 1, "B_CHE": 1}},
        ],
        "turn": {
            "current_seat": current_seat,
            "round_index": 3,
            "round_kind": 0,
            "last_combo": None,
            "plays": [],
        },
        "pillar_groups": [],
        "reveal": {
            "buckler_seat": buckler_seat,
            "active_revealer_seat": active_revealer_seat,
            "pending_order": pending_order,
            "relations": relations,
        },
    }


def _make_in_round_round_end_state(*, version: int = 90) -> dict[str, Any]:
    return {
        "version": version,
        "phase": "in_round",
        "players": [
            {"seat": 0, "hand": {"B_NIU": 1}},
            {"seat": 1, "hand": {}},
            {"seat": 2, "hand": {}},
        ],
        "turn": {
            "current_seat": 0,
            "round_index": 4,
            "round_kind": 1,
            "last_combo": {
                "power": 8,
                "cards": {"B_SHI": 1},
                "owner_seat": 1,
            },
            "plays": [
                {"seat": 1, "power": 8, "cards": {"B_SHI": 1}},
                {"seat": 2, "power": -1, "cards": {"B_CHE": 1}},
            ],
        },
        "pillar_groups": [],
        "reveal": {
            "buckler_seat": 2,
            "active_revealer_seat": 1,
            "pending_order": [1],
            "relations": [
                {
                    "revealer_seat": 1,
                    "buckler_seat": 2,
                    "revealer_enough_at_time": False,
                }
            ],
        },
    }


def test_m3_bf_01_buckle_flow_start_only_buckle_actions() -> None:
    """M3-BF-01: buckle_flow start should only expose BUCKLE/PASS_BUCKLE."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(_make_buckle_flow_state(current_seat=0, pending_order=[]))

    legal = engine.get_legal_actions(0)
    action_types = [action.get("type") for action in legal.get("actions", [])]

    assert action_types == ["BUCKLE", "PASS_BUCKLE"]


def test_m3_bf_02_pass_buckle_enters_in_round_first_hand_state() -> None:
    """M3-BF-02: PASS_BUCKLE should enter in_round with first-hand pre-state."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(_make_buckle_flow_state(current_seat=0, pending_order=[]))

    legal = engine.get_legal_actions(0)
    pass_idx = _find_action_idx(legal, "PASS_BUCKLE")

    output = engine.apply_action(action_idx=pass_idx, client_version=50)
    next_state = _extract_state(engine, output)

    turn = next_state.get("turn") or {}
    assert next_state.get("phase") == "in_round"
    assert turn.get("current_seat") == 0
    assert turn.get("round_kind") == 0
    assert turn.get("plays") == []
    assert turn.get("last_combo") is None


def test_m3_bf_03_buckle_with_active_revealer_prioritized() -> None:
    """M3-BF-03: BUCKLE should ask active revealer first when present."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(
        _make_buckle_flow_state(
            current_seat=2,
            pending_order=[],
            active_revealer_seat=1,
        )
    )

    legal = engine.get_legal_actions(2)
    buckle_idx = _find_action_idx(legal, "BUCKLE")

    output = engine.apply_action(action_idx=buckle_idx, client_version=50)
    next_state = _extract_state(engine, output)

    reveal = next_state.get("reveal") or {}
    turn = next_state.get("turn") or {}
    assert reveal.get("buckler_seat") == 2
    assert reveal.get("pending_order") == [1, 0]
    assert turn.get("current_seat") == 1
    assert next_state.get("phase") == "buckle_flow"


def test_m3_bf_04_buckle_without_active_revealer_uses_counterclockwise_order() -> None:
    """M3-BF-04: BUCKLE should ask next two seats counterclockwise by default."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(
        _make_buckle_flow_state(
            current_seat=2,
            pending_order=[],
            active_revealer_seat=None,
        )
    )

    legal = engine.get_legal_actions(2)
    buckle_idx = _find_action_idx(legal, "BUCKLE")

    output = engine.apply_action(action_idx=buckle_idx, client_version=50)
    next_state = _extract_state(engine, output)

    reveal = next_state.get("reveal") or {}
    assert reveal.get("pending_order") == [0, 1]


def test_m3_bf_05_pass_reveal_consumes_pending_order_and_advances_turn() -> None:
    """M3-BF-05: PASS_REVEAL should consume queue head and advance current seat."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(
        _make_buckle_flow_state(
            current_seat=1,
            pending_order=[1, 2],
            buckler_seat=0,
            version=51,
        )
    )

    legal = engine.get_legal_actions(1)
    pass_idx = _find_action_idx(legal, "PASS_REVEAL")

    output = engine.apply_action(action_idx=pass_idx, client_version=51)
    next_state = _extract_state(engine, output)

    reveal = next_state.get("reveal") or {}
    turn = next_state.get("turn") or {}
    assert next_state.get("phase") == "buckle_flow"
    assert reveal.get("pending_order") == [2]
    assert turn.get("current_seat") == 2


def test_m3_bf_06_first_reveal_hits_and_immediately_enters_in_round() -> None:
    """M3-BF-06: first REVEAL should stop asking and return to buckler in in_round."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(
        _make_buckle_flow_state(
            current_seat=1,
            pending_order=[1, 2],
            buckler_seat=0,
            version=52,
        )
    )

    legal = engine.get_legal_actions(1)
    reveal_idx = _find_action_idx(legal, "REVEAL")

    output = engine.apply_action(action_idx=reveal_idx, client_version=52)
    next_state = _extract_state(engine, output)

    reveal = next_state.get("reveal") or {}
    turn = next_state.get("turn") or {}
    relations = reveal.get("relations") or []

    assert next_state.get("phase") == "in_round"
    assert reveal.get("pending_order") == []
    assert reveal.get("active_revealer_seat") == 1
    assert turn.get("current_seat") == 0
    assert len(relations) == 1
    assert relations[0].get("revealer_seat") == 1
    assert relations[0].get("buckler_seat") == 0


def test_m3_bf_07_active_revealer_pass_reveal_clears_active() -> None:
    """M3-BF-07: active revealer PASS_REVEAL should clear active_revealer_seat."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(
        _make_buckle_flow_state(
            current_seat=1,
            pending_order=[1, 2],
            buckler_seat=0,
            active_revealer_seat=1,
            version=53,
        )
    )

    legal = engine.get_legal_actions(1)
    pass_idx = _find_action_idx(legal, "PASS_REVEAL")

    output = engine.apply_action(action_idx=pass_idx, client_version=53)
    next_state = _extract_state(engine, output)

    reveal = next_state.get("reveal") or {}
    turn = next_state.get("turn") or {}
    assert reveal.get("active_revealer_seat") is None
    assert reveal.get("pending_order") == [2]
    assert turn.get("current_seat") == 2


def test_m3_bf_08_no_revealer_after_all_pass_enters_settlement() -> None:
    """M3-BF-08: when all asked seats PASS_REVEAL, phase should enter settlement."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(
        _make_buckle_flow_state(
            current_seat=1,
            pending_order=[1],
            buckler_seat=0,
            relations=[],
            version=54,
        )
    )

    legal = engine.get_legal_actions(1)
    pass_idx = _find_action_idx(legal, "PASS_REVEAL")

    output = engine.apply_action(action_idx=pass_idx, client_version=54)
    next_state = _extract_state(engine, output)

    reveal = next_state.get("reveal") or {}
    assert reveal.get("pending_order") == []
    assert next_state.get("phase") == "settlement"


def test_m3_bf_09_round_finish_resets_buckle_flow_and_cleans_reveal_residue() -> None:
    """M3-BF-09: third play should start next buckle_flow and clean reveal residue."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(_make_in_round_round_end_state(version=90))

    legal = engine.get_legal_actions(0)
    cover_idx = _find_action_idx(legal, "COVER")

    output = engine.apply_action(
        action_idx=cover_idx,
        cover_list={"B_NIU": 1},
        client_version=90,
    )
    next_state = _extract_state(engine, output)

    reveal = next_state.get("reveal") or {}
    turn = next_state.get("turn") or {}
    assert next_state.get("phase") == "buckle_flow"
    assert turn.get("current_seat") == 1
    assert reveal.get("buckler_seat") is None
    assert reveal.get("pending_order") == []


def test_m3_bf_10_reveal_to_in_round_resets_turn_first_hand_fields() -> None:
    """M3-BF-10: after REVEAL returns to buckler, in_round must be first-hand pre-state."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(
        _make_buckle_flow_state(
            current_seat=1,
            pending_order=[1, 2],
            buckler_seat=0,
            version=55,
        )
    )

    legal = engine.get_legal_actions(1)
    reveal_idx = _find_action_idx(legal, "REVEAL")

    output = engine.apply_action(action_idx=reveal_idx, client_version=55)
    next_state = _extract_state(engine, output)

    turn = next_state.get("turn") or {}
    assert next_state.get("phase") == "in_round"
    assert turn.get("current_seat") == 0
    assert turn.get("round_kind") == 0
    assert turn.get("plays") == []
    assert turn.get("last_combo") is None


def test_m3_bf_11_buckle_by_active_revealer_clears_active_before_pending_order() -> None:
    """M3-BF-11: BUCKLE by active revealer should clear active seat before order generation."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(
        _make_buckle_flow_state(
            current_seat=1,
            pending_order=[],
            active_revealer_seat=1,
            version=56,
        )
    )

    legal = engine.get_legal_actions(1)
    buckle_idx = _find_action_idx(legal, "BUCKLE")

    output = engine.apply_action(action_idx=buckle_idx, client_version=56)
    next_state = _extract_state(engine, output)

    reveal = next_state.get("reveal") or {}
    turn = next_state.get("turn") or {}
    assert reveal.get("active_revealer_seat") is None
    assert reveal.get("pending_order") == [2, 0]
    assert reveal.get("buckler_seat") == 1
    assert turn.get("current_seat") == 2
