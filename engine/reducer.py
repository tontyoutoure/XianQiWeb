"""Reducer functions for engine action application."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, TypedDict


class ReducerDeps(TypedDict):
    """External dependencies injected from engine core."""

    get_legal_actions: Callable[[int], dict[str, Any]]
    enumerate_combos: Callable[..., list[dict[str, Any]]]


def _count_cards(cards: dict[str, int]) -> int:
    return sum(int(count) for count in cards.values())


def _normalize_cards(cards: dict[str, Any] | None) -> dict[str, int]:
    if cards is None:
        return {}
    if not isinstance(cards, dict):
        raise ValueError("ENGINE_INVALID_COVER_LIST")

    normalized: dict[str, int] = {}
    for raw_type, raw_count in cards.items():
        card_type = str(raw_type).strip()
        try:
            count = int(raw_count)
        except (TypeError, ValueError) as exc:
            raise ValueError("ENGINE_INVALID_COVER_LIST") from exc
        if not card_type or count <= 0:
            raise ValueError("ENGINE_INVALID_COVER_LIST")
        normalized[card_type] = int(normalized.get(card_type, 0)) + count
    return normalized


def _cards_signature(cards: dict[str, int]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((str(card_type), int(count)) for card_type, count in cards.items()))


def _consume_cards_from_hand(state: dict[str, Any], seat: int, cards: dict[str, int]) -> None:
    hand = state["players"][int(seat)]["hand"]
    for card_type, count in cards.items():
        if int(hand.get(card_type, 0)) < count:
            raise ValueError("ENGINE_INVALID_COVER_LIST")

    for card_type, count in cards.items():
        hand[card_type] = int(hand.get(card_type, 0)) - count
        if hand[card_type] == 0:
            del hand[card_type]


def _find_combo_power(
    deps: ReducerDeps,
    hand: dict[str, int],
    cards: dict[str, int],
    round_kind: int,
) -> int:
    signature = _cards_signature(cards)
    enumerate_combos = deps["enumerate_combos"]
    for combo in enumerate_combos(hand, round_kind=round_kind):
        combo_cards = combo.get("cards", {})
        if not isinstance(combo_cards, dict):
            continue
        combo_sig = _cards_signature(combo_cards)
        if combo_sig == signature:
            return int(combo["power"])
    raise ValueError("ENGINE_INVALID_ACTION")


def _captured_pillar_count(state: dict[str, Any], seat: int) -> int:
    count = 0
    for group in state.get("pillar_groups", []):
        if int(group.get("winner_seat", -1)) != int(seat):
            continue
        count += int(group.get("round_kind", 0))
    return count


def _reset_turn_for_round_start(state: dict[str, Any], seat: int) -> None:
    turn = state.get("turn")
    if not isinstance(turn, dict):
        raise ValueError("ENGINE_INVALID_PHASE")
    turn["current_seat"] = int(seat)
    turn["round_kind"] = 0
    turn["last_combo"] = None
    turn["plays"] = []


def _finish_round(state: dict[str, Any]) -> None:
    turn = state.get("turn", {})
    plays = deepcopy(turn.get("plays", []))
    round_kind = int(turn.get("round_kind", 0))
    last_combo = turn.get("last_combo") or {}
    winner_seat = int(last_combo.get("owner_seat", 0))
    reveal = state["reveal"]
    active_revealer_raw = reveal.get("active_revealer_seat")
    active_revealer_seat = int(active_revealer_raw) if active_revealer_raw is not None else None
    active_pillars_before = (
        _captured_pillar_count(state, active_revealer_seat)
        if active_revealer_seat is not None
        else None
    )

    pillar_group = {
        "round_index": int(turn.get("round_index", 0)),
        "winner_seat": winner_seat,
        "round_kind": round_kind,
        "plays": plays,
    }
    state.setdefault("pillar_groups", []).append(pillar_group)
    pillar_counts = [_captured_pillar_count(state, seat) for seat in range(3)]

    if active_revealer_seat is not None and active_pillars_before is not None:
        active_pillars_after = _captured_pillar_count(state, active_revealer_seat)
        if active_pillars_before < 3 <= active_pillars_after:
            reveal["active_revealer_seat"] = None

    has_ceramic = any(count >= 6 for count in pillar_counts)
    enough_player_count = sum(1 for count in pillar_counts if count >= 3)
    should_enter_settlement = has_ceramic or enough_player_count == 2

    turn["round_index"] = int(turn.get("round_index", 0)) + 1
    turn["round_kind"] = 0
    turn["last_combo"] = None
    turn["plays"] = []
    turn["current_seat"] = winner_seat
    state["phase"] = "settlement" if should_enter_settlement else "buckle_flow"
    reveal["buckler_seat"] = None
    reveal["pending_order"] = []


def reduce_apply_action(
    *,
    state: dict[str, Any],
    action_idx: int,
    cover_list: dict[str, int] | None,
    client_version: int | None,
    deps: ReducerDeps,
) -> dict[str, Any]:
    """Apply action to state in-place and return the mutated state."""

    phase = state.get("phase")
    if phase == "settlement":
        raise ValueError("ENGINE_INVALID_PHASE")

    if client_version is not None and int(client_version) != int(state.get("version", 0)):
        raise ValueError("ENGINE_VERSION_CONFLICT")

    turn = state.get("turn") or {}
    if not isinstance(turn, dict):
        raise ValueError("ENGINE_INVALID_PHASE")
    acting_seat_raw = turn.get("current_seat")
    if acting_seat_raw is None:
        raise ValueError("ENGINE_INVALID_PHASE")
    acting_seat = int(acting_seat_raw)

    legal_actions = deps["get_legal_actions"](acting_seat)
    actions = legal_actions.get("actions", [])
    if action_idx < 0 or action_idx >= len(actions):
        raise ValueError("ENGINE_INVALID_ACTION_INDEX")

    target = actions[action_idx]
    action_type = str(target.get("type"))

    normalized_cover = _normalize_cards(cover_list)
    if action_type != "COVER" and normalized_cover:
        raise ValueError("ENGINE_INVALID_COVER_LIST")

    if action_type == "PLAY":
        payload_cards = _normalize_cards(target.get("payload_cards", {}))
        round_kind = _count_cards(payload_cards)
        if round_kind == 0:
            raise ValueError("ENGINE_INVALID_ACTION")

        hand_before_raw = state["players"][acting_seat]["hand"]
        hand_before = {str(card_type): int(count) for card_type, count in hand_before_raw.items()}
        power = int(target.get("power", _find_combo_power(deps, hand_before, payload_cards, round_kind)))
        _consume_cards_from_hand(state, acting_seat, payload_cards)

        play = {"seat": acting_seat, "power": power, "cards": payload_cards}

        if phase != "in_round":
            raise ValueError("ENGINE_INVALID_PHASE")

        expected_round_kind = int(turn.get("round_kind", 0))
        if expected_round_kind == 0:
            turn["round_kind"] = round_kind
            turn["plays"] = [play]
            turn["last_combo"] = {
                "power": power,
                "cards": payload_cards,
                "owner_seat": acting_seat,
            }
            turn["current_seat"] = (acting_seat + 1) % 3
        else:
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
                "owner_seat": acting_seat,
            }

            if len(plays) >= 3:
                _finish_round(state)
            else:
                turn["current_seat"] = (acting_seat + 1) % 3

    elif action_type == "COVER":
        if phase != "in_round":
            raise ValueError("ENGINE_INVALID_PHASE")

        required_count = int(target.get("required_count", 0))
        if _count_cards(normalized_cover) != required_count:
            raise ValueError("ENGINE_INVALID_COVER_LIST")

        _consume_cards_from_hand(state, acting_seat, normalized_cover)

        plays = turn.setdefault("plays", [])
        plays.append({"seat": acting_seat, "power": -1, "cards": normalized_cover})

        if len(plays) >= 3:
            _finish_round(state)
        else:
            next_seat = (acting_seat + 1) % 3
            turn["current_seat"] = next_seat

    elif action_type == "BUCKLE":
        if phase != "buckle_flow":
            raise ValueError("ENGINE_INVALID_PHASE")

        reveal = state["reveal"]
        if reveal.get("pending_order"):
            raise ValueError("ENGINE_INVALID_PHASE")

        default_order = [((acting_seat + 1) % 3), ((acting_seat + 2) % 3)]
        active_revealer = reveal.get("active_revealer_seat")
        if active_revealer is not None and int(active_revealer) == acting_seat:
            reveal["active_revealer_seat"] = None
            active_revealer = None
        if active_revealer is None:
            pending = default_order
        else:
            active_revealer_seat = int(active_revealer)
            pending = [active_revealer_seat]
            pending.extend(seat for seat in default_order if seat != active_revealer_seat)

        reveal["buckler_seat"] = acting_seat
        reveal["pending_order"] = pending
        turn["current_seat"] = int(pending[0])

    elif action_type == "PASS_BUCKLE":
        if phase != "buckle_flow":
            raise ValueError("ENGINE_INVALID_PHASE")

        reveal = state["reveal"]
        if reveal.get("pending_order"):
            raise ValueError("ENGINE_INVALID_PHASE")

        reveal["buckler_seat"] = None
        reveal["pending_order"] = []
        state["phase"] = "in_round"
        _reset_turn_for_round_start(state, acting_seat)

    elif action_type in {"REVEAL", "PASS_REVEAL"}:
        if phase != "buckle_flow":
            raise ValueError("ENGINE_INVALID_PHASE")

        reveal = state["reveal"]
        pending_order = list(reveal["pending_order"])
        if not pending_order or int(pending_order[0]) != acting_seat:
            raise ValueError("ENGINE_INVALID_PHASE")

        pending_order.pop(0)
        reveal["pending_order"] = pending_order

        active_revealer = reveal.get("active_revealer_seat")
        if action_type == "PASS_REVEAL" and active_revealer is not None and int(active_revealer) == acting_seat:
            reveal["active_revealer_seat"] = None

        buckler_raw = reveal.get("buckler_seat")
        if buckler_raw is None:
            raise ValueError("ENGINE_INVALID_PHASE")
        buckler_seat = int(buckler_raw)
        relations = reveal["relations"]
        if action_type == "REVEAL":
            relations.append(
                {
                    "revealer_seat": acting_seat,
                    "buckler_seat": buckler_seat,
                    "revealer_enough_at_time": _captured_pillar_count(state, acting_seat) >= 3,
                }
            )
            reveal["active_revealer_seat"] = acting_seat
            reveal["pending_order"] = []
            reveal["buckler_seat"] = None
            state["phase"] = "in_round"
            _reset_turn_for_round_start(state, buckler_seat)
        elif pending_order:
            turn["current_seat"] = int(pending_order[0])
        else:
            reveal["buckler_seat"] = None
            reveal["pending_order"] = []
            state["phase"] = "settlement"
            turn["current_seat"] = acting_seat
    else:
        raise ValueError("ENGINE_INVALID_ACTION")

    state["version"] = int(state.get("version", 0)) + 1
    return state
