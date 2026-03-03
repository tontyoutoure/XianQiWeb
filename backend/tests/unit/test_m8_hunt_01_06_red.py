"""Red-phase unit tests for M8 hunting flow semantics (HUNT-01~06)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.seed_hunter import run_seed_hunting
from app.seed_hunter import run_seed_hunting_mode


def _write_catalog(path: Path, cases: list[dict[str, Any]]) -> None:
    payload = {"cases": cases}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _candidate_case(
    test_id: str,
    *,
    seed_current: int | None = None,
    search_range: tuple[int, int] = (0, 10),
) -> dict[str, Any]:
    return {
        "test_id": test_id,
        "enabled": True,
        "seed_required": True,
        "seed_current": seed_current,
        "seed_requirement": {
            "first_turn_seat": 0,
            "hands_at_least_by_seat": {"0": {"R_SHI": 1}, "1": {}, "2": {}},
        },
        "fallback_policy": {"search_range": [search_range[0], search_range[1]]},
        "updated_at": "2026-01-01",
    }


def test_m8_hunt_01_hit_seed_current_should_skip_range_search(tmp_path: Path) -> None:
    """HUNT-01: when seed_current matches, run should not enter fallback range search."""
    catalog_dir = tmp_path / "seed-catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = catalog_dir / "catalog.json"
    _write_catalog(catalog_path, [_candidate_case("m8-hunt-01", seed_current=11, search_range=(20, 25))])
    calls: list[int] = []

    def _snapshot_provider(seed: int) -> dict[str, object]:
        calls.append(seed)
        if seed != 11:
            pytest.fail("range search should not run when seed_current already matches")
        return {"first_turn_seat": 0, "hands_by_seat": {0: {"R_SHI": 1}, 1: {}, 2: {}}}

    summary = run_seed_hunting(catalog_dir, snapshot_provider=_snapshot_provider)

    assert summary.case_total == 1
    assert summary.case_success == 1
    assert summary.case_fail == 0
    assert calls == [11]
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert payload["cases"][0]["seed_current"] == 11


def test_m8_hunt_02_miss_seed_current_should_search_range_in_order(tmp_path: Path) -> None:
    """HUNT-02: after quick-check miss, search [start,end) in order and pick first match."""
    catalog_dir = tmp_path / "seed-catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = catalog_dir / "catalog.json"
    _write_catalog(catalog_path, [_candidate_case("m8-hunt-02", seed_current=10, search_range=(20, 25))])
    calls: list[int] = []

    def _snapshot_provider(seed: int) -> dict[str, object]:
        calls.append(seed)
        if seed == 22:
            return {"first_turn_seat": 0, "hands_by_seat": {0: {"R_SHI": 1}, 1: {}, 2: {}}}
        return {"first_turn_seat": 0, "hands_by_seat": {0: {}, 1: {}, 2: {}}}

    summary = run_seed_hunting(catalog_dir, snapshot_provider=_snapshot_provider)

    assert summary.case_success == 1
    assert summary.case_fail == 0
    assert calls == [10, 20, 21, 22]
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert payload["cases"][0]["seed_current"] == 22


def test_m8_hunt_03_exhausted_search_should_be_recorded_as_failure(tmp_path: Path) -> None:
    """HUNT-03: exhausted range without match should increase fail stats and failed_test_ids."""
    catalog_dir = tmp_path / "seed-catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = catalog_dir / "catalog.json"
    _write_catalog(catalog_path, [_candidate_case("m8-hunt-03", seed_current=None, search_range=(30, 33))])

    def _snapshot_provider(seed: int) -> dict[str, object]:
        _ = seed
        return {"first_turn_seat": 0, "hands_by_seat": {0: {}, 1: {}, 2: {}}}

    summary = run_seed_hunting(catalog_dir, snapshot_provider=_snapshot_provider)

    assert summary.case_total == 1
    assert summary.case_success == 0
    assert summary.case_fail == 1
    assert summary.failed_test_ids == ["m8-hunt-03"]
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert payload["cases"][0]["seed_current"] is None
    assert payload["cases"][0]["updated_at"] == "2026-01-01"


def test_m8_hunt_04_writeback_should_only_touch_seed_current_and_updated_at(tmp_path: Path) -> None:
    """HUNT-04: writeback should update only seed_current/updated_at and keep other fields unchanged."""
    catalog_dir = tmp_path / "seed-catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = catalog_dir / "catalog.json"
    fixed_now = datetime(2026, 3, 3, 13, 0, 0, tzinfo=UTC)
    case = _candidate_case("m8-hunt-04", seed_current=None, search_range=(40, 45))
    case["tag"] = "keep-me"
    case["notes"] = {"owner": "qa"}
    case["fallback_policy"]["extra"] = "keep-policy"
    _write_catalog(catalog_path, [case])
    before = json.loads(catalog_path.read_text(encoding="utf-8"))

    def _snapshot_provider(seed: int) -> dict[str, object]:
        hand = {"R_SHI": 1} if seed == 42 else {}
        return {"first_turn_seat": 0, "hands_by_seat": {0: hand, 1: {}, 2: {}}}

    run_seed_hunting(
        catalog_dir,
        snapshot_provider=_snapshot_provider,
        now_provider=lambda: fixed_now,
    )

    after = json.loads(catalog_path.read_text(encoding="utf-8"))
    before_case = before["cases"][0]
    after_case = after["cases"][0]
    assert after_case["seed_current"] == 42
    assert after_case["updated_at"] == "2026-03-03T13:00:00Z"
    assert set(after_case.keys()) == set(before_case.keys())
    for key, value in before_case.items():
        if key in {"seed_current", "updated_at"}:
            continue
        assert after_case[key] == value


def test_m8_hunt_05_writeback_should_use_tmp_and_atomic_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HUNT-05: writeback should write .tmp and replace target file atomically."""
    catalog_dir = tmp_path / "seed-catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = catalog_dir / "catalog.json"
    _write_catalog(catalog_path, [_candidate_case("m8-hunt-05", seed_current=51, search_range=(60, 70))])

    def _snapshot_provider(seed: int) -> dict[str, object]:
        _ = seed
        return {"first_turn_seat": 0, "hands_by_seat": {0: {"R_SHI": 1}, 1: {}, 2: {}}}

    write_calls: list[Path] = []
    replace_calls: list[tuple[Path, Path]] = []
    original_write_text = Path.write_text
    original_replace = Path.replace

    def _spy_write_text(path_obj: Path, data: str, *args: Any, **kwargs: Any) -> int:
        write_calls.append(path_obj)
        return original_write_text(path_obj, data, *args, **kwargs)

    def _spy_replace(path_obj: Path, target: Path | str) -> Path:
        target_path = Path(target)
        replace_calls.append((path_obj, target_path))
        return original_replace(path_obj, target)

    monkeypatch.setattr(Path, "write_text", _spy_write_text)
    monkeypatch.setattr(Path, "replace", _spy_replace)
    run_seed_hunting(catalog_dir, snapshot_provider=_snapshot_provider)

    assert any(path.suffix == ".tmp" for path in write_calls)
    assert any(src.suffix == ".tmp" and dst == catalog_path for src, dst in replace_calls)


def test_m8_hunt_06_exit_code_should_reflect_summary_failures(tmp_path: Path) -> None:
    """HUNT-06: run_seed_hunting_mode should return 0 on full success, non-zero when any fail exists."""
    success_dir = tmp_path / "success-catalog"
    success_dir.mkdir(parents=True, exist_ok=True)
    _write_catalog(success_dir / "catalog.json", [_candidate_case("m8-hunt-06-ok", seed_current=71)])

    fail_dir = tmp_path / "fail-catalog"
    fail_dir.mkdir(parents=True, exist_ok=True)
    _write_catalog(fail_dir / "catalog.json", [_candidate_case("m8-hunt-06-fail", seed_current=None, search_range=(80, 82))])

    def _snapshot_provider(seed: int) -> dict[str, object]:
        hand = {"R_SHI": 1} if seed == 71 else {}
        return {"first_turn_seat": 0, "hands_by_seat": {0: hand, 1: {}, 2: {}}}

    success_code = run_seed_hunting_mode(success_dir, snapshot_provider=_snapshot_provider)
    fail_code = run_seed_hunting_mode(fail_dir, snapshot_provider=_snapshot_provider)

    assert success_code == 0
    assert fail_code != 0
