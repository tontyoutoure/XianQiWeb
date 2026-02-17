"""Settlement entrypoint for the engine."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _get_pillar_counts(state: dict[str, Any]) -> list[int]:
    counts = [0, 0, 0]
    for group in state.get("pillar_groups", []):
        if not isinstance(group, dict):
            continue
        winner_seat = int(group.get("winner_seat", -1))
        if 0 <= winner_seat <= 2:
            counts[winner_seat] += 1
    return counts


def _has_enough_reveal_flag(relations: list[dict[str, Any]], seat: int) -> bool:
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        if int(relation.get("revealer_seat", -1)) != seat:
            continue
        if bool(relation.get("revealer_enough_at_time", False)):
            return True
    return False


def settle_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Settle the current game state and return state + settlement payload."""

    if state is None:
        raise RuntimeError("engine state is not initialized")

    if state.get("phase") != "settlement":
        raise ValueError("ENGINE_INVALID_PHASE")

    pillar_counts = _get_pillar_counts(state)
    reveal = state.get("reveal", {})
    relations = reveal.get("relations", []) if isinstance(reveal, dict) else []
    if not isinstance(relations, list):
        relations = []

    is_enough = [3 <= count < 6 for count in pillar_counts]
    is_ceramic = [count >= 6 for count in pillar_counts]
    is_not_enough = [count < 3 for count in pillar_counts]

    enough_receivers: set[int] = set()
    for seat in (0, 1, 2):
        if not is_enough[seat]:
            continue
        already_enough_revealer = _has_enough_reveal_flag(relations, seat)
        if already_enough_revealer and not is_ceramic[seat]:
            continue
        enough_receivers.add(seat)

    ceramic_receivers = {seat for seat in (0, 1, 2) if is_ceramic[seat]}

    delta_enough = [0, 0, 0]
    delta_reveal = [0, 0, 0]
    delta_ceramic = [0, 0, 0]

    for payer_seat in (0, 1, 2):
        if not is_not_enough[payer_seat]:
            continue
        for receiver_seat in enough_receivers:
            delta_enough[payer_seat] -= 1
            delta_enough[receiver_seat] += 1
        for receiver_seat in ceramic_receivers:
            delta_ceramic[payer_seat] -= 3
            delta_ceramic[receiver_seat] += 3

    for relation in relations:
        if not isinstance(relation, dict):
            continue
        revealer_seat = int(relation.get("revealer_seat", -1))
        buckler_seat = int(relation.get("buckler_seat", -1))
        if revealer_seat not in (0, 1, 2) or buckler_seat not in (0, 1, 2):
            continue
        revealer_enough_at_time = bool(relation.get("revealer_enough_at_time", False))
        if revealer_enough_at_time:
            continue
        if not is_not_enough[revealer_seat]:
            continue

        delta_reveal[revealer_seat] -= 1
        delta_reveal[buckler_seat] += 1

    chip_delta_by_seat: list[dict[str, int]] = []
    for seat in (0, 1, 2):
        seat_delta_enough = delta_enough[seat]
        seat_delta_reveal = delta_reveal[seat]
        seat_delta_ceramic = delta_ceramic[seat]
        chip_delta_by_seat.append(
            {
                "seat": seat,
                "delta": seat_delta_enough + seat_delta_reveal + seat_delta_ceramic,
                "delta_enough": seat_delta_enough,
                "delta_reveal": seat_delta_reveal,
                "delta_ceramic": seat_delta_ceramic,
            }
        )

    final_state = deepcopy(state)
    final_state["phase"] = "finished"
    final_state["version"] = int(final_state.get("version", 0)) + 1

    return {
        "new_state": final_state,
        "settlement": {
            "final_state": deepcopy(final_state),
            "chip_delta_by_seat": chip_delta_by_seat,
        },
    }
