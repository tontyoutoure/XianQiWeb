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
    cards = combo.get("cards", [])
    return sum(int(card.get("count", 0)) for card in cards)


def _combo_signature(combo: dict[str, Any]) -> tuple[tuple[str, int], ...]:
    cards = combo.get("cards", [])
    return tuple(sorted((str(card["type"]), int(card["count"])) for card in cards))


def _single_combos(hand: dict[str, int]) -> list[dict[str, Any]]:
    combos: list[dict[str, Any]] = []
    for card_type in sorted(hand):
        combos.append(
            {
                "kind": 1,
                "power": CARD_POWER[card_type],
                "cards": [{"type": card_type, "count": 1}],
            }
        )
    return combos


def _pair_power(card_type: str) -> int:
    if card_type == "R_SHI":
        return 19
    if card_type == "B_SHI":
        return 18
    return CARD_POWER[card_type]


def _pair_combos(hand: dict[str, int]) -> list[dict[str, Any]]:
    combos: list[dict[str, Any]] = []
    for card_type in sorted(hand):
        if hand[card_type] >= 2:
            combos.append(
                {
                    "kind": 2,
                    "power": _pair_power(card_type),
                    "cards": [{"type": card_type, "count": 2}],
                }
            )

    if hand.get("R_GOU", 0) >= 1 and hand.get("B_GOU", 0) >= 1:
        combos.append(
            {
                "kind": 2,
                "power": 19,
                "cards": [
                    {"type": "R_GOU", "count": 1},
                    {"type": "B_GOU", "count": 1},
                ],
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
                "cards": [{"type": "R_NIU", "count": 3}],
            }
        )
    if hand.get("B_NIU", 0) >= 3:
        combos.append(
            {
                "kind": 3,
                "power": 10,
                "cards": [{"type": "B_NIU", "count": 3}],
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
