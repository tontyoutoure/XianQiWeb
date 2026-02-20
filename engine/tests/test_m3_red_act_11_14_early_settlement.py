"""M3 Red tests: M3-ACT-11~14 early settlement after round finish."""

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


def _make_previous_pillar_groups(pillar_counts: tuple[int, int, int]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    round_index = 0
    for seat, count in enumerate(pillar_counts):
        for _ in range(count):
            groups.append(
                {
                    "round_index": round_index,
                    "winner_seat": seat,
                    "round_kind": 1,
                    "plays": [],
                }
            )
            round_index += 1
    return groups


def _make_round_end_state(
    *,
    owner_seat: int,
    version: int,
    pillar_counts_before: tuple[int, int, int],
    reveal_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reveal = {
        "buckler_seat": None,
        "active_revealer_seat": None,
        "pending_order": [],
        "relations": [],
    }
    if reveal_override:
        reveal.update(reveal_override)
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
            "round_index": 20,
            "round_kind": 1,
            "last_combo": {
                "power": 9,
                "cards": {"R_SHI": 1},
                "owner_seat": owner_seat,
            },
            "plays": [
                {"seat": owner_seat, "power": 9, "cards": {"R_SHI": 1}},
                {"seat": (owner_seat + 1) % 3, "power": -1, "cards": {"B_CHE": 1}},
            ],
        },
        "pillar_groups": _make_previous_pillar_groups(pillar_counts_before),
        "reveal": reveal,
    }


def test_m3_act_11_round_end_enters_settlement_when_any_player_reaches_ceramic() -> None:
    """M3-ACT-11: any seat reaching ceramic (>=6) should end game immediately."""

    Engine = _load_engine_class()
    engine = Engine()
    state = _make_round_end_state(owner_seat=0, version=111, pillar_counts_before=(5, 0, 0))
    engine.load_state(state)

    cover_idx = _find_action_idx(engine.get_legal_actions(0), "COVER")
    output = engine.apply_action(
        action_idx=cover_idx,
        cover_list={"B_NIU": 1},
        client_version=111,
    )
    next_state = _extract_state(engine, output)

    assert next_state.get("phase") == "settlement"


def test_m3_act_12_round_end_enters_settlement_when_two_players_are_enough() -> None:
    """M3-ACT-12: when two seats are enough (>=3), game should enter settlement."""

    Engine = _load_engine_class()
    engine = Engine()
    state = _make_round_end_state(owner_seat=0, version=112, pillar_counts_before=(2, 3, 0))
    engine.load_state(state)

    cover_idx = _find_action_idx(engine.get_legal_actions(0), "COVER")
    output = engine.apply_action(
        action_idx=cover_idx,
        cover_list={"B_NIU": 1},
        client_version=112,
    )
    next_state = _extract_state(engine, output)

    assert next_state.get("phase") == "settlement"


def test_m3_act_13_round_end_keeps_buckle_flow_when_early_settlement_not_hit() -> None:
    """M3-ACT-13: with only one enough and no ceramic, next phase stays buckle_flow."""

    Engine = _load_engine_class()
    engine = Engine()
    state = _make_round_end_state(owner_seat=0, version=113, pillar_counts_before=(2, 2, 1))
    engine.load_state(state)

    cover_idx = _find_action_idx(engine.get_legal_actions(0), "COVER")
    output = engine.apply_action(
        action_idx=cover_idx,
        cover_list={"B_NIU": 1},
        client_version=113,
    )
    next_state = _extract_state(engine, output)

    assert next_state.get("phase") == "buckle_flow"
    assert next_state.get("turn", {}).get("current_seat") == 0


def test_m3_act_14_early_settlement_cleans_reveal_pending_and_blocks_actions() -> None:
    """M3-ACT-14: early settlement should clear reveal pending order and legal actions."""

    Engine = _load_engine_class()
    engine = Engine()
    state = _make_round_end_state(
        owner_seat=0,
        version=114,
        pillar_counts_before=(5, 0, 0),
        reveal_override={"buckler_seat": 2, "pending_order": [1, 0], "active_revealer_seat": 1},
    )
    engine.load_state(state)

    cover_idx = _find_action_idx(engine.get_legal_actions(0), "COVER")
    output = engine.apply_action(
        action_idx=cover_idx,
        cover_list={"B_NIU": 1},
        client_version=114,
    )
    next_state = _extract_state(engine, output)
    reveal = next_state.get("reveal", {})

    assert next_state.get("phase") == "settlement"
    assert reveal.get("pending_order") == []
    assert reveal.get("buckler_seat") is None
    current_seat = int(next_state.get("turn", {}).get("current_seat", 0))
    legal_actions = engine.get_legal_actions(current_seat)
    assert legal_actions.get("actions") == []
