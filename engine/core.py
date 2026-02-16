"""Core game engine shell used by M3 tests."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import random
from typing import Any

from engine.combos import enumerate_combos


class XianqiGameEngine:
    """Stateful game engine facade.

    Current M3 scope focuses on state loading, legal action enumeration,
    and a minimal playable transition path for tests.
    """

    _DECK_TEMPLATE: dict[str, int] = {
        "R_SHI": 2,
        "B_SHI": 2,
        "R_XIANG": 2,
        "B_XIANG": 2,
        "R_MA": 2,
        "B_MA": 2,
        "R_CHE": 2,
        "B_CHE": 2,
        "R_GOU": 1,
        "B_GOU": 1,
        "R_NIU": 3,
        "B_NIU": 3,
    }

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
            if int(player.get("seat", -1)) == int(seat):
                hand = player.get("hand", {})
                if isinstance(hand, dict):
                    return {str(card_type): int(count) for card_type, count in hand.items()}
        return {}

    def _seat_hand_ref(self, seat: int) -> dict[str, int]:
        state = self._require_state()
        players = state.get("players", [])
        for player in players:
            if int(player.get("seat", -1)) == int(seat):
                hand = player.get("hand")
                if isinstance(hand, dict):
                    return hand
        raise ValueError(f"missing hand for seat={seat}")

    @staticmethod
    def _count_cards(cards: list[dict[str, int]]) -> int:
        return sum(int(card.get("count", 0)) for card in cards)

    @staticmethod
    def _normalize_cards(cards: list[dict[str, int]] | None) -> list[dict[str, int]]:
        if cards is None:
            return []
        normalized: list[dict[str, int]] = []
        for card in cards:
            card_type = str(card.get("type", ""))
            count = int(card.get("count", 0))
            if not card_type or count <= 0:
                continue
            normalized.append({"type": card_type, "count": count})
        normalized.sort(key=lambda item: (item["type"], item["count"]))
        return normalized

    @staticmethod
    def _cards_signature(cards: list[dict[str, int]]) -> tuple[tuple[str, int], ...]:
        return tuple(sorted((str(card["type"]), int(card["count"])) for card in cards))

    @staticmethod
    def _cards_to_types(cards: list[dict[str, int]], expected_count: int) -> list[str]:
        expanded: list[str] = []
        for card in cards:
            expanded.extend([str(card["type"])] * int(card["count"]))
        if len(expanded) != expected_count:
            raise ValueError("card count does not match expected round kind")
        expanded.sort()
        return expanded

    @staticmethod
    def _is_black_hand(hand: dict[str, int]) -> bool:
        shi_xiang = (
            int(hand.get("R_SHI", 0))
            + int(hand.get("B_SHI", 0))
            + int(hand.get("R_XIANG", 0))
            + int(hand.get("B_XIANG", 0))
        )
        return shi_xiang == 0

    def _consume_cards_from_hand(self, seat: int, cards: list[dict[str, int]]) -> None:
        hand = self._seat_hand_ref(seat)
        for card in cards:
            card_type = str(card["type"])
            count = int(card["count"])
            if int(hand.get(card_type, 0)) < count:
                raise ValueError("ENGINE_INVALID_COVER_LIST")

        for card in cards:
            card_type = str(card["type"])
            count = int(card["count"])
            hand[card_type] = int(hand.get(card_type, 0)) - count
            if hand[card_type] == 0:
                del hand[card_type]

    def _build_pillars(self, plays: list[dict[str, Any]], round_kind: int) -> list[dict[str, Any]]:
        expanded_per_play = [self._cards_to_types(play.get("cards", []), round_kind) for play in plays]

        pillars: list[dict[str, Any]] = []
        for idx in range(round_kind):
            single_pillar_types = [cards[idx] for cards in expanded_per_play]
            counter = Counter(single_pillar_types)
            pillar_cards = [{"type": card_type, "count": count} for card_type, count in sorted(counter.items())]
            pillars.append({"index": idx, "cards": pillar_cards})
        return pillars

    def _find_combo_power(self, hand: dict[str, int], cards: list[dict[str, int]], round_kind: int) -> int:
        signature = self._cards_signature(cards)
        for combo in enumerate_combos(hand, round_kind=round_kind):
            combo_sig = self._cards_signature(combo.get("cards", []))
            if combo_sig == signature:
                return int(combo["power"])
        raise ValueError("ENGINE_INVALID_ACTION")

    def _advance_decision(self, seat: int, context: str) -> None:
        state = self._require_state()
        state["decision"] = {
            "seat": int(seat),
            "context": context,
            "started_at_ms": 0,
            "timeout_at_ms": None,
        }

    def _finish_round(self) -> None:
        state = self._require_state()
        turn = state.get("turn", {})
        plays = deepcopy(turn.get("plays", []))
        round_kind = int(turn.get("round_kind", 0))
        last_combo = turn.get("last_combo") or {}
        winner_seat = int(last_combo.get("owner_seat", 0))

        pillar_group = {
            "round_index": int(turn.get("round_index", 0)),
            "winner_seat": winner_seat,
            "round_kind": round_kind,
            "plays": plays,
            "pillars": self._build_pillars(plays, round_kind),
        }
        state.setdefault("pillar_groups", []).append(pillar_group)

        turn["round_index"] = int(turn.get("round_index", 0)) + 1
        turn["round_kind"] = 0
        turn["last_combo"] = None
        turn["plays"] = []
        turn["current_seat"] = winner_seat
        state["phase"] = "buckle_decision"
        self._advance_decision(winner_seat, "buckle_decision")

    def get_legal_actions(self, seat: int) -> dict[str, Any]:
        state = self._require_state()
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

        hand = self._seat_hand(seat)

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

    def _init_deck(self) -> list[str]:
        deck: list[str] = []
        for card_type, count in self._DECK_TEMPLATE.items():
            deck.extend([card_type] * count)
        return deck

    @staticmethod
    def _cards_to_hand(cards: list[str]) -> dict[str, int]:
        return dict(Counter(cards))

    def init_game(self, config: dict[str, Any], rng_seed: int | None = None) -> dict[str, Any]:
        player_count = int(config.get("player_count", 0))
        if player_count != 3:
            raise ValueError("ENGINE_INVALID_CONFIG")

        rng = random.Random(rng_seed)
        deck = self._init_deck()
        rng.shuffle(deck)

        dealt_cards: dict[int, list[str]] = {0: [], 1: [], 2: []}
        for idx, card in enumerate(deck):
            dealt_cards[idx % 3].append(card)

        players = [
            {"seat": seat, "hand": self._cards_to_hand(dealt_cards[seat])}
            for seat in range(3)
        ]

        first_seat = int(rng.randint(0, 2))
        black_chess = any(self._is_black_hand(player["hand"]) for player in players)
        phase = "settlement" if black_chess else "buckle_decision"

        self._state = {
            "version": 1,
            "phase": phase,
            "players": players,
            "turn": {
                "current_seat": first_seat,
                "round_index": 0,
                "round_kind": 0,
                "last_combo": None,
                "plays": [],
            },
            "decision": {
                "seat": first_seat,
                "context": "buckle_decision" if not black_chess else "settlement",
                "started_at_ms": 0,
                "timeout_at_ms": None,
            },
            "pillar_groups": [],
            "reveal": {"buckler_seat": None, "pending_order": [], "relations": []},
        }
        return {"new_state": self.dump_state()}

    def apply_action(
        self,
        action_idx: int,
        cover_list: list[dict[str, int]] | None = None,
        client_version: int | None = None,
    ) -> dict[str, Any]:
        state = self._require_state()
        phase = state.get("phase")
        if phase in {"settlement", "finished"}:
            raise ValueError("ENGINE_INVALID_PHASE")

        if client_version is not None and int(client_version) != int(state.get("version", 0)):
            raise ValueError("ENGINE_VERSION_CONFLICT")

        decision = state.get("decision") or {}
        decision_seat = int(decision.get("seat", -1))

        legal_actions = self.get_legal_actions(decision_seat)
        actions = legal_actions.get("actions", [])
        if action_idx < 0 or action_idx >= len(actions):
            raise ValueError("ENGINE_INVALID_ACTION_INDEX")

        target = actions[action_idx]
        action_type = str(target.get("type"))

        normalized_cover = self._normalize_cards(cover_list)
        if action_type != "COVER" and normalized_cover:
            raise ValueError("ENGINE_INVALID_COVER_LIST")

        if action_type == "PLAY":
            payload_cards = self._normalize_cards(target.get("payload_cards", []))
            round_kind = self._count_cards(payload_cards)
            if round_kind == 0:
                raise ValueError("ENGINE_INVALID_ACTION")

            hand_before = self._seat_hand(decision_seat)
            power = int(target.get("power", self._find_combo_power(hand_before, payload_cards, round_kind)))
            self._consume_cards_from_hand(decision_seat, payload_cards)

            play = {"seat": decision_seat, "power": power, "cards": payload_cards}
            turn = state.get("turn", {})

            if phase == "buckle_decision":
                turn["round_kind"] = round_kind
                turn["plays"] = [play]
                turn["last_combo"] = {
                    "power": power,
                    "cards": payload_cards,
                    "owner_seat": decision_seat,
                }
                next_seat = (decision_seat + 1) % 3
                turn["current_seat"] = next_seat
                state["phase"] = "in_round"
                self._advance_decision(next_seat, "in_round")
            elif phase == "in_round":
                expected_round_kind = int(turn.get("round_kind", 0))
                if round_kind != expected_round_kind:
                    raise ValueError("ENGINE_INVALID_ACTION")

                last_combo = turn.get("last_combo") or {}
                last_power = int(last_combo.get("power", -1))
                if power <= last_power:
                    raise ValueError("ENGINE_INVALID_ACTION")

                plays = turn.setdefault("plays", [])
                plays.append(play)
                turn["last_combo"] = {
                    "power": power,
                    "cards": payload_cards,
                    "owner_seat": decision_seat,
                }

                if len(plays) >= 3:
                    self._finish_round()
                else:
                    next_seat = (decision_seat + 1) % 3
                    turn["current_seat"] = next_seat
                    self._advance_decision(next_seat, "in_round")
            else:
                raise ValueError("ENGINE_INVALID_PHASE")

        elif action_type == "COVER":
            if phase != "in_round":
                raise ValueError("ENGINE_INVALID_PHASE")

            required_count = int(target.get("required_count", 0))
            if self._count_cards(normalized_cover) != required_count:
                raise ValueError("ENGINE_INVALID_COVER_LIST")

            self._consume_cards_from_hand(decision_seat, normalized_cover)

            turn = state.get("turn", {})
            plays = turn.setdefault("plays", [])
            plays.append({"seat": decision_seat, "power": -1, "cards": normalized_cover})

            if len(plays) >= 3:
                self._finish_round()
            else:
                next_seat = (decision_seat + 1) % 3
                turn["current_seat"] = next_seat
                self._advance_decision(next_seat, "in_round")

        elif action_type == "BUCKLE":
            if phase != "buckle_decision":
                raise ValueError("ENGINE_INVALID_PHASE")
            state["phase"] = "reveal_decision"
            pending = [((decision_seat + 1) % 3), ((decision_seat + 2) % 3)]
            state["reveal"] = {
                "buckler_seat": decision_seat,
                "pending_order": pending,
                "relations": [],
            }
            self._advance_decision(pending[0], "reveal_decision")

        elif action_type in {"REVEAL", "PASS_REVEAL"}:
            raise ValueError("ENGINE_INVALID_PHASE")
        else:
            raise ValueError("ENGINE_INVALID_ACTION")

        state["version"] = int(state.get("version", 0)) + 1
        return {"new_state": self.dump_state()}

    def settle(self) -> dict[str, Any]:
        raise NotImplementedError("settle is not implemented in this stage")

    def get_public_state(self) -> dict[str, Any]:
        return self.dump_state()

    def get_private_state(self, seat: int) -> dict[str, Any]:
        return {"hand": self._seat_hand(seat)}
