"""Command-line runner for local engine debugging."""

from __future__ import annotations

import argparse
import time
from typing import Any, Callable

from engine.core import XianqiGameEngine

CARD_NAME_MAP: dict[str, str] = {
    "R_SHI": "红士",
    "B_SHI": "黑士",
    "R_XIANG": "红相",
    "B_XIANG": "黑相",
    "R_MA": "红马",
    "B_MA": "黑马",
    "R_CHE": "红车",
    "B_CHE": "黑车",
    "R_GOU": "红狗",
    "B_GOU": "黑狗",
    "R_NIU": "红牛",
    "B_NIU": "黑牛",
}

ACTION_NAME_MAP: dict[str, str] = {
    "PLAY": "出棋",
    "COVER": "垫棋",
    "BUCKLE": "扣棋",
    "PASS_BUCKLE": "不扣",
    "REVEAL": "掀棋",
    "PASS_REVEAL": "不掀",
}


def _resolve_acting_seat(public_state: dict[str, Any]) -> int | None:
    turn = public_state.get("turn")
    if isinstance(turn, dict) and turn.get("current_seat") is not None:
        return int(turn["current_seat"])
    return None


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
    """Render the seat prompt for the current acting seat."""

    seat = _resolve_acting_seat(public_state)
    if seat is None:
        return "当前无可操作座次。"
    return f"当前请扮演 seat{int(seat)} 操作。"


def _format_hand(hand: dict[str, Any]) -> str:
    if not hand:
        return "{}"
    parts = [
        f"{CARD_NAME_MAP.get(str(card_type), str(card_type))}:{int(count)}"
        for card_type, count in sorted(hand.items())
    ]
    return "{ " + ", ".join(parts) + " }"


def _compute_pillar_counts(public_state: dict[str, Any]) -> dict[int, int]:
    counts = {0: 0, 1: 0, 2: 0}
    groups = public_state.get("pillar_groups") or []
    if not isinstance(groups, list):
        return counts

    for group in groups:
        if not isinstance(group, dict):
            continue
        winner_seat = int(group.get("winner_seat", -1))
        round_kind = int(group.get("round_kind", 0))
        if winner_seat in counts:
            counts[winner_seat] += max(round_kind, 0)
    return counts


def render_state_view(
    *,
    public_state: dict[str, Any],
    acting_seat: int,
    private_state_by_seat: dict[int, dict[str, Any]] | dict[str, dict[str, Any]],
) -> str:
    """Render public summary and only the acting seat's private state."""

    acting_hint = _resolve_acting_seat(public_state)
    players = public_state.get("players") or []
    pillar_counts = _compute_pillar_counts(public_state)

    lines: list[str] = []
    lines.append("=== Public State ===")
    lines.append(f"version: {public_state.get('version')}")
    lines.append(f"phase: {public_state.get('phase')}")
    lines.append(f"current_seat: {acting_hint}")
    for player in players:
        seat = int(player.get("seat", -1))
        hand_count = player.get("hand_count", "-")
        captured = player.get("captured_pillar_count")
        if captured is None:
            captured = pillar_counts.get(seat, 0)
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
        action_name = ACTION_NAME_MAP.get(action_type, action_type)
        if action_type == "PLAY":
            payload_cards = action.get("payload_cards")
            payload = _format_hand(payload_cards if isinstance(payload_cards, dict) else {})
            lines.append(
                f"action_idx={idx} 动作={action_name} payload_cards={payload} 牌力={action.get('power')}"
            )
        elif action_type == "COVER":
            lines.append(
                f"action_idx={idx} 动作={action_name} required_count={action.get('required_count')}"
            )
        else:
            lines.append(f"action_idx={idx} 动作={action_name}")
    return "\n".join(lines)


def _expand_hand_cards(hand: dict[str, Any]) -> list[str]:
    cards: list[str] = []
    for card_type, count in sorted(hand.items()):
        card_count = int(count)
        if card_count <= 0:
            continue
        cards.extend([str(card_type)] * card_count)
    return cards


def _render_cover_cards(cover_cards: list[str]) -> str:
    lines = ["=== Cover Cards ==="]
    for idx, card_type in enumerate(cover_cards):
        lines.append(f"{idx}. {CARD_NAME_MAP.get(card_type, card_type)}")
    return "\n".join(lines)


def _parse_cover_indexes(raw: str, required_count: int, cover_cards: list[str]) -> dict[str, int]:
    text = raw.strip().replace(" ", "")
    if not text:
        raise ValueError("cover 索引不能为空")
    if len(text) != required_count:
        raise ValueError(f"cover 索引数量不正确，需选择 {required_count} 张")
    if not text.isdigit():
        raise ValueError("cover 索引格式错误，请输入数字索引串，例如 01")

    selected_indexes: set[int] = set()
    selected_cards: dict[str, int] = {}
    for digit in text:
        idx = int(digit)
        if idx in selected_indexes:
            raise ValueError("cover 索引不能重复")
        if idx < 0 or idx >= len(cover_cards):
            raise ValueError("cover 索引越界")
        selected_indexes.add(idx)
        card_type = cover_cards[idx]
        selected_cards[card_type] = selected_cards.get(card_type, 0) + 1

    return {card_type: count for card_type, count in sorted(selected_cards.items())}


def _emit_error(output_fn: Callable[[str], None], exc: Exception) -> None:
    message = str(exc)
    if message.startswith("ENGINE_"):
        output_fn(f"错误码:{message}")
        return
    output_fn(message)


def _format_settlement_row(row: dict[str, Any]) -> str:
    seat = int(row.get("seat", -1))
    delta = int(row.get("delta", 0))
    delta_enough = int(row.get("delta_enough", 0))
    delta_reveal = int(row.get("delta_reveal", 0))
    delta_ceramic = int(row.get("delta_ceramic", 0))
    return (
        f"seat{seat}: delta={delta} "
        f"delta_enough={delta_enough} delta_reveal={delta_reveal} delta_ceramic={delta_ceramic}"
    )


def render_settlement_view(settlement_payload: dict[str, Any]) -> str:
    rows = settlement_payload.get("chip_delta_by_seat", []) if isinstance(settlement_payload, dict) else []
    if not isinstance(rows, list):
        rows = []

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized_rows.append(row)
    normalized_rows.sort(key=lambda row: int(row.get("seat", 99)))

    total_delta = sum(int(row.get("delta", 0)) for row in normalized_rows)

    lines: list[str] = ["=== Settlement ==="]
    for row in normalized_rows:
        lines.append(_format_settlement_row(row))
    lines.append(f"invariant: sum(delta)={total_delta}")
    return "\n".join(lines)


def run_cli(
    seed: int | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    log_path: str | None = None,
) -> int:
    """Run one local game loop by rotating seats according to turn.current_seat."""

    actual_seed = resolve_seed(seed)
    output_fn(f"seed={actual_seed}")
    output_fn(f"replay: python -m engine.cli --seed {actual_seed}")
    if log_path is not None:
        output_fn(f"log_path={log_path}")

    engine = XianqiGameEngine()
    init_config: dict[str, Any] = {"player_count": 3}
    if log_path is not None:
        init_config["log_path"] = log_path
    engine.init_game(init_config, rng_seed=actual_seed)

    while True:
        public_state = engine.get_public_state()
        phase = str(public_state.get("phase"))

        if phase in {"settlement", "finished"}:
            output_fn(render_state_view(public_state=public_state, acting_seat=0, private_state_by_seat={0: {}}))
            if phase == "settlement":
                try:
                    settle_output = engine.settle()
                    settlement_payload = (
                        settle_output.get("settlement", {}) if isinstance(settle_output, dict) else {}
                    )
                    output_fn(render_settlement_view(settlement_payload))
                    continue
                except NotImplementedError:
                    output_fn("结算阶段已到达，当前版本未实现 settle，结束演练。")
            else:
                output_fn("对局已结束。")
            return 0

        acting_seat = _resolve_acting_seat(public_state)
        if acting_seat is None:
            output_fn("当前无可操作座次，结束。")
            return 0

        private_state_by_seat = {seat: engine.get_private_state(seat) for seat in range(3)}
        output_fn(render_state_view(public_state=public_state, acting_seat=acting_seat, private_state_by_seat=private_state_by_seat))
        output_fn(render_turn_prompt(public_state))

        legal_actions = engine.get_legal_actions(acting_seat)
        actions = legal_actions.get("actions", [])
        if not actions:
            output_fn("当前无合法动作，结束。")
            return 0

        is_cover_only = len(actions) == 1 and str(actions[0].get("type")) == "COVER"
        if is_cover_only:
            action_idx = 0
            selected = actions[0]
            output_fn("当前仅可垫棋，跳过 action_idx，直接输入垫牌索引。")
        else:
            output_fn(_render_actions(actions))
            try:
                idx_raw = input_fn("请输入 action_idx: ").strip()
                action_idx = int(idx_raw)
                if action_idx < 0 or action_idx >= len(actions):
                    raise ValueError("ENGINE_INVALID_ACTION_INDEX")
            except ValueError as exc:
                _emit_error(output_fn, exc)
                continue
            selected = actions[action_idx]

        action_applied = False
        if str(selected.get("type")) == "COVER":
            required_count = int(selected.get("required_count", 0))
            private_state = private_state_by_seat.get(acting_seat) or private_state_by_seat.get(str(acting_seat), {})
            hand = private_state.get("hand") if isinstance(private_state, dict) else {}
            cover_cards = _expand_hand_cards(hand if isinstance(hand, dict) else {})
            output_fn(_render_cover_cards(cover_cards))

            while True:
                example = "01" if required_count >= 2 else "0"
                raw_cover = input_fn(f"请输入 cover 索引串 (需选{required_count}张，例如 {example}): ")
                try:
                    cover_list = _parse_cover_indexes(
                        raw=raw_cover,
                        required_count=required_count,
                        cover_cards=cover_cards,
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    _emit_error(output_fn, exc)
                    continue

                try:
                    engine.apply_action(
                        action_idx=action_idx,
                        cover_list=cover_list,
                        client_version=int(public_state.get("version", 0)),
                    )
                    action_applied = True
                    break
                except Exception as exc:  # pylint: disable=broad-except
                    _emit_error(output_fn, exc)
                    if str(exc) == "ENGINE_INVALID_COVER_LIST":
                        continue
                    break
            if not action_applied:
                continue
            continue

        try:
            engine.apply_action(
                action_idx=action_idx,
                cover_list=None,
                client_version=int(public_state.get("version", 0)),
            )
            action_applied = True
        except Exception as exc:  # pylint: disable=broad-except
            _emit_error(output_fn, exc)

        if not action_applied:
            continue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local Xianqi engine CLI.")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducible runs.")
    parser.add_argument("--log-path", type=str, default=None, help="Optional directory for lightweight log files.")
    args = parser.parse_args(argv)
    return run_cli(seed=args.seed, log_path=args.log_path)


if __name__ == "__main__":
    raise SystemExit(main())
