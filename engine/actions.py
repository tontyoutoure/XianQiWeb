"""Legal-action generation helpers for engine state."""

from __future__ import annotations

from typing import Any

from engine.combos import enumerate_combos


def get_legal_actions(state: dict[str, Any] | None, seat: int) -> dict[str, Any]:
    """Return legal actions for seat by current phase and decision owner."""

    if state is None:
        return {"seat": seat, "actions": []}

    phase = state.get("phase")

    decision = state.get("decision") or {}
    decision_seat = decision.get("seat")
    if decision_seat is None or int(decision_seat) != int(seat):
        return {"seat": seat, "actions": []}

    if phase in {"settlement", "finished"}:
        return {"seat": seat, "actions": []}

    if phase == "reveal_decision":
        return {
            "seat": seat,
            "actions": [
                {"type": "REVEAL"},
                {"type": "PASS_REVEAL"},
            ],
        }

    raw_hand = state["players"][int(seat)]["hand"]
    hand = {str(card_type): int(count) for card_type, count in raw_hand.items()}

    if phase == "buckle_decision":
        actions = [
            {"type": "PLAY", "payload_cards": combo["cards"], "power": int(combo["power"])}
            for combo in enumerate_combos(hand)
        ]
        actions.append({"type": "BUCKLE"})
        return {"seat": seat, "actions": actions}

    if phase == "in_round":
        turn = state.get("turn") or {}
        round_kind = int(turn.get("round_kind", 0))
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
