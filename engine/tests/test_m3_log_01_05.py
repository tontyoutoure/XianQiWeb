"""M3 log tests: lightweight state/action/settlement file logging."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_engine_class():
    try:
        from engine.core import XianqiGameEngine  # type: ignore
    except ModuleNotFoundError as exc:
        pytest.fail(f"M3-LOG: missing engine module/class: {exc}")
    return XianqiGameEngine


def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _make_settlement_state(version: int = 7) -> dict[str, object]:
    return {
        "version": version,
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
        "pillar_groups": [],
        "reveal": {
            "buckler_seat": None,
            "active_revealer_seat": None,
            "pending_order": [],
            "relations": [],
        },
    }


def test_m3_log_01_init_with_log_path_resets_old_logs_and_writes_state_v1(tmp_path: Path) -> None:
    """M3-LOG-01: init_game(log_path) should reset old files and emit state_v1.json."""

    Engine = _load_engine_class()
    log_dir = tmp_path / "engine-log"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "state_v99.json").write_text("{}", encoding="utf-8")
    (log_dir / "action.json").write_text("[]", encoding="utf-8")
    (log_dir / "settle.json").write_text("{}", encoding="utf-8")

    engine = Engine()
    engine.init_game({"player_count": 3, "log_path": str(log_dir)}, rng_seed=20260219)

    state_v1 = log_dir / "state_v1.json"
    assert state_v1.is_file()
    assert not (log_dir / "state_v99.json").exists()
    assert not (log_dir / "action.json").exists()
    assert not (log_dir / "settle.json").exists()
    snapshot = _read_json(state_v1)
    assert set(snapshot.keys()) == {"global", "public", "private_states"}
    assert snapshot["global"].get("version") == 1


def test_m3_log_02_apply_action_updates_state_and_appends_action_record(tmp_path: Path) -> None:
    """M3-LOG-02: successful apply_action should write next state and append action.json."""

    Engine = _load_engine_class()
    log_dir = tmp_path / "engine-log"
    engine = Engine()
    engine.init_game({"player_count": 3, "log_path": str(log_dir)}, rng_seed=20260219)

    state_before = engine.dump_state()
    version_before = int(state_before.get("version", 0))
    acting_seat = int((state_before.get("turn") or {}).get("current_seat", 0))
    legal_actions = engine.get_legal_actions(acting_seat)
    chosen_action = legal_actions["actions"][0]

    engine.apply_action(action_idx=0, cover_list=None, client_version=version_before)

    assert (log_dir / "state_v2.json").is_file()
    action_records = _read_json(log_dir / "action.json")
    assert isinstance(action_records, list)
    assert len(action_records) == 1
    assert action_records[0]["version"] == version_before
    assert action_records[0]["seat"] == acting_seat
    assert action_records[0]["legal_actions"] == legal_actions["actions"]
    assert action_records[0]["taken_action"]["action_idx"] == 0
    assert action_records[0]["taken_action"]["action_type"] == chosen_action["type"]
    assert action_records[0]["taken_action"]["cover_list"] is None


def test_m3_log_03_invalid_action_does_not_write_new_logs(tmp_path: Path) -> None:
    """M3-LOG-03: failed apply_action should keep log files unchanged."""

    Engine = _load_engine_class()
    log_dir = tmp_path / "engine-log"
    engine = Engine()
    engine.init_game({"player_count": 3, "log_path": str(log_dir)}, rng_seed=20260219)

    with pytest.raises(ValueError, match="ENGINE_INVALID_ACTION_INDEX"):
        engine.apply_action(action_idx=999, cover_list=None, client_version=1)

    assert (log_dir / "state_v1.json").is_file()
    assert not (log_dir / "state_v2.json").exists()
    assert not (log_dir / "action.json").exists()


def test_m3_log_04_settle_overwrites_settle_json_and_writes_new_state(tmp_path: Path) -> None:
    """M3-LOG-04: settle success should overwrite settle.json and emit next state snapshot."""

    Engine = _load_engine_class()
    log_dir = tmp_path / "engine-log"

    engine = Engine()
    engine.init_game({"player_count": 3, "log_path": str(log_dir)}, rng_seed=20260219)
    engine.load_state(_make_settlement_state(version=7))
    before = engine.dump_state()
    assert before.get("phase") == "settlement"

    settle_output = engine.settle()

    settle_payload = _read_json(log_dir / "settle.json")
    assert settle_payload["from_version"] == int(before.get("version", 0))
    assert settle_payload["to_version"] == int(settle_output["new_state"]["version"])
    assert settle_payload["settlement"] == settle_output["settlement"]
    assert (log_dir / f"state_v{int(settle_output['new_state']['version'])}.json").is_file()


def test_m3_log_05_cli_passes_log_path_to_engine_init() -> None:
    """M3-LOG-05: CLI --log-path should be forwarded into init_game config."""

    import engine.cli as cli  # type: ignore

    captured: dict[str, object] = {}

    class FakeEngine:
        def init_game(self, config, rng_seed=None):  # noqa: ANN001, ANN002
            captured["config"] = dict(config)
            captured["rng_seed"] = rng_seed

        @staticmethod
        def get_public_state():
            return {
                "version": 1,
                "phase": "finished",
                "turn": {"current_seat": None},
                "players": [
                    {"seat": 0, "hand_count": 0},
                    {"seat": 1, "hand_count": 0},
                    {"seat": 2, "hand_count": 0},
                ],
            }

    outputs: list[str] = []
    original_engine_class = cli.XianqiGameEngine
    cli.XianqiGameEngine = FakeEngine
    try:
        exit_code = cli.run_cli(seed=7, log_path="/tmp/xq-log", input_fn=lambda _prompt: "0", output_fn=outputs.append)
    finally:
        cli.XianqiGameEngine = original_engine_class

    assert exit_code == 0
    assert captured["config"] == {"player_count": 3, "log_path": "/tmp/xq-log"}
    assert captured["rng_seed"] == 7
    assert any("log_path=/tmp/xq-log" in line for line in outputs)


def test_m3_log_06_state_snapshot_uses_global_public_private_states_shape(tmp_path: Path) -> None:
    """M3-LOG-06: state_v*.json should use global/public/private_states top-level schema."""

    Engine = _load_engine_class()
    log_dir = tmp_path / "engine-log"
    engine = Engine()
    engine.init_game({"player_count": 3, "log_path": str(log_dir)}, rng_seed=20260219)

    snapshot = _read_json(log_dir / "state_v1.json")
    assert set(snapshot.keys()) == {"global", "public", "private_states"}
    assert snapshot["global"] == engine.dump_state()
    assert snapshot["public"] == engine.get_public_state()
    assert snapshot["private_states"] == [engine.get_private_state(seat) for seat in range(3)]


def test_m3_log_07_apply_action_snapshot_matches_engine_projections(tmp_path: Path) -> None:
    """M3-LOG-07: post-action snapshot should match dump/public/private projections."""

    Engine = _load_engine_class()
    log_dir = tmp_path / "engine-log"
    engine = Engine()
    engine.init_game({"player_count": 3, "log_path": str(log_dir)}, rng_seed=20260219)
    state_before = engine.dump_state()
    engine.apply_action(action_idx=0, cover_list=None, client_version=int(state_before["version"]))

    snapshot = _read_json(log_dir / "state_v2.json")
    assert set(snapshot.keys()) == {"global", "public", "private_states"}
    assert snapshot["global"] == engine.dump_state()
    assert snapshot["public"] == engine.get_public_state()
    assert snapshot["private_states"] == [engine.get_private_state(seat) for seat in range(3)]


def test_m3_log_08_invalid_action_keeps_snapshot_schema_and_no_new_files(tmp_path: Path) -> None:
    """M3-LOG-08: invalid action should not create new state/action logs."""

    Engine = _load_engine_class()
    log_dir = tmp_path / "engine-log"
    engine = Engine()
    engine.init_game({"player_count": 3, "log_path": str(log_dir)}, rng_seed=20260219)

    with pytest.raises(ValueError, match="ENGINE_INVALID_ACTION_INDEX"):
        engine.apply_action(action_idx=999, cover_list=None, client_version=1)

    state_v1 = _read_json(log_dir / "state_v1.json")
    assert set(state_v1.keys()) == {"global", "public", "private_states"}
    assert not (log_dir / "state_v2.json").exists()
    assert not (log_dir / "action.json").exists()
