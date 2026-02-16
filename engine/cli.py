"""Command-line runner for local engine debugging."""

from __future__ import annotations

import argparse
import time
from typing import Any, Callable

from engine.core import XianqiGameEngine


def resolve_seed(seed: int | None, now_provider: Callable[[], int] | None = None) -> int:
    """Return an explicit seed or derive one from current time."""

    if seed is not None:
        return int(seed)

    provider = now_provider or time.time_ns
    value = int(provider())
    return abs(value)


def build_initial_snapshot(seed: int | None = None) -> dict[str, Any]:
    """Initialize a game and return reproducible first-frame data."""

    actual_seed = resolve_seed(seed)
    engine = XianqiGameEngine()
    engine.init_game({"player_count": 3}, rng_seed=actual_seed)
    return {
        "seed": actual_seed,
        "public_state": engine.get_public_state(),
        "private_state_by_seat": {seat: engine.get_private_state(seat) for seat in range(3)},
    }


def render_turn_prompt(public_state: dict[str, Any]) -> str:
    """Render the seat prompt for the current decision maker."""

    decision = public_state.get("decision") or {}
    seat = decision.get("seat")
    if seat is None:
        return "当前无可操作座次。"
    return f"当前请扮演 seat{int(seat)} 操作。"


def _format_hand(hand: dict[str, Any]) -> str:
    if not hand:
        return "{}"
    parts = [f"{card_type}:{int(count)}" for card_type, count in sorted(hand.items())]
    return "{ " + ", ".join(parts) + " }"


def render_state_view(
    *,
    public_state: dict[str, Any],
    acting_seat: int,
    private_state_by_seat: dict[int, dict[str, Any]] | dict[str, dict[str, Any]],
) -> str:
    """Render public summary and only the acting seat's private state."""

    decision = public_state.get("decision") or {}
    players = public_state.get("players") or []

    lines: list[str] = []
    lines.append("=== Public State ===")
    lines.append(f"version: {public_state.get('version')}")
    lines.append(f"phase: {public_state.get('phase')}")
    lines.append(f"decision_seat: {decision.get('seat')}")
    for player in players:
        seat = player.get("seat")
        hand_count = player.get("hand_count", "-")
        captured = player.get("captured_pillar_count", "-")
        lines.append(f"seat{seat}: hand_count={hand_count}, captured_pillar_count={captured}")

    private_state = private_state_by_seat.get(acting_seat) or private_state_by_seat.get(str(acting_seat), {})
    hand = private_state.get("hand") if isinstance(private_state, dict) else {}

    lines.append("")
    lines.append(f"=== Private State (seat{acting_seat}) ===")
    lines.append(f"hand: {_format_hand(hand if isinstance(hand, dict) else {})}")

    return "\n".join(lines)


def _render_actions(actions: list[dict[str, Any]]) -> str:
    lines = ["=== Legal Actions ==="]
    for idx, action in enumerate(actions):
        action_type = str(action.get("type", ""))
        if action_type == "PLAY":
            payload = _format_hand({str(card["type"]): int(card["count"]) for card in action.get("payload_cards", [])})
            lines.append(f"[{idx}] PLAY payload={payload} power={action.get('power')}")
        elif action_type == "COVER":
            lines.append(f"[{idx}] COVER required_count={action.get('required_count')}")
        else:
            lines.append(f"[{idx}] {action_type}")
    return "\n".join(lines)


def _parse_cover_list(raw: str) -> list[dict[str, int]]:
    text = raw.strip()
    if not text:
        return []

    cards: dict[str, int] = {}
    for chunk in text.split(","):
        token = chunk.strip()
        if not token:
            continue
        if ":" not in token:
            raise ValueError("cover_list format must be TYPE:COUNT separated by commas")
        card_type, count_text = token.split(":", 1)
        card_type = card_type.strip().upper()
        count = int(count_text.strip())
        if not card_type or count <= 0:
            raise ValueError("cover_list contains invalid card or count")
        cards[card_type] = cards.get(card_type, 0) + count
    return [{"type": card_type, "count": count} for card_type, count in sorted(cards.items())]


def run_cli(seed: int | None = None, input_fn: Callable[[str], str] = input, output_fn: Callable[[str], None] = print) -> int:
    """Run one local game loop by rotating seats according to decision state."""

    actual_seed = resolve_seed(seed)
    output_fn(f"seed={actual_seed}")
    output_fn(f"replay: python -m engine.cli --seed {actual_seed}")

    engine = XianqiGameEngine()
    engine.init_game({"player_count": 3}, rng_seed=actual_seed)

    while True:
        public_state = engine.get_public_state()
        phase = str(public_state.get("phase"))

        if phase in {"settlement", "finished"}:
            output_fn(render_state_view(public_state=public_state, acting_seat=0, private_state_by_seat={0: {}}))
            if phase == "settlement":
                try:
                    engine.settle()
                    continue
                except NotImplementedError:
                    output_fn("已到 settlement，当前版本 settle 未实现，结束演练。")
            else:
                output_fn("对局已结束。")
            return 0

        decision = public_state.get("decision") or {}
        if decision.get("seat") is None:
            output_fn("当前无可操作座次，结束。")
            return 0
        acting_seat = int(decision["seat"])

        private_state_by_seat = {seat: engine.get_private_state(seat) for seat in range(3)}
        output_fn(render_state_view(public_state=public_state, acting_seat=acting_seat, private_state_by_seat=private_state_by_seat))
        output_fn(render_turn_prompt(public_state))

        legal_actions = engine.get_legal_actions(acting_seat)
        actions = legal_actions.get("actions", [])
        if not actions:
            output_fn("当前无合法动作，结束。")
            return 0
        output_fn(_render_actions(actions))

        try:
            idx_raw = input_fn("请输入 action_idx: ").strip()
            action_idx = int(idx_raw)
            if action_idx < 0 or action_idx >= len(actions):
                raise ValueError("ENGINE_INVALID_ACTION_INDEX")
        except ValueError as exc:
            output_fn(str(exc))
            continue

        selected = actions[action_idx]
        cover_list: list[dict[str, int]] | None = None
        if str(selected.get("type")) == "COVER":
            raw_cover = input_fn("请输入 cover_list (例如 R_SHI:1,B_NIU:1): ")
            try:
                cover_list = _parse_cover_list(raw_cover)
            except Exception as exc:  # pylint: disable=broad-except
                output_fn(str(exc))
                continue

        try:
            engine.apply_action(
                action_idx=action_idx,
                cover_list=cover_list,
                client_version=int(public_state.get("version", 0)),
            )
        except Exception as exc:  # pylint: disable=broad-except
            output_fn(str(exc))
            continue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local Xianqi engine CLI.")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducible runs.")
    args = parser.parse_args(argv)
    return run_cli(seed=args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
