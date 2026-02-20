"""M3-CB-13~14: verify single-card power equivalence for GOU and CHE."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_enumerate_combos():
    try:
        from engine.combos import enumerate_combos  # type: ignore
    except ModuleNotFoundError as exc:
        pytest.fail(f"M3-CB: missing module/function: {exc}")
    return enumerate_combos


def _power_map(combos: list[dict[str, Any]]) -> dict[tuple[tuple[str, int], ...], int]:
    result: dict[tuple[tuple[str, int], ...], int] = {}
    for combo in combos:
        cards = combo.get("cards", {})
        if not isinstance(cards, dict):
            continue
        signature = tuple(sorted((str(card_type), int(count)) for card_type, count in cards.items()))
        result[signature] = int(combo["power"])
    return result


def test_m3_cb_13_r_gou_power_equals_r_che() -> None:
    """M3-CB-13: single R_GOU and R_CHE must have equal power."""

    enumerate_combos = _load_enumerate_combos()
    combos = enumerate_combos({"R_GOU": 1, "R_CHE": 1}, round_kind=1)
    powers = _power_map(combos)

    assert powers[(("R_GOU", 1),)] == powers[(("R_CHE", 1),)]


def test_m3_cb_14_b_gou_power_equals_b_che() -> None:
    """M3-CB-14: single B_GOU and B_CHE must have equal power."""

    enumerate_combos = _load_enumerate_combos()
    combos = enumerate_combos({"B_GOU": 1, "B_CHE": 1}, round_kind=1)
    powers = _power_map(combos)

    assert powers[(("B_GOU", 1),)] == powers[(("B_CHE", 1),)]
