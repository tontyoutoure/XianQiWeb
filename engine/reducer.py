"""Reducer functions for engine action application."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Callable, TypedDict


class ReducerDeps(TypedDict):
    """External dependencies injected from engine core."""

    get_legal_actions: Callable[[int], dict[str, Any]]
    enumerate_combos: Callable[..., list[dict[str, Any]]]


def _count_cards(cards: list[dict[str, int]]) -> int:
    return sum(int(card.get("count", 0)) for card in cards)


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


def _cards_signature(cards: list[dict[str, int]]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((str(card["type"]), int(card["count"])) for card in cards))


def _cards_to_types(cards: list[dict[str, int]], expected_count: int) -> list[str]:
    expanded: list[str] = []
    for card in cards:
        expanded.extend([str(card["type"])] * int(card["count"]))
    if len(expanded) != expected_count:
        raise ValueError("card count does not match expected round kind")
    expanded.sort()
    return expanded


def _consume_cards_from_hand(state: dict[str, Any], seat: int, cards: list[dict[str, int]]) -> None:
    hand = state["players"][int(seat)]["hand"]
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


def _build_pillars(plays: list[dict[str, Any]], round_kind: int) -> list[dict[str, Any]]:
    expanded_per_play = [_cards_to_types(play.get("cards", []), round_kind) for play in plays]

    pillars: list[dict[str, Any]] = []
    for idx in range(round_kind):
        single_pillar_types = [cards[idx] for cards in expanded_per_play]
        counter = Counter(single_pillar_types)
        pillar_cards = [{"type": card_type, "count": count} for card_type, count in sorted(counter.items())]
        pillars.append({"index": idx, "cards": pillar_cards})
    return pillars


def _find_combo_power(
    deps: ReducerDeps,
    hand: dict[str, int],
    cards: list[dict[str, int]],
    round_kind: int,
) -> int:
    signature = _cards_signature(cards)
    enumerate_combos = deps["enumerate_combos"]
    for combo in enumerate_combos(hand, round_kind=round_kind):
        combo_sig = _cards_signature(combo.get("cards", []))
        if combo_sig == signature:
            return int(combo["power"])
    raise ValueError("ENGINE_INVALID_ACTION")


def _advance_decision(state: dict[str, Any], seat: int, context: str) -> None:
    state["decision"] = {
        "seat": int(seat),
        "context": context,
        "started_at_ms": 0,
        "timeout_at_ms": None,
    }


def _captured_pillar_count(state: dict[str, Any], seat: int) -> int:
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


def _finish_round(state: dict[str, Any]) -> None:
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
        "pillars": _build_pillars(plays, round_kind),
    }
    state.setdefault("pillar_groups", []).append(pillar_group)

    turn["round_index"] = int(turn.get("round_index", 0)) + 1
    turn["round_kind"] = 0
    turn["last_combo"] = None
    turn["plays"] = []
    turn["current_seat"] = winner_seat
    state["phase"] = "buckle_decision"
    _advance_decision(state, winner_seat, "buckle_decision")


def reduce_apply_action(
    *,
    state: dict[str, Any],
    action_idx: int,
    cover_list: list[dict[str, int]] | None,
    client_version: int | None,
    deps: ReducerDeps,
) -> dict[str, Any]:
    """Apply action to state in-place and return the mutated state."""

    phase = state.get("phase")
    if phase in {"settlement", "finished"}:
        raise ValueError("ENGINE_INVALID_PHASE")

    if client_version is not None and int(client_version) != int(state.get("version", 0)):
        raise ValueError("ENGINE_VERSION_CONFLICT")

    decision = state.get("decision") or {}
    decision_seat = int(decision.get("seat", -1))

    legal_actions = deps["get_legal_actions"](decision_seat)
    actions = legal_actions.get("actions", [])
    if action_idx < 0 or action_idx >= len(actions):
        raise ValueError("ENGINE_INVALID_ACTION_INDEX")

    target = actions[action_idx]
    action_type = str(target.get("type"))

    normalized_cover = _normalize_cards(cover_list)
    if action_type != "COVER" and normalized_cover:
        raise ValueError("ENGINE_INVALID_COVER_LIST")

    if action_type == "PLAY":
        payload_cards = _normalize_cards(target.get("payload_cards", []))
        round_kind = _count_cards(payload_cards)
        if round_kind == 0:
            raise ValueError("ENGINE_INVALID_ACTION")

        hand_before_raw = state["players"][decision_seat]["hand"]
        hand_before = {str(card_type): int(count) for card_type, count in hand_before_raw.items()}
        power = int(target.get("power", _find_combo_power(deps, hand_before, payload_cards, round_kind)))
        _consume_cards_from_hand(state, decision_seat, payload_cards)

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
            _advance_decision(state, next_seat, "in_round")
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
                _finish_round(state)
            else:
                next_seat = (decision_seat + 1) % 3
                turn["current_seat"] = next_seat
                _advance_decision(state, next_seat, "in_round")
        else:
            raise ValueError("ENGINE_INVALID_PHASE")

    elif action_type == "COVER":
        if phase != "in_round":
            raise ValueError("ENGINE_INVALID_PHASE")

        required_count = int(target.get("required_count", 0))
        if _count_cards(normalized_cover) != required_count:
            raise ValueError("ENGINE_INVALID_COVER_LIST")

        _consume_cards_from_hand(state, decision_seat, normalized_cover)

        turn = state.get("turn", {})
        plays = turn.setdefault("plays", [])
        plays.append({"seat": decision_seat, "power": -1, "cards": normalized_cover})

        if len(plays) >= 3:
            _finish_round(state)
        else:
            next_seat = (decision_seat + 1) % 3
            turn["current_seat"] = next_seat
            _advance_decision(state, next_seat, "in_round")

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
        _advance_decision(state, pending[0], "reveal_decision")

    elif action_type in {"REVEAL", "PASS_REVEAL"}:
        if phase != "reveal_decision":
            raise ValueError("ENGINE_INVALID_PHASE")

        reveal = state.setdefault("reveal", {})
        pending_order = list(reveal.get("pending_order", []))
        if not pending_order or int(pending_order[0]) != decision_seat:
            raise ValueError("ENGINE_INVALID_PHASE")

        pending_order.pop(0)
        reveal["pending_order"] = pending_order

        buckler_seat = int(reveal.get("buckler_seat", -1))
        relations = reveal.setdefault("relations", [])
        if action_type == "REVEAL":
            relations.append(
                {
                    "revealer_seat": decision_seat,
                    "buckler_seat": buckler_seat,
                    "revealer_enough_at_time": _captured_pillar_count(state, decision_seat) >= 3,
                }
            )

        turn = state.get("turn", {})
        if pending_order:
            next_seat = int(pending_order[0])
            turn["current_seat"] = next_seat
            _advance_decision(state, next_seat, "reveal_decision")
        elif relations:
            next_seat = int(relations[-1].get("revealer_seat", decision_seat))
            state["phase"] = "buckle_decision"
            turn["current_seat"] = next_seat
            _advance_decision(state, next_seat, "buckle_decision")
        else:
            state["phase"] = "settlement"
            turn["current_seat"] = decision_seat
            _advance_decision(state, decision_seat, "settlement")
    else:
        raise ValueError("ENGINE_INVALID_ACTION")

    state["version"] = int(state.get("version", 0)) + 1
    return state
