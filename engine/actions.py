"""Legal-action generation helpers for engine state."""

from __future__ import annotations

from typing import Any

from engine.combos import enumerate_combos


def get_legal_actions(state: dict[str, Any] | None, seat: int) -> dict[str, Any]:
    """Return legal actions for seat by current phase and turn.current_seat."""

    if state is None:
        return {"seat": seat, "actions": []}

    phase = state.get("phase")

    turn = state.get("turn") or {}
    current_seat = turn.get("current_seat")
    if current_seat is None or int(current_seat) != int(seat):
        return {"seat": seat, "actions": []}

    if phase == "settlement":
        return {"seat": seat, "actions": []}

    if phase == "buckle_flow":
        reveal = state.get("reveal") or {}
        pending_raw = reveal.get("pending_order") or []
        pending_order = [int(pending_seat) for pending_seat in pending_raw]
        if pending_order:
            if int(pending_order[0]) != int(seat):
                return {"seat": seat, "actions": []}
            return {
                "seat": seat,
                "actions": [
                    {"type": "REVEAL"},
                    {"type": "PASS_REVEAL"},
                ],
            }
        return {
            "seat": seat,
            "actions": [
                {"type": "BUCKLE"},
                {"type": "PASS_BUCKLE"},
            ],
        }

    raw_hand = state["players"][int(seat)]["hand"]
    hand = {str(card_type): int(count) for card_type, count in raw_hand.items()}

    if phase == "in_round":
        turn = state.get("turn") or {}
        round_kind = int(turn.get("round_kind", 0))
        if round_kind == 0:
            return {
                "seat": seat,
                "actions": [
                    {"type": "PLAY", "payload_cards": combo["cards"], "power": int(combo["power"])}
                    for combo in enumerate_combos(hand)
                ],
            }

        last_combo = turn.get("last_combo") or {}
        last_power = int(last_combo.get("power", -1))

        combos = enumerate_combos(hand, round_kind=round_kind)
        beatable = [combo for combo in combos if int(combo["power"]) > last_power]

        if beatable:
            return {
                "seat": seat,
                "actions": [
                    {
                        "type": "PLAY",
                        "payload_cards": combo["cards"],
                        "power": int(combo["power"]),
                    }
                    for combo in beatable
                ],
            }

        return {
            "seat": seat,
            "actions": [{"type": "COVER", "required_count": round_kind}],
        }

    return {"seat": seat, "actions": []}
