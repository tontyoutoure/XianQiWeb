"""Shared settlement test helpers for M5 UT scenarios."""

from __future__ import annotations

from pathlib import Path
import random
import sys
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def load_engine_class():
    """Import engine class with a test-friendly failure message."""

    try:
        from engine.core import XianqiGameEngine  # type: ignore
    except ModuleNotFoundError as exc:
        pytest.fail(f"M5-UT: missing engine module/class: {exc}")
    return XianqiGameEngine


def extract_state(output: Any, engine: Any) -> dict[str, Any]:
    """Extract state from output payload or engine dump fallback."""

    if isinstance(output, dict):
        state = output.get("new_state")
        if isinstance(state, dict):
            return state
    dumped = engine.dump_state()
    if isinstance(dumped, dict) and dumped:
        return dumped
    pytest.fail("init_game should expose state via output.new_state or dump_state()")


def _build_turn(current_seat: int = 0) -> dict[str, Any]:
    return {
        "current_seat": current_seat,
        "round_index": 0,
        "round_kind": 0,
        "last_combo": None,
        "plays": [],
    }


def _build_players() -> list[dict[str, Any]]:
    return [
        {"seat": 0, "hand": {}},
        {"seat": 1, "hand": {}},
        {"seat": 2, "hand": {}},
    ]


def _build_pillar_groups_from_counts(pillar_counts: tuple[int, int, int]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    round_index = 0
    for seat, count in enumerate(pillar_counts):
        for _ in range(count):
            groups.append(
                {
                    "round_index": round_index,
                    "winner_seat": seat,
                    "round_kind": 1,
                    "plays": [],
                }
            )
            round_index += 1
    return groups


def make_state(
    *,
    phase: str,
    version: int,
    pillar_counts: tuple[int, int, int] = (0, 0, 0),
    reveal_relations: list[dict[str, Any]] | None = None,
    current_seat: int = 0,
) -> dict[str, Any]:
    """Build a canonical engine state for settlement-focused tests."""

    if sum(pillar_counts) > 8:
        raise ValueError("pillar_count_sum must be <= 8")

    return {
        "version": version,
        "phase": phase,
        "players": _build_players(),
        "turn": _build_turn(current_seat=current_seat),
        "pillar_groups": _build_pillar_groups_from_counts(pillar_counts),
        "reveal": {
            "buckler_seat": None,
            "active_revealer_seat": None,
            "pending_order": [],
            "relations": reveal_relations or [],
        },
    }


def extract_settlement(output: Any) -> dict[str, Any]:
    if isinstance(output, dict):
        settlement = output.get("settlement")
        if isinstance(settlement, dict):
            return settlement
    pytest.fail("settle() should expose settlement payload via output.settlement")


def extract_new_state(output: Any) -> dict[str, Any]:
    if isinstance(output, dict):
        new_state = output.get("new_state")
        if isinstance(new_state, dict):
            return new_state
    pytest.fail("settle() should expose new state via output.new_state")


def _index_delta_rows(settlement_payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = settlement_payload.get("chip_delta_by_seat")
    if not isinstance(rows, list):
        pytest.fail("settlement.chip_delta_by_seat should be a list")

    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            pytest.fail("chip_delta_by_seat entries should be objects")
        seat = int(row.get("seat", -1))
        indexed[seat] = row
    return indexed


def assert_common_delta_invariants(settlement_payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Assert per-seat decomposition and global sum conservation."""

    indexed = _index_delta_rows(settlement_payload)
    assert set(indexed.keys()) == {0, 1, 2}

    sum_delta = 0
    sum_enough = 0
    sum_reveal = 0
    sum_ceramic = 0
    for seat in (0, 1, 2):
        row = indexed[seat]
        delta = int(row.get("delta", 0))
        delta_enough = int(row.get("delta_enough", 0))
        delta_reveal = int(row.get("delta_reveal", 0))
        delta_ceramic = int(row.get("delta_ceramic", 0))

        assert delta == delta_enough + delta_reveal + delta_ceramic

        sum_delta += delta
        sum_enough += delta_enough
        sum_reveal += delta_reveal
        sum_ceramic += delta_ceramic

    assert sum_delta == 0
    assert sum_enough == 0
    assert sum_reveal == 0
    assert sum_ceramic == 0
    return indexed


def assert_seat_delta(
    row: dict[str, Any],
    *,
    delta: int,
    enough: int,
    reveal: int,
    ceramic: int,
) -> None:
    """Assert one seat's settlement decomposition."""

    assert int(row["delta"]) == delta
    assert int(row["delta_enough"]) == enough
    assert int(row["delta_reveal"]) == reveal
    assert int(row["delta_ceramic"]) == ceramic


def settle_and_index(engine: Any) -> tuple[dict[str, Any], dict[str, Any], dict[int, dict[str, Any]]]:
    """Run settle() once and return output/settlement/indexed rows."""

    output = engine.settle()
    settlement = extract_settlement(output)
    indexed = assert_common_delta_invariants(settlement)
    return output, settlement, indexed


def _has_black_hand(hand: dict[str, int]) -> bool:
    shi_xiang = (
        int(hand.get("R_SHI", 0))
        + int(hand.get("B_SHI", 0))
        + int(hand.get("R_XIANG", 0))
        + int(hand.get("B_XIANG", 0))
    )
    return shi_xiang == 0


def _seed_has_black_opening(seed: int) -> bool:
    deck_template = {
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
    deck: list[str] = []
    for card_type, count in deck_template.items():
        deck.extend([card_type] * count)
    rng = random.Random(seed)
    rng.shuffle(deck)

    hands: list[dict[str, int]] = [{}, {}, {}]
    for idx, card in enumerate(deck):
        seat = idx % 3
        hands[seat][card] = int(hands[seat].get(card, 0)) + 1
    return any(_has_black_hand(hand) for hand in hands)


def find_black_opening_seed(*, max_seed: int = 4096) -> int:
    """Find a deterministic seed whose first deal would be black-chess."""

    for seed in range(max_seed):
        if _seed_has_black_opening(seed):
            return seed
    pytest.fail(f"did not find a black-opening seed in [0, {max_seed})")
