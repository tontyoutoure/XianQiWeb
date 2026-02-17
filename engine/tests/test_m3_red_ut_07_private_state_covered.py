"""M3 Red test: M3-UT-07 get_private_state private projection contract."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_engine_class():
    from engine.core import XianqiGameEngine  # type: ignore

    return XianqiGameEngine


def test_m3_ut_07_get_private_state_returns_target_hand_and_covered() -> None:
    """M3-UT-07: private state should expose only target seat hand/covered."""

    Engine = _load_engine_class()
    engine = Engine()

    internal_state = {
        "version": 13,
        "phase": "in_round",
        "players": [
            {"seat": 0, "hand": {"R_SHI": 2, "B_SHI": 1}},
            {"seat": 1, "hand": {"R_MA": 1, "B_NIU": 2}},
            {"seat": 2, "hand": {"R_NIU": 3}},
        ],
        "turn": {
            "current_seat": 2,
            "round_index": 3,
            "round_kind": 1,
            "last_combo": {
                "power": 9,
                "cards": [{"type": "R_SHI", "count": 1}],
                "owner_seat": 0,
            },
            "plays": [
                {"seat": 0, "power": 9, "cards": [{"type": "R_SHI", "count": 1}]},
                {"seat": 1, "power": -1, "cards": [{"type": "B_NIU", "count": 1}]},
                {"seat": 2, "power": -1, "cards": [{"type": "R_NIU", "count": 1}]},
            ],
        },
        "pillar_groups": [
            {
                "round_index": 1,
                "winner_seat": 2,
                "round_kind": 2,
                "plays": [
                    {"seat": 2, "power": 9, "cards": [{"type": "R_SHI", "count": 2}]},
                    {"seat": 1, "power": -1, "cards": [{"type": "B_NIU", "count": 2}]},
                    {"seat": 0, "power": -1, "cards": [{"type": "R_NIU", "count": 2}]},
                ],
            },
            {
                "round_index": 2,
                "winner_seat": 0,
                "round_kind": 1,
                "plays": [
                    {"seat": 0, "power": 5, "cards": [{"type": "R_MA", "count": 1}]},
                    {
                        "seat": 1,
                        "power": -1,
                        "cards": [
                            {"type": "R_NIU", "count": 1},
                            {"type": "B_NIU", "count": 1},
                        ],
                    },
                ],
            },
        ],
        "reveal": {"buckler_seat": None, "pending_order": [], "relations": []},
    }

    engine.load_state(internal_state)
    private_state = engine.get_private_state(1)

    assert set(private_state.keys()) == {"hand", "covered"}
    assert private_state["hand"] == {"R_MA": 1, "B_NIU": 2}
    assert private_state["covered"] == {"B_NIU": 4, "R_NIU": 1}
    assert "players" not in private_state
    assert "turn" not in private_state
