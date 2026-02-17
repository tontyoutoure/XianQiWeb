"""M3 Red tests: M3-CLI-01~04 command-line interface design contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_cli_module():
    try:
        import engine.cli as cli  # type: ignore
    except ModuleNotFoundError as exc:
        pytest.fail(f"M3-CLI: missing engine.cli module: {exc}")
    return cli


def test_m3_cli_01_explicit_seed_is_reproducible() -> None:
    """M3-CLI-01: explicit seed should produce reproducible first-frame snapshots."""

    cli = _load_cli_module()

    snapshot_a = cli.build_initial_snapshot(seed=20260217)
    snapshot_b = cli.build_initial_snapshot(seed=20260217)

    assert int(snapshot_a["seed"]) == 20260217
    assert int(snapshot_b["seed"]) == 20260217
    assert snapshot_a["public_state"] == snapshot_b["public_state"]
    assert snapshot_a["private_state_by_seat"] == snapshot_b["private_state_by_seat"]


def test_m3_cli_02_missing_seed_uses_time_provider() -> None:
    """M3-CLI-02: when seed is omitted, CLI should derive it from current time."""

    cli = _load_cli_module()

    seed = cli.resolve_seed(seed=None, now_provider=lambda: 1739769600123456789)

    assert seed == 1739769600123456789


def test_m3_cli_03_turn_prompt_matches_current_seat() -> None:
    """M3-CLI-03: turn prompt should instruct user to act as current acting seat."""

    cli = _load_cli_module()

    prompt = cli.render_turn_prompt({"turn": {"current_seat": 2}})

    assert "seat2" in prompt or "seat 2" in prompt


def test_m3_cli_04_state_view_shows_public_and_current_private_only() -> None:
    """M3-CLI-04: state view should include public summary + current seat private hand only."""

    cli = _load_cli_module()

    public_state: dict[str, Any] = {
        "version": 7,
        "phase": "in_round",
        "turn": {"current_seat": 1},
        "players": [
            {"seat": 0, "hand_count": 4},
            {"seat": 1, "hand_count": 5},
            {"seat": 2, "hand_count": 6},
        ],
    }
    private_state_by_seat = {
        0: {"hand": {"R_SHI": 2}},
        1: {"hand": {"B_NIU": 1}},
        2: {"hand": {"R_NIU": 1}},
    }

    rendered = cli.render_state_view(
        public_state=public_state,
        acting_seat=1,
        private_state_by_seat=private_state_by_seat,
    )

    assert "version" in rendered and "phase" in rendered
    assert "B_NIU" in rendered
    assert "R_SHI" not in rendered
    assert "R_NIU" not in rendered
