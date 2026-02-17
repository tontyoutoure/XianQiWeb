"""M3-LA-13~22: legal PLAY action enumeration scenarios."""

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
    actions = legal_actions.get("actions", [])
    signatures: list[tuple[tuple[str, int], ...]] = []
    for action in actions:
        if action.get("type") == "PLAY":
            signatures.append(_cards_signature(action.get("payload_cards", [])))
    return signatures


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
            if phase == "in_round" and round_kind > 0
            else None,
            "plays": [],
        },
        "pillar_groups": [],
        "reveal": {"buckler_seat": None, "active_revealer_seat": None, "pending_order": [], "relations": []},
    }


def test_m3_la_13_buckle_play_covers_all_combo_kinds() -> None:
    engine = XianqiGameEngine()
    hand = {"R_SHI": 2, "R_GOU": 1, "B_GOU": 1, "R_NIU": 3}
    state = _make_state(
        phase="in_round",
        current_seat=0,
        hand_by_seat={0: hand},
        round_kind=0,
        last_combo_power=-1,
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(0)
    signatures = set(_play_signatures(legal_actions))

    assert (("R_SHI", 1),) in signatures
    assert (("R_SHI", 2),) in signatures
    assert (("B_GOU", 1), ("R_GOU", 1)) in signatures
    assert (("R_NIU", 3),) in signatures


def test_m3_la_14_buckle_play_matches_enumerate_combos() -> None:
    engine = XianqiGameEngine()
    hand = {"R_SHI": 2, "R_GOU": 1, "B_GOU": 1, "R_NIU": 3}
    state = _make_state(
        phase="in_round",
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


def test_m3_la_15_in_round_single_beatable_full_set() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="in_round",
        current_seat=1,
        hand_by_seat={1: {"R_SHI": 1, "B_SHI": 1, "R_XIANG": 1, "B_CHE": 1}},
        round_kind=1,
        last_combo_power=3,
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(1)

    assert set(_play_signatures(legal_actions)) == {
        (("R_SHI", 1),),
        (("B_SHI", 1),),
        (("R_XIANG", 1),),
    }


def test_m3_la_16_in_round_pair_beatable_includes_dog_pair() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="in_round",
        current_seat=1,
        hand_by_seat={
            1: {
                "R_SHI": 2,
                "B_SHI": 2,
                "R_MA": 2,
                "R_GOU": 1,
                "B_GOU": 1,
                "B_NIU": 2,
            }
        },
        round_kind=2,
        last_combo_power=4,
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(1)

    assert set(_play_signatures(legal_actions)) == {
        (("B_GOU", 1), ("R_GOU", 1)),
        (("R_SHI", 2),),
        (("B_SHI", 2),),
        (("R_MA", 2),),
    }


def test_m3_la_17_in_round_pair_strictly_greater_only() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="in_round",
        current_seat=1,
        hand_by_seat={1: {"R_SHI": 2, "B_SHI": 2, "R_MA": 2, "R_GOU": 1, "B_GOU": 1}},
        round_kind=2,
        last_combo_power=8,
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(1)
    signatures = set(_play_signatures(legal_actions))

    assert signatures == {
        (("B_GOU", 1), ("R_GOU", 1)),
        (("R_SHI", 2),),
    }
    assert (("B_SHI", 2),) not in signatures


def test_m3_la_18_in_round_triple_beatable_full_set() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="in_round",
        current_seat=1,
        hand_by_seat={1: {"R_NIU": 3, "B_NIU": 3}},
        round_kind=3,
        last_combo_power=10,
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(1)

    assert _play_signatures(legal_actions) == [(("R_NIU", 3),)]


def test_m3_la_19_in_round_play_count_matches_round_kind() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="in_round",
        current_seat=1,
        hand_by_seat={1: {"R_SHI": 2, "B_SHI": 1, "R_NIU": 3, "R_MA": 2}},
        round_kind=2,
        last_combo_power=0,
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(1)

    for signature in _play_signatures(legal_actions):
        assert sum(count for _, count in signature) == 2


def test_m3_la_20_in_round_single_no_duplicate_for_same_type() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="in_round",
        current_seat=1,
        hand_by_seat={1: {"R_SHI": 2, "B_SHI": 1}},
        round_kind=1,
        last_combo_power=0,
    )

    engine.load_state(state)
    legal_actions = engine.get_legal_actions(1)
    signatures = _play_signatures(legal_actions)

    assert signatures.count((("R_SHI", 1),)) == 1


def test_m3_la_21_buckle_play_order_stable() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="in_round",
        current_seat=0,
        hand_by_seat={0: {"R_SHI": 2, "R_GOU": 1, "B_GOU": 1, "R_NIU": 3}},
        round_kind=0,
        last_combo_power=-1,
    )

    engine.load_state(state)
    sequence_1 = _play_signatures(engine.get_legal_actions(0))
    sequence_2 = _play_signatures(engine.get_legal_actions(0))
    sequence_3 = _play_signatures(engine.get_legal_actions(0))

    assert sequence_1 == sequence_2 == sequence_3


def test_m3_la_22_in_round_play_order_stable() -> None:
    engine = XianqiGameEngine()
    state = _make_state(
        phase="in_round",
        current_seat=1,
        hand_by_seat={
            1: {
                "R_SHI": 2,
                "B_SHI": 2,
                "R_MA": 2,
                "R_GOU": 1,
                "B_GOU": 1,
                "B_NIU": 2,
            }
        },
        round_kind=2,
        last_combo_power=4,
    )

    engine.load_state(state)
    sequence_1 = _play_signatures(engine.get_legal_actions(1))
    sequence_2 = _play_signatures(engine.get_legal_actions(1))
    sequence_3 = _play_signatures(engine.get_legal_actions(1))

    assert sequence_1 == sequence_2 == sequence_3
