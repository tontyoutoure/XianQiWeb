"""M3 Red tests: M3-CB-01~04 + M3-LA-04~06.

These tests intentionally codify the expected interfaces/behavior before
engine implementation is completed.
"""

from __future__ import annotations

from typing import Any
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_enumerate_combos():
    try:
        from engine.combos import enumerate_combos  # type: ignore
    except ModuleNotFoundError as exc:
        pytest.fail(f"M3-CB: missing module/function: {exc}")
    return enumerate_combos


def _combo_cards_signature(combo: dict[str, Any]) -> tuple[tuple[str, int], ...]:
    cards = combo.get("cards")
    if not isinstance(cards, list):
        pytest.fail(f"combo must contain list cards, got: {combo}")
    pairs: list[tuple[str, int]] = []
    for card in cards:
        if not isinstance(card, dict) or "type" not in card or "count" not in card:
            pytest.fail(f"invalid card entry in combo: {combo}")
        pairs.append((card["type"], card["count"]))
    return tuple(sorted(pairs))


def _extract_actions_types(legal_actions: dict[str, Any]) -> list[str]:
    actions = legal_actions.get("actions")
    if not isinstance(actions, list):
        pytest.fail(f"legal_actions.actions must be a list, got: {legal_actions}")
    types: list[str] = []
    for action in actions:
        action_type = action.get("type")
        if not isinstance(action_type, str):
            pytest.fail(f"action.type must be str, got: {action}")
        types.append(action_type)
    return types


def _load_engine_instance():
    try:
        from engine.core import XianqiGameEngine  # type: ignore
    except ModuleNotFoundError as exc:
        pytest.fail(f"M3-LA: missing module/class: {exc}")
    return XianqiGameEngine()


def _make_in_round_state(
    *,
    current_seat: int,
    round_kind: int,
    last_combo_power: int,
    hand_by_seat: dict[int, dict[str, int]],
) -> dict[str, Any]:
    return {
        "version": 12,
        "phase": "in_round",
        "players": [
            {"seat": 0, "hand": hand_by_seat.get(0, {})},
            {"seat": 1, "hand": hand_by_seat.get(1, {})},
            {"seat": 2, "hand": hand_by_seat.get(2, {})},
        ],
        "turn": {
            "current_seat": current_seat,
            "round_index": 0,
            "round_kind": round_kind,
            "last_combo": {
                "power": last_combo_power,
                "cards": [{"type": "B_CHE", "count": round_kind}],
                "owner_seat": (current_seat + 1) % 3,
            },
            "plays": [
                {
                    "seat": (current_seat + 1) % 3,
                    "power": last_combo_power,
                    "cards": [{"type": "B_CHE", "count": round_kind}],
                }
            ],
        },
        "decision": {
            "seat": current_seat,
            "context": "in_round",
            "started_at_ms": 0,
            "timeout_at_ms": None,
        },
        "pillar_groups": [],
        "reveal": {"buckler_seat": 0, "pending_order": [], "relations": []},
    }


def test_m3_cb_01_single_enumeration_dedup() -> None:
    """M3-CB-01: singles are deduped, and pair is generated when available."""

    enumerate_combos = _load_enumerate_combos()
    hand = {"R_SHI": 2, "B_NIU": 1}

    combos = enumerate_combos(hand)
    signatures = {_combo_cards_signature(combo) for combo in combos}

    assert (("R_SHI", 1),) in signatures
    assert (("B_NIU", 1),) in signatures
    assert (("R_SHI", 2),) in signatures


def test_m3_cb_02_same_type_pair_enumeration() -> None:
    """M3-CB-02: pair should only exist when count >= 2."""

    enumerate_combos = _load_enumerate_combos()
    hand = {"R_SHI": 1, "R_MA": 2, "B_NIU": 1}

    combos = enumerate_combos(hand, round_kind=2)
    signatures = {_combo_cards_signature(combo) for combo in combos}

    assert (("R_MA", 2),) in signatures
    assert (("R_SHI", 2),) not in signatures
    assert (("B_NIU", 2),) not in signatures


def test_m3_cb_03_dog_pair_enumeration() -> None:
    """M3-CB-03: dog_pair exists iff both R_GOU and B_GOU are present."""

    enumerate_combos = _load_enumerate_combos()

    combos_yes = enumerate_combos({"R_GOU": 1, "B_GOU": 1}, round_kind=2)
    signatures_yes = {_combo_cards_signature(combo) for combo in combos_yes}
    assert (("B_GOU", 1), ("R_GOU", 1)) in signatures_yes

    combos_no = enumerate_combos({"R_GOU": 1, "B_GOU": 0}, round_kind=2)
    signatures_no = {_combo_cards_signature(combo) for combo in combos_no}
    assert (("B_GOU", 1), ("R_GOU", 1)) not in signatures_no


def test_m3_cb_04_dog_pair_no_duplicate() -> None:
    """M3-CB-04: dog_pair appears only once in results."""

    enumerate_combos = _load_enumerate_combos()
    hand = {"R_GOU": 1, "B_GOU": 1}

    combos = enumerate_combos(hand, round_kind=2)
    signatures = [_combo_cards_signature(combo) for combo in combos]

    assert signatures.count((("B_GOU", 1), ("R_GOU", 1))) == 1


def test_m3_la_04_in_round_must_not_offer_cover_when_can_beat() -> None:
    """M3-LA-04: if beatable, actions must contain PLAY only."""

    engine = _load_engine_instance()
    state = _make_in_round_state(
        current_seat=1,
        round_kind=1,
        last_combo_power=2,
        hand_by_seat={
            0: {"B_NIU": 1},
            1: {"R_SHI": 1},
            2: {"R_NIU": 1},
        },
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(1)
    action_types = _extract_actions_types(legal_actions)

    assert "PLAY" in action_types
    assert "COVER" not in action_types


def test_m3_la_05_in_round_only_cover_when_cannot_beat() -> None:
    """M3-LA-05: if cannot beat, actions must contain only one COVER."""

    engine = _load_engine_instance()
    state = _make_in_round_state(
        current_seat=1,
        round_kind=1,
        last_combo_power=9,
        hand_by_seat={
            0: {"R_SHI": 1},
            1: {"B_NIU": 1},
            2: {"R_NIU": 1},
        },
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(1)
    actions = legal_actions.get("actions", [])
    action_types = _extract_actions_types(legal_actions)

    assert action_types == ["COVER"]
    assert len(actions) == 1


def test_m3_la_06_cover_required_count_equals_round_kind() -> None:
    """M3-LA-06: COVER.required_count must equal current round_kind."""

    engine = _load_engine_instance()
    state = _make_in_round_state(
        current_seat=1,
        round_kind=2,
        last_combo_power=999,
        hand_by_seat={
            0: {"R_SHI": 2},
            1: {"R_NIU": 1, "B_NIU": 1},
            2: {"B_SHI": 2},
        },
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(1)
    actions = legal_actions.get("actions", [])

    assert len(actions) == 1
    assert actions[0]["type"] == "COVER"
    assert actions[0]["required_count"] == 2
