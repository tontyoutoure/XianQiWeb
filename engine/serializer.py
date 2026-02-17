"""State serializer helpers for engine state/public/private projections."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _assert_players_canonical(players: Any) -> None:
    if not isinstance(players, list):
        raise AssertionError("state.players must be list")
    if len(players) != 3:
        raise AssertionError("state.players must contain exactly 3 players")

    for seat, player in enumerate(players):
        if not isinstance(player, dict):
            raise AssertionError("state.players item must be object")
        if int(player["seat"]) != seat:
            raise AssertionError("state.players must be indexed by seat order")


def load_state(state: dict[str, Any]) -> dict[str, Any]:
    """Clone and return internal complete state for engine restore."""

    cloned = deepcopy(state)
    _assert_players_canonical(cloned["players"])
    return cloned


def dump_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Export complete internal state for persistence/reconnect."""

    if state is None:
        return {}
    return deepcopy(state)


def _count_cards(cards: list[dict[str, Any]]) -> int:
    return sum(int(card.get("count", 0)) for card in cards)


def _sum_hand_count(hand: dict[str, Any]) -> int:
    return sum(int(count) for count in hand.values())


def _project_public_play(play: dict[str, Any]) -> dict[str, Any]:
    projected = deepcopy(play)
    if int(projected.get("power", 0)) != -1:
        return projected

    cards = projected.pop("cards", None)
    if isinstance(cards, list):
        covered_count = _count_cards(cards)
    else:
        covered_count = int(projected.get("covered_count", 0))
    projected["covered_count"] = int(covered_count)
    return projected


def get_public_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Project complete internal state to public view."""

    if state is None:
        return {}

    public_state: dict[str, Any] = {
        "version": int(state.get("version", 0)),
        "phase": state.get("phase"),
    }

    players = state.get("players", [])
    public_players: list[dict[str, Any]] = []
    for player in players:
        if not isinstance(player, dict):
            continue
        hand = player.get("hand")
        hand_count = _sum_hand_count(hand if isinstance(hand, dict) else {})
        public_players.append({"seat": int(player.get("seat", -1)), "hand_count": hand_count})
    public_state["players"] = public_players

    turn = state.get("turn")
    if isinstance(turn, dict):
        public_turn: dict[str, Any] = {
            "current_seat": turn.get("current_seat"),
            "round_index": turn.get("round_index"),
            "round_kind": turn.get("round_kind"),
            "last_combo": deepcopy(turn.get("last_combo")),
            "plays": [],
        }
        plays = turn.get("plays") or []
        if isinstance(plays, list):
            public_turn["plays"] = [_project_public_play(play) for play in plays if isinstance(play, dict)]
        public_state["turn"] = public_turn

    pillar_groups = state.get("pillar_groups") or []
    public_pillar_groups: list[dict[str, Any]] = []
    for group in pillar_groups:
        if not isinstance(group, dict):
            continue
        projected_group = deepcopy(group)
        plays = projected_group.get("plays") or []
        if isinstance(plays, list):
            projected_group["plays"] = [_project_public_play(play) for play in plays if isinstance(play, dict)]
        public_pillar_groups.append(projected_group)
    public_state["pillar_groups"] = public_pillar_groups

    reveal = state.get("reveal")
    if isinstance(reveal, dict):
        public_state["reveal"] = deepcopy(reveal)

    return public_state


def _accumulate_covered_cards(covered: dict[str, int], plays: list[dict[str, Any]], seat: int) -> None:
    for play in plays:
        if int(play.get("seat", -1)) != int(seat):
            continue
        if int(play.get("power", 0)) != -1:
            continue
        cards = play.get("cards") or []
        if not isinstance(cards, list):
            continue
        for card in cards:
            card_type = str(card.get("type", ""))
            count = int(card.get("count", 0))
            if not card_type or count <= 0:
                continue
            covered[card_type] = int(covered.get(card_type, 0)) + count


def get_private_state(state: dict[str, Any] | None, seat: int) -> dict[str, Any]:
    """Project complete internal state to one seat private view."""

    if state is None:
        raise RuntimeError("engine state is not initialized")

    target_seat = int(seat)
    covered: dict[str, int] = {}

    turn = state.get("turn") or {}
    turn_plays = turn.get("plays") or []
    if isinstance(turn_plays, list):
        _accumulate_covered_cards(covered, turn_plays, target_seat)

    for group in state.get("pillar_groups", []):
        if not isinstance(group, dict):
            continue
        group_plays = group.get("plays") or []
        if isinstance(group_plays, list):
            _accumulate_covered_cards(covered, group_plays, target_seat)

    return {"hand": state["players"][target_seat]["hand"], "covered": covered}
