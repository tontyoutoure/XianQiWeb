"""M3 SSOT tests: pillar_groups should not store redundant derived pillars field."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_engine_class():
    try:
        from engine.core import XianqiGameEngine  # type: ignore
    except ModuleNotFoundError as exc:
        pytest.fail(f"M3-SSOT: missing engine module/class: {exc}")
    return XianqiGameEngine


def _find_action_idx(legal_actions: dict[str, Any], action_type: str) -> int:
    actions = legal_actions.get("actions", [])
    for idx, action in enumerate(actions):
        if action.get("type") == action_type:
            return idx
    pytest.fail(f"missing expected action type {action_type} in legal actions: {actions}")


def _extract_state(engine: Any, output: Any) -> dict[str, Any]:
    if isinstance(output, dict):
        state = output.get("new_state")
        if isinstance(state, dict):
            return state
    dumped = engine.dump_state()
    if isinstance(dumped, dict) and dumped:
        return dumped
    pytest.fail("apply_action should expose state via output.new_state or dump_state()")


def _make_round_end_state(*, version: int) -> dict[str, Any]:
    return {
        "version": version,
        "phase": "in_round",
        "players": [
            {"seat": 0, "hand": {"B_NIU": 2}},
            {"seat": 1, "hand": {}},
            {"seat": 2, "hand": {}},
        ],
        "turn": {
            "current_seat": 0,
            "round_index": 5,
            "round_kind": 2,
            "last_combo": {
                "power": 9,
                "cards": {"R_SHI": 2},
                "owner_seat": 1,
            },
            "plays": [
                {"seat": 1, "power": 9, "cards": {"R_SHI": 2}},
                {"seat": 2, "power": -1, "cards": {"B_CHE": 2}},
            ],
        },
        "pillar_groups": [],
        "reveal": {
            "buckler_seat": None,
            "active_revealer_seat": None,
            "pending_order": [],
            "relations": [],
        },
    }


def test_m3_ssot_01_round_finish_group_has_no_legacy_pillars() -> None:
    """M3-SSOT-01: reducer should append pillar_groups item without legacy pillars cache."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(_make_round_end_state(version=301))

    cover_idx = _find_action_idx(engine.get_legal_actions(0), "COVER")
    output = engine.apply_action(
        action_idx=cover_idx,
        cover_list={"B_NIU": 2},
        client_version=301,
    )
    next_state = _extract_state(engine, output)

    groups = next_state.get("pillar_groups", [])
    assert len(groups) == 1
    group = groups[0]
    assert int(group.get("winner_seat", -1)) == 1
    assert int(group.get("round_kind", 0)) == 2
    assert "pillars" not in group


def test_m3_ssot_03_settlement_counts_pillars_by_round_kind() -> None:
    """M3-SSOT-03: settlement pillar counts should be sum(round_kind), not group count."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(
        {
            "version": 302,
            "phase": "settlement",
            "players": [
                {"seat": 0, "hand": {}},
                {"seat": 1, "hand": {}},
                {"seat": 2, "hand": {}},
            ],
            "turn": {
                "current_seat": 0,
                "round_index": 0,
                "round_kind": 0,
                "last_combo": None,
                "plays": [],
            },
            "pillar_groups": [
                {"round_index": 0, "winner_seat": 0, "round_kind": 2, "plays": []},
                {"round_index": 1, "winner_seat": 1, "round_kind": 1, "plays": []},
                {"round_index": 2, "winner_seat": 2, "round_kind": 3, "plays": []},
            ],
            "reveal": {
                "buckler_seat": None,
                "active_revealer_seat": None,
                "pending_order": [],
                "relations": [],
            },
        }
    )

    output = engine.settle()
    settlement = output.get("settlement", {})
    rows = settlement.get("chip_delta_by_seat", []) if isinstance(settlement, dict) else []
    indexed = {int(row.get("seat", -1)): row for row in rows if isinstance(row, dict)}

    assert int(indexed[0]["delta"]) == -1
    assert int(indexed[1]["delta"]) == -1
    assert int(indexed[2]["delta"]) == 2


def test_m3_ssot_05_logged_state_snapshot_excludes_legacy_pillars(tmp_path: Path) -> None:
    """M3-SSOT-05: logged state snapshots should not persist legacy pillars field."""

    Engine = _load_engine_class()
    log_dir = tmp_path / "ssot-log"

    engine = Engine()
    engine.init_game({"player_count": 3, "log_path": str(log_dir)}, rng_seed=20260220)
    engine.load_state(_make_round_end_state(version=303))

    cover_idx = _find_action_idx(engine.get_legal_actions(0), "COVER")
    engine.apply_action(
        action_idx=cover_idx,
        cover_list={"B_NIU": 2},
        client_version=303,
    )

    state_path = log_dir / "state_v304.json"
    assert state_path.is_file()
    with state_path.open("r", encoding="utf-8") as stream:
        logged_state = json.load(stream)
    groups = (logged_state.get("global") or {}).get("pillar_groups", [])
    assert isinstance(groups, list)
    assert groups
    assert "pillars" not in groups[0]


def test_m3_ssot_07_public_state_does_not_add_pillars_cache() -> None:
    """M3-SSOT-07: public_state should not include any derived pillars cache field."""

    Engine = _load_engine_class()
    engine = Engine()
    engine.load_state(_make_round_end_state(version=304))

    cover_idx = _find_action_idx(engine.get_legal_actions(0), "COVER")
    engine.apply_action(
        action_idx=cover_idx,
        cover_list={"B_NIU": 2},
        client_version=304,
    )

    public_state = engine.get_public_state()
    groups = public_state.get("pillar_groups", [])
    assert isinstance(groups, list)
    assert groups
    assert "pillars" not in groups[0]
