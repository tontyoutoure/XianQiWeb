"""Core game engine shell used by M3 tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from engine.combos import enumerate_combos


class XianqiGameEngine:
    """Stateful game engine facade.

    Current M3 scope focuses on state loading and legal action enumeration.
    """

    def __init__(self) -> None:
        self._state: dict[str, Any] | None = None

    def load_state(self, state: dict[str, Any]) -> None:
        self._state = deepcopy(state)

    def dump_state(self) -> dict[str, Any]:
        if self._state is None:
            return {}
        return deepcopy(self._state)

    def _require_state(self) -> dict[str, Any]:
        if self._state is None:
            raise RuntimeError("engine state is not initialized")
        return self._state

    def _seat_hand(self, seat: int) -> dict[str, int]:
        state = self._require_state()
        players = state.get("players", [])
        for player in players:
            if int(player.get("seat", -1)) == seat:
                hand = player.get("hand", {})
                if isinstance(hand, dict):
                    return {str(card_type): int(count) for card_type, count in hand.items()}
        return {}

    def get_legal_actions(self, seat: int) -> dict[str, Any]:
        state = self._require_state()
        phase = state.get("phase")

        decision = state.get("decision") or {}
        decision_seat = decision.get("seat")
        if decision_seat != seat:
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

        hand = self._seat_hand(seat)

        if phase == "buckle_decision":
            actions = [
                {"type": "PLAY", "payload_cards": combo["cards"]}
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
                        {"type": "PLAY", "payload_cards": combo["cards"]} for combo in beatable
                    ],
                }

            return {
                "seat": seat,
                "actions": [{"type": "COVER", "required_count": round_kind}],
            }

        return {"seat": seat, "actions": []}

    # The methods below are intentionally left as explicit placeholders
    # for later M3/M4 milestones.
    def init_game(self, config: dict[str, Any], rng_seed: int | None = None) -> dict[str, Any]:
        raise NotImplementedError("init_game is not implemented in this stage")

    def apply_action(
        self,
        action_idx: int,
        cover_list: list[dict[str, int]] | None = None,
        client_version: int | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("apply_action is not implemented in this stage")

    def settle(self) -> dict[str, Any]:
        raise NotImplementedError("settle is not implemented in this stage")

    def get_public_state(self) -> dict[str, Any]:
        return self.dump_state()

    def get_private_state(self, seat: int) -> dict[str, Any]:
        return {"hand": self._seat_hand(seat)}
