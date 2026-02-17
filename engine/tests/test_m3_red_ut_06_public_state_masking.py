"""M3 Red test: M3-UT-06 get_public_state masking contract."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_engine_class():
    from engine.core import XianqiGameEngine  # type: ignore

    return XianqiGameEngine


def test_m3_ut_06_get_public_state_masks_private_fields() -> None:
    """M3-UT-06: public state should hide hand/cards and decision-only details."""

    Engine = _load_engine_class()
    engine = Engine()

    internal_state = {
        "version": 12,
        "phase": "in_round",
        "players": [
            {"seat": 0, "hand": {"R_SHI": 2, "B_NIU": 1}},
            {"seat": 1, "hand": {"R_MA": 1, "B_NIU": 2}},
            {"seat": 2, "hand": {"R_NIU": 3}},
        ],
        "turn": {
            "current_seat": 1,
            "round_index": 2,
            "round_kind": 1,
            "last_combo": {
                "power": 9,
                "cards": [{"type": "R_SHI", "count": 1}],
                "owner_seat": 0,
            },
            "plays": [
                {"seat": 0, "power": 9, "cards": [{"type": "R_SHI", "count": 1}]},
                {"seat": 1, "power": -1, "cards": [{"type": "B_NIU", "count": 1}]},
            ],
        },
        "pillar_groups": [
            {
                "round_index": 1,
                "winner_seat": 2,
                "round_kind": 2,
                "plays": [
                    {"seat": 2, "power": 9, "cards": [{"type": "R_SHI", "count": 2}]},
                    {"seat": 0, "power": -1, "cards": [{"type": "R_NIU", "count": 2}]},
                    {"seat": 1, "power": -1, "cards": [{"type": "B_NIU", "count": 2}]},
                ],
            }
        ],
        "reveal": {"buckler_seat": None, "pending_order": [], "relations": []},
    }

    engine.load_state(internal_state)
    public_state = engine.get_public_state()

    assert "decision" not in public_state
    assert "started_at_ms" not in public_state
    assert "timeout_at_ms" not in public_state

    players = public_state["players"]
    expected_counts = {0: 3, 1: 3, 2: 3}
    assert len(players) == 3
    for player in players:
        seat = int(player["seat"])
        assert "hand" not in player
        assert int(player["hand_count"]) == expected_counts[seat]

    assert int(public_state["turn"]["current_seat"]) == 1

    turn_covered_play = public_state["turn"]["plays"][1]
    assert int(turn_covered_play["power"]) == -1
    assert turn_covered_play.get("covered_count") == 1
    assert "cards" not in turn_covered_play

    covered_group_plays = public_state["pillar_groups"][0]["plays"][1:]
    assert len(covered_group_plays) == 2
    assert covered_group_plays[0].get("covered_count") == 2
    assert covered_group_plays[1].get("covered_count") == 2
    assert "cards" not in covered_group_plays[0]
    assert "cards" not in covered_group_plays[1]
