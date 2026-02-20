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


def _assert_card_count_map(value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must be CardCountMap object")

    for card_type, raw_count in value.items():
        key = str(card_type).strip()
        if not key:
            raise AssertionError(f"{path} contains empty card type")
        try:
            count = int(raw_count)
        except (TypeError, ValueError) as exc:
            raise AssertionError(f"{path} contains invalid card count") from exc
        if count < 0:
            raise AssertionError(f"{path} contains negative card count")


def _assert_card_maps_canonical(state: dict[str, Any]) -> None:
    players = state.get("players") or []
    for seat, player in enumerate(players):
        if not isinstance(player, dict):
            continue
        _assert_card_count_map(player.get("hand", {}), f"state.players[{seat}].hand")

    turn = state.get("turn") or {}
    if isinstance(turn, dict):
        last_combo = turn.get("last_combo")
        if isinstance(last_combo, dict) and "cards" in last_combo:
            _assert_card_count_map(last_combo.get("cards"), "state.turn.last_combo.cards")

        plays = turn.get("plays") or []
        if isinstance(plays, list):
            for idx, play in enumerate(plays):
                if not isinstance(play, dict):
                    continue
                _assert_card_count_map(play.get("cards", {}), f"state.turn.plays[{idx}].cards")

    groups = state.get("pillar_groups") or []
    if isinstance(groups, list):
        for group_idx, group in enumerate(groups):
            if not isinstance(group, dict):
                continue
            if "pillars" in group:
                raise AssertionError("state.pillar_groups[*].pillars is no longer supported")
            plays = group.get("plays") or []
            if not isinstance(plays, list):
                continue
            for play_idx, play in enumerate(plays):
                if not isinstance(play, dict):
                    continue
                _assert_card_count_map(
                    play.get("cards", {}),
                    f"state.pillar_groups[{group_idx}].plays[{play_idx}].cards",
                )


def _assert_seat_or_none(value: Any, path: str) -> None:
    if value is None:
        return
    if type(value) is not int or value not in (0, 1, 2):
        raise AssertionError(f"{path} must be null or seat index(0/1/2)")


def _assert_seat_index(value: Any, path: str) -> None:
    if type(value) is not int or value not in (0, 1, 2):
        raise AssertionError(f"{path} must be seat index(0/1/2)")


def _assert_reveal_canonical(state: dict[str, Any]) -> None:
    reveal = state.get("reveal")
    if not isinstance(reveal, dict):
        raise AssertionError("state.reveal must be object")

    required_fields = ("buckler_seat", "active_revealer_seat", "pending_order", "relations")
    for field in required_fields:
        if field not in reveal:
            raise AssertionError(f"state.reveal.{field} is required")

    _assert_seat_or_none(reveal.get("buckler_seat"), "state.reveal.buckler_seat")
    _assert_seat_or_none(reveal.get("active_revealer_seat"), "state.reveal.active_revealer_seat")

    pending_order = reveal.get("pending_order")
    if not isinstance(pending_order, list):
        raise AssertionError("state.reveal.pending_order must be list")
    if len(pending_order) > 2:
        raise AssertionError("state.reveal.pending_order must contain at most 2 seats")
    pending_seen: set[int] = set()
    for idx, seat in enumerate(pending_order):
        if type(seat) is not int or seat not in (0, 1, 2):
            raise AssertionError(f"state.reveal.pending_order[{idx}] must be seat index(0/1/2)")
        if seat in pending_seen:
            raise AssertionError("state.reveal.pending_order must not contain duplicates")
        pending_seen.add(seat)

    relations = reveal.get("relations")
    if not isinstance(relations, list):
        raise AssertionError("state.reveal.relations must be list")
    required_relation_fields = ("revealer_seat", "buckler_seat", "revealer_enough_at_time")
    for idx, relation in enumerate(relations):
        if not isinstance(relation, dict):
            raise AssertionError(f"state.reveal.relations[{idx}] must be object")
        for field in required_relation_fields:
            if field not in relation:
                raise AssertionError(f"state.reveal.relations[{idx}].{field} is required")
        _assert_seat_index(relation.get("revealer_seat"), f"state.reveal.relations[{idx}].revealer_seat")
        _assert_seat_index(relation.get("buckler_seat"), f"state.reveal.relations[{idx}].buckler_seat")
        if type(relation.get("revealer_enough_at_time")) is not bool:
            raise AssertionError(
                f"state.reveal.relations[{idx}].revealer_enough_at_time must be bool"
            )


def load_state(state: dict[str, Any]) -> dict[str, Any]:
    """Clone and return internal complete state for engine restore."""

    cloned = deepcopy(state)
    _assert_players_canonical(cloned["players"])
    _assert_card_maps_canonical(cloned)
    _assert_reveal_canonical(cloned)
    return cloned


def dump_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Export complete internal state for persistence/reconnect."""

    if state is None:
        return {}
    return deepcopy(state)


def _count_cards(cards: dict[str, Any]) -> int:
    return sum(int(count) for count in cards.values())


def _sum_hand_count(hand: dict[str, Any]) -> int:
    return sum(int(count) for count in hand.values())


def _project_public_play(play: dict[str, Any]) -> dict[str, Any]:
    projected = deepcopy(play)
    if int(projected.get("power", 0)) != -1:
        return projected

    cards = projected.pop("cards", None)
    if isinstance(cards, dict):
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
        cards = play.get("cards") or {}
        if not isinstance(cards, dict):
            continue
        for card_type, raw_count in cards.items():
            card_type = str(card_type)
            count = int(raw_count)
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

    return {"hand": deepcopy(state["players"][target_seat]["hand"]), "covered": covered}
