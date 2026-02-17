"""Core game engine shell used by M3 tests."""

from __future__ import annotations

from collections import Counter
import random
from typing import Any

from engine.actions import get_legal_actions as actions_get_legal_actions
from engine.combos import enumerate_combos
from engine.reducer import ReducerDeps, reduce_apply_action
from engine.settlements import settle_state
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
    def _is_black_hand(hand: dict[str, int]) -> bool:
        shi_xiang = (
            int(hand.get("R_SHI", 0))
            + int(hand.get("B_SHI", 0))
            + int(hand.get("R_XIANG", 0))
            + int(hand.get("B_XIANG", 0))
        )
        return shi_xiang == 0

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
        state = self._require_state()
        output = settle_state(state)
        self._state = output["new_state"]
        return {
            "new_state": self.dump_state(),
            "settlement": output["settlement"],
        }

    def get_public_state(self) -> dict[str, Any]:
        return serializer_get_public_state(self._state)

    def get_private_state(self, seat: int) -> dict[str, Any]:
        return serializer_get_private_state(self._state, seat)
