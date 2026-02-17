"""Core game engine shell used by M3 tests."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import random
from typing import Any

from engine.actions import get_legal_actions as actions_get_legal_actions
from engine.combos import enumerate_combos
from engine.reducer import ReducerDeps, reduce_apply_action
from engine.serializer import (
    dump_state as serializer_dump_state,
    get_private_state as serializer_get_private_state,
    get_public_state as serializer_get_public_state,
    load_state as serializer_load_state,
)


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
        self._state = serializer_load_state(state)

    def dump_state(self) -> dict[str, Any]:
        return serializer_dump_state(self._state)

    def _require_state(self) -> dict[str, Any]:
        if self._state is None:
            raise RuntimeError("engine state is not initialized")
        return self._state

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

    def _captured_pillar_count(self, seat: int) -> int:
        state = self._require_state()
        count = 0
        for group in state.get("pillar_groups", []):
            if int(group.get("winner_seat", -1)) != int(seat):
                continue
            pillars = group.get("pillars")
            if isinstance(pillars, list) and pillars:
                count += len(pillars)
            else:
                count += int(group.get("round_kind", 0))
        return count

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
        return actions_get_legal_actions(self._state, seat)

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
        deps: ReducerDeps = {
            "get_legal_actions": self.get_legal_actions,
            "enumerate_combos": enumerate_combos,
        }
        self._state = reduce_apply_action(
            state=state,
            action_idx=action_idx,
            cover_list=cover_list,
            client_version=client_version,
            deps=deps,
        )
        return {"new_state": self.dump_state()}

    def settle(self) -> dict[str, Any]:
        raise NotImplementedError("settle is not implemented in this stage")

    def get_public_state(self) -> dict[str, Any]:
        return serializer_get_public_state(self._state)

    def get_private_state(self, seat: int) -> dict[str, Any]:
        return serializer_get_private_state(self._state, seat)
