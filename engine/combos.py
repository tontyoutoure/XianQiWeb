"""Combo enumeration and strength helpers for the Xianqi engine."""

from __future__ import annotations

from typing import Any

CARD_POWER: dict[str, int] = {
    "R_SHI": 9,
    "B_SHI": 8,
    "R_XIANG": 7,
    "B_XIANG": 6,
    "R_MA": 5,
    "B_MA": 4,
    "R_CHE": 3,
    "B_CHE": 2,
    "R_GOU": 3,
    "B_GOU": 2,
    "R_NIU": 1,
    "B_NIU": 0,
}


def _positive_hand(hand: dict[str, int]) -> dict[str, int]:
    return {card_type: count for card_type, count in hand.items() if count > 0}


def _combo_kind(combo: dict[str, Any]) -> int:
    cards = combo.get("cards", {})
    if not isinstance(cards, dict):
        return 0
    return sum(int(count) for count in cards.values())


def _combo_signature(combo: dict[str, Any]) -> tuple[tuple[str, int], ...]:
    cards = combo.get("cards", {})
    if not isinstance(cards, dict):
        return ()
    return tuple(sorted((str(card_type), int(count)) for card_type, count in cards.items()))


def _single_combos(hand: dict[str, int]) -> list[dict[str, Any]]:
    combos: list[dict[str, Any]] = []
    for card_type in sorted(hand):
        combos.append(
            {
                "kind": 1,
                "power": CARD_POWER[card_type],
                "cards": {card_type: 1},
            }
        )
    return combos


def _pair_combos(hand: dict[str, int]) -> list[dict[str, Any]]:
    combos: list[dict[str, Any]] = []
    for card_type in sorted(hand):
        if hand[card_type] >= 2:
            combos.append(
                {
                    "kind": 2,
                    "power": CARD_POWER[card_type],
                    "cards": {card_type: 2},
                }
            )

    if hand.get("R_GOU", 0) >= 1 and hand.get("B_GOU", 0) >= 1:
        combos.append(
            {
                "kind": 2,
                "power": CARD_POWER["R_SHI"],
                "cards": {"R_GOU": 1, "B_GOU": 1},
            }
        )
    return combos


def _triple_combos(hand: dict[str, int]) -> list[dict[str, Any]]:
    combos: list[dict[str, Any]] = []
    if hand.get("R_NIU", 0) >= 3:
        combos.append(
            {
                "kind": 3,
                "power": 11,
                "cards": {"R_NIU": 3},
            }
        )
    if hand.get("B_NIU", 0) >= 3:
        combos.append(
            {
                "kind": 3,
                "power": 10,
                "cards": {"B_NIU": 3},
            }
        )
    return combos


def enumerate_combos(
    hand: dict[str, int],
    round_kind: int | None = None,
) -> list[dict[str, Any]]:
    """Enumerate legal play combos from a hand in deterministic order."""

    normalized = _positive_hand(hand)
    combos = _single_combos(normalized) + _pair_combos(normalized) + _triple_combos(normalized)

    if round_kind is not None:
        combos = [combo for combo in combos if _combo_kind(combo) == round_kind]

    combos.sort(key=lambda combo: (_combo_kind(combo), -int(combo["power"]), _combo_signature(combo)))
    return combos
