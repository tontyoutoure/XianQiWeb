"""M3 UT test: load_state should fail fast for non-canonical players order."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_engine_class():
    from engine.core import XianqiGameEngine  # type: ignore

    return XianqiGameEngine


def test_m3_ut_08_load_state_asserts_players_index_matches_seat() -> None:
    """M3-UT-08: load_state should assert when players list is not seat-indexed."""

    Engine = _load_engine_class()
    engine = Engine()

    broken_state = {
        "version": 1,
        "phase": "buckle_decision",
        "players": [
            {"seat": 1, "hand": {"R_SHI": 1}},
            {"seat": 0, "hand": {"B_SHI": 1}},
            {"seat": 2, "hand": {"R_NIU": 1}},
        ],
        "turn": {
            "current_seat": 0,
            "round_index": 0,
            "round_kind": 0,
            "last_combo": None,
            "plays": [],
        },
        "pillar_groups": [],
        "reveal": {"buckler_seat": None, "pending_order": [], "relations": []},
    }

    with pytest.raises(AssertionError):
        engine.load_state(broken_state)
