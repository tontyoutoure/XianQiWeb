"""M3 Red tests: M3-LA-01~03 and M3-LA-07~12."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.combos import enumerate_combos
from engine.core import XianqiGameEngine


def _cards_signature(cards: list[dict[str, Any]]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((str(card["type"]), int(card["count"])) for card in cards))


def _play_signatures(legal_actions: dict[str, Any]) -> list[tuple[tuple[str, int], ...]]:
    signatures: list[tuple[tuple[str, int], ...]] = []
    for action in legal_actions.get("actions", []):
        if action.get("type") == "PLAY":
            signatures.append(_cards_signature(action.get("payload_cards", [])))
    return signatures


def _action_sequence(legal_actions: dict[str, Any]) -> list[tuple[str, tuple[tuple[str, int], ...], int, int]]:
    sequence: list[tuple[str, tuple[tuple[str, int], ...], int, int]] = []
    for action in legal_actions.get("actions", []):
        action_type = str(action.get("type", ""))
        payload = _cards_signature(action.get("payload_cards", [])) if action_type == "PLAY" else ()
        power = int(action.get("power", -999)) if action_type == "PLAY" else -999
        required_count = int(action.get("required_count", -1)) if action_type == "COVER" else -1
        sequence.append((action_type, payload, power, required_count))
    return sequence


def _make_state(
    *,
    phase: str,
    current_seat: int,
    hand_by_seat: dict[int, dict[str, int]],
    round_kind: int,
    last_combo_power: int,
) -> dict[str, Any]:
    return {
        "version": 1,
        "phase": phase,
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
                "cards": [{"type": "B_CHE", "count": max(round_kind, 1)}],
                "owner_seat": (current_seat + 1) % 3,
            }
            if phase == "in_round"
            else None,
            "plays": [],
        },
        "pillar_groups": [],
        "reveal": {"buckler_seat": 0, "pending_order": [], "relations": []},
    }


def test_m3_la_01_buckle_actions_only_play_plus_single_buckle() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="buckle_decision",
        current_seat=0,
        hand_by_seat={0: {"R_SHI": 2, "R_GOU": 1, "B_GOU": 1}},
        round_kind=0,
        last_combo_power=-1,
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(0)
    actions = legal_actions.get("actions", [])
    types = [action.get("type") for action in actions]

    assert actions
    assert set(types).issubset({"PLAY", "BUCKLE"})
    assert types.count("BUCKLE") <= 1


def test_m3_la_02_buckle_play_completeness_matches_combos() -> None:
    engine = XianqiGameEngine()
    hand = {"R_SHI": 2, "R_GOU": 1, "B_GOU": 1}
    state = _make_state(
        phase="buckle_decision",
        current_seat=0,
        hand_by_seat={0: hand},
        round_kind=0,
        last_combo_power=-1,
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(0)

    actual = sorted(_play_signatures(legal_actions))
    expected = sorted(_cards_signature(combo["cards"]) for combo in enumerate_combos(hand))
    assert actual == expected


def test_m3_la_03_buckle_action_order_stable() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="buckle_decision",
        current_seat=0,
        hand_by_seat={0: {"R_SHI": 2, "R_GOU": 1, "B_GOU": 1}},
        round_kind=0,
        last_combo_power=-1,
    )

    engine.load_state(state)
    seq_1 = _action_sequence(engine.get_legal_actions(0))
    seq_2 = _action_sequence(engine.get_legal_actions(0))
    seq_3 = _action_sequence(engine.get_legal_actions(0))

    assert seq_1 == seq_2 == seq_3


def test_m3_la_07_in_round_beatable_set_is_exact_and_valid() -> None:
    engine = XianqiGameEngine()
    hand = {"R_SHI": 2, "R_MA": 2, "B_NIU": 2}
    state = _make_state(
        phase="in_round",
        current_seat=1,
        hand_by_seat={1: hand},
        round_kind=2,
        last_combo_power=6,
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(1)
    actions = legal_actions.get("actions", [])

    assert actions
    assert all(action.get("type") == "PLAY" for action in actions)

    actual = sorted(_play_signatures(legal_actions))
    expected = sorted(
        _cards_signature(combo["cards"]) for combo in enumerate_combos(hand, round_kind=2) if int(combo["power"]) > 6
    )
    assert actual == expected


def test_m3_la_08_non_current_seat_has_empty_actions() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="in_round",
        current_seat=1,
        hand_by_seat={1: {"R_SHI": 1}},
        round_kind=1,
        last_combo_power=0,
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(0)

    assert legal_actions == {"seat": 0, "actions": []}


def test_m3_la_09_reveal_decision_only_reveal_and_pass() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="reveal_decision",
        current_seat=2,
        hand_by_seat={2: {"R_SHI": 1}},
        round_kind=0,
        last_combo_power=-1,
    )
    state["turn"] = {
        "current_seat": 2,
        "round_index": 3,
        "round_kind": 0,
        "last_combo": None,
        "plays": [],
    }
    state["reveal"] = {"buckler_seat": 0, "pending_order": [2, 1], "relations": []}

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(2)
    types = [action.get("type") for action in legal_actions.get("actions", [])]

    assert types == ["REVEAL", "PASS_REVEAL"]


def test_m3_la_10_settlement_and_finished_have_no_actions() -> None:
    engine = XianqiGameEngine()

    settlement_state = _make_state(
        phase="settlement",
        current_seat=0,
        hand_by_seat={0: {"R_SHI": 1}},
        round_kind=0,
        last_combo_power=-1,
    )
    settlement_state["turn"] = {
        "current_seat": 0,
        "round_index": 0,
        "round_kind": 0,
        "last_combo": None,
        "plays": [],
    }

    finished_state = _make_state(
        phase="finished",
        current_seat=0,
        hand_by_seat={0: {"R_SHI": 1}},
        round_kind=0,
        last_combo_power=-1,
    )
    finished_state["turn"] = {
        "current_seat": 0,
        "round_index": 0,
        "round_kind": 0,
        "last_combo": None,
        "plays": [],
    }

    engine.load_state(settlement_state)
    assert engine.get_legal_actions(0) == {"seat": 0, "actions": []}

    engine.load_state(finished_state)
    assert engine.get_legal_actions(0) == {"seat": 0, "actions": []}


def test_m3_la_11_action_index_meaning_is_stable_on_same_state() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="in_round",
        current_seat=1,
        hand_by_seat={1: {"R_SHI": 1, "B_SHI": 1, "R_XIANG": 1, "B_CHE": 1}},
        round_kind=1,
        last_combo_power=3,
    )

    engine.load_state(state)
    seq_1 = _action_sequence(engine.get_legal_actions(1))
    seq_2 = _action_sequence(engine.get_legal_actions(1))
    seq_3 = _action_sequence(engine.get_legal_actions(1))

    assert seq_1 == seq_2 == seq_3


def test_m3_la_12_actions_refresh_after_phase_switch() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="buckle_decision",
        current_seat=0,
        hand_by_seat={0: {"R_SHI": 1}, 1: {"B_NIU": 1}, 2: {"R_NIU": 1}},
        round_kind=0,
        last_combo_power=-1,
    )

    engine.load_state(state)
    out = engine.apply_action(action_idx=0, client_version=1)
    next_state = out["new_state"]
    next_seat = int((next_state.get("turn") or {}).get("current_seat", -1))

    assert next_state.get("phase") == "in_round"
    assert next_seat == 1
    assert engine.get_legal_actions(1).get("actions")
    assert engine.get_legal_actions(0) == {"seat": 0, "actions": []}
    assert engine.get_legal_actions(2) == {"seat": 2, "actions": []}
