"""M3 Red tests: M3-ACT-08~10 pillar generation and ownership."""

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


def _make_state(
    *,
    round_kind: int,
    decision_seat: int,
    owner_seat: int,
    last_combo_cards: list[dict[str, int]],
    last_combo_power: int,
    hand_by_seat: dict[int, dict[str, int]],
    plays: list[dict[str, Any]],
    version: int = 42,
) -> dict[str, Any]:
    return {
        "version": version,
        "phase": "in_round",
        "players": [
            {"seat": 0, "hand": hand_by_seat.get(0, {})},
            {"seat": 1, "hand": hand_by_seat.get(1, {})},
            {"seat": 2, "hand": hand_by_seat.get(2, {})},
        ],
        "turn": {
            "current_seat": decision_seat,
            "round_index": 3,
            "round_kind": round_kind,
            "last_combo": {
                "power": last_combo_power,
                "cards": last_combo_cards,
                "owner_seat": owner_seat,
            },
            "plays": plays,
        },
        "decision": {
            "seat": decision_seat,
            "context": "in_round",
            "started_at_ms": 0,
            "timeout_at_ms": None,
        },
        "pillar_groups": [],
        "reveal": {"buckler_seat": 0, "pending_order": [], "relations": []},
    }


def test_m3_act_08_round_end_pillar_group_owned_by_winner() -> None:
    """M3-ACT-08: finishing a round should append pillar group with correct owner."""

    Engine = _load_engine_class()
    engine = Engine()

    state = _make_state(
        round_kind=1,
        decision_seat=2,
        owner_seat=1,
        last_combo_cards=[{"type": "R_XIANG", "count": 1}],
        last_combo_power=7,
        hand_by_seat={0: {}, 1: {}, 2: {"B_NIU": 1}},
        plays=[
            {"seat": 1, "power": 7, "cards": [{"type": "R_XIANG", "count": 1}]},
            {"seat": 0, "power": -1, "cards": [{"type": "B_CHE", "count": 1}]},
        ],
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(2)
    cover_idx = _find_action_idx(legal_actions, "COVER")

    output = engine.apply_action(
        action_idx=cover_idx,
        cover_list=[{"type": "B_NIU", "count": 1}],
        client_version=42,
    )
    next_state = _extract_state(engine, output)

    groups = next_state.get("pillar_groups", [])
    assert len(groups) == 1
    group = groups[-1]
    assert group.get("winner_seat") == 1
    assert group.get("round_kind") == 1
    assert len(group.get("plays", [])) == 3


def test_m3_act_09_pair_round_split_same_pair_into_two_pillars() -> None:
    """M3-ACT-09: pair round should split same pair cards across different pillars."""

    Engine = _load_engine_class()
    engine = Engine()

    state = _make_state(
        round_kind=2,
        decision_seat=2,
        owner_seat=1,
        last_combo_cards=[{"type": "R_SHI", "count": 2}],
        last_combo_power=19,
        hand_by_seat={0: {}, 1: {}, 2: {"B_NIU": 2}},
        plays=[
            {"seat": 1, "power": 19, "cards": [{"type": "R_SHI", "count": 2}]},
            {"seat": 0, "power": -1, "cards": [{"type": "B_CHE", "count": 2}]},
        ],
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(2)
    cover_idx = _find_action_idx(legal_actions, "COVER")

    output = engine.apply_action(
        action_idx=cover_idx,
        cover_list=[{"type": "B_NIU", "count": 2}],
        client_version=42,
    )
    next_state = _extract_state(engine, output)

    groups = next_state.get("pillar_groups", [])
    assert len(groups) == 1
    group = groups[-1]
    assert group.get("winner_seat") == 1
    assert group.get("round_kind") == 2

    pillars = group.get("pillars")
    assert isinstance(pillars, list)
    assert len(pillars) == 2

    r_shi_distribution = []
    for pillar in pillars:
        cards = pillar.get("cards", [])
        r_shi_count = sum(int(card.get("count", 0)) for card in cards if card.get("type") == "R_SHI")
        r_shi_distribution.append(r_shi_count)

    assert sorted(r_shi_distribution) == [1, 1]


def test_m3_act_10_triple_round_split_same_triple_into_three_pillars() -> None:
    """M3-ACT-10: triple round should split same triple cards across three pillars."""

    Engine = _load_engine_class()
    engine = Engine()

    state = _make_state(
        round_kind=3,
        decision_seat=1,
        owner_seat=2,
        last_combo_cards=[{"type": "R_NIU", "count": 3}],
        last_combo_power=11,
        hand_by_seat={0: {}, 1: {"B_NIU": 3}, 2: {}},
        plays=[
            {"seat": 2, "power": 11, "cards": [{"type": "R_NIU", "count": 3}]},
            {"seat": 0, "power": -1, "cards": [{"type": "B_CHE", "count": 3}]},
        ],
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(1)
    cover_idx = _find_action_idx(legal_actions, "COVER")

    output = engine.apply_action(
        action_idx=cover_idx,
        cover_list=[{"type": "B_NIU", "count": 3}],
        client_version=42,
    )
    next_state = _extract_state(engine, output)

    groups = next_state.get("pillar_groups", [])
    assert len(groups) == 1
    group = groups[-1]
    assert group.get("winner_seat") == 2
    assert group.get("round_kind") == 3

    pillars = group.get("pillars")
    assert isinstance(pillars, list)
    assert len(pillars) == 3

    r_niu_distribution = []
    for pillar in pillars:
        cards = pillar.get("cards", [])
        r_niu_count = sum(int(card.get("count", 0)) for card in cards if card.get("type") == "R_NIU")
        r_niu_distribution.append(r_niu_count)

    assert sorted(r_niu_distribution) == [1, 1, 1]
