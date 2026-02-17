"""M3 refactor tests: extract apply_action reducer without behavior changes."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _make_buckle_state(*, version: int = 12) -> dict[str, Any]:
    return {
        "version": version,
        "phase": "buckle_flow",
        "players": [
            {"seat": 0, "hand": {"R_SHI": 1, "B_NIU": 1}},
            {"seat": 1, "hand": {"B_SHI": 1}},
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
        "reveal": {"buckler_seat": None, "active_revealer_seat": None, "pending_order": [], "relations": []},
    }


def _make_in_round_cover_state(
    *,
    current_seat: int,
    round_kind: int,
    required_cover_hand: dict[str, int],
    winner_seat: int = 1,
    plays: list[dict[str, Any]] | None = None,
    version: int = 21,
) -> dict[str, Any]:
    if plays is None:
        plays = [
            {"seat": winner_seat, "power": 8, "cards": [{"type": "B_SHI", "count": round_kind}]},
        ]

    return {
        "version": version,
        "phase": "in_round",
        "players": [
            {"seat": 0, "hand": required_cover_hand if current_seat == 0 else {}},
            {"seat": 1, "hand": required_cover_hand if current_seat == 1 else {}},
            {"seat": 2, "hand": required_cover_hand if current_seat == 2 else {}},
        ],
        "turn": {
            "current_seat": current_seat,
            "round_index": 2,
            "round_kind": round_kind,
            "last_combo": {
                "power": 8,
                "cards": [{"type": "B_SHI", "count": round_kind}],
                "owner_seat": winner_seat,
            },
            "plays": plays,
        },
        "pillar_groups": [],
        "reveal": {"buckler_seat": None, "active_revealer_seat": None, "pending_order": [], "relations": []},
    }


def _find_action_idx(legal_actions: dict[str, Any], action_type: str) -> int:
    actions = legal_actions.get("actions", [])
    for idx, action in enumerate(actions):
        if action.get("type") == action_type:
            return idx
    pytest.fail(f"missing expected action type {action_type} in legal actions: {actions}")


def test_m3_rf_01_core_apply_action_delegates_to_reducer(monkeypatch: pytest.MonkeyPatch) -> None:
    """M3-RF-01: core.apply_action should delegate transition to reducer."""

    import engine.core as core_module

    calls: dict[str, Any] = {}

    def fake_reduce_apply_action(*, state, action_idx, cover_list, client_version, deps):
        calls["called"] = True
        calls["action_idx"] = action_idx
        calls["cover_list"] = cover_list
        calls["client_version"] = client_version
        calls["deps"] = deps
        state["version"] = int(state.get("version", 0)) + 1
        return state

    monkeypatch.setattr(core_module, "reduce_apply_action", fake_reduce_apply_action, raising=True)

    engine = core_module.XianqiGameEngine()
    engine.load_state(_make_buckle_state(version=40))

    output = engine.apply_action(action_idx=0, cover_list=None, client_version=40)
    next_state = output.get("new_state", {})

    assert calls.get("called") is True
    assert calls.get("action_idx") == 0
    assert calls.get("cover_list") is None
    assert calls.get("client_version") == 40
    assert isinstance(calls.get("deps"), dict)
    assert int(next_state.get("version", 0)) == 41


def test_m3_rf_02_cover_round_finish_stays_equivalent() -> None:
    """M3-RF-02: cover-driven round finish behavior should stay unchanged."""

    from engine.core import XianqiGameEngine

    engine = XianqiGameEngine()
    state = _make_in_round_cover_state(
        current_seat=0,
        round_kind=1,
        required_cover_hand={"B_NIU": 1},
        winner_seat=1,
        plays=[
            {"seat": 1, "power": 8, "cards": [{"type": "B_SHI", "count": 1}]},
            {"seat": 2, "power": -1, "cards": [{"type": "B_CHE", "count": 1}]},
        ],
        version=50,
    )
    engine.load_state(state)

    legal_actions = engine.get_legal_actions(0)
    cover_idx = _find_action_idx(legal_actions, "COVER")

    output = engine.apply_action(
        action_idx=cover_idx,
        cover_list=[{"type": "B_NIU", "count": 1}],
        client_version=50,
    )
    next_state = output.get("new_state", {})

    assert next_state.get("phase") == "buckle_flow"
    assert (next_state.get("turn") or {}).get("current_seat") == 1
    assert int(next_state.get("version", 0)) == 51
    assert len(next_state.get("pillar_groups", [])) == 1


def test_m3_rf_03_errors_and_version_guard_stay_equivalent() -> None:
    """M3-RF-03: failure paths keep original error codes and version semantics."""

    from engine.core import XianqiGameEngine

    engine = XianqiGameEngine()
    engine.load_state(_make_buckle_state(version=60))
    before = engine.dump_state()

    with pytest.raises(ValueError, match="ENGINE_VERSION_CONFLICT"):
        engine.apply_action(action_idx=0, cover_list=None, client_version=59)
    assert int(engine.dump_state().get("version", 0)) == int(before.get("version", 0))

    with pytest.raises(ValueError, match="ENGINE_INVALID_ACTION_INDEX"):
        engine.apply_action(action_idx=999, cover_list=None, client_version=60)
    assert int(engine.dump_state().get("version", 0)) == int(before.get("version", 0))
