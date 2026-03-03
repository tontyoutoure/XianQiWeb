"""Red-phase unit tests for M8 catalog contract (CAT-01~05)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.seed_hunter import run_seed_hunting


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


def _snapshot_always_match(seed: int) -> dict[str, object]:
    _ = seed
    return {
        "first_turn_seat": 0,
        "hands_by_seat": {0: {"R_SHI": 1}, 1: {}, 2: {}},
    }


def test_m8_cat_01_directory_and_case_order(tmp_path: Path) -> None:
    """CAT-01: catalog traversal should be filename asc + cases order."""
    catalog_dir = tmp_path / "seed-catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)

    _write_catalog(
        catalog_dir / "a-catalog.json",
        [
            _candidate_case("m8-cat-01-a1", seed_current=11),
            _candidate_case("m8-cat-01-a2", seed_current=12),
        ],
    )
    _write_catalog(
        catalog_dir / "b-catalog.json",
        [
            _candidate_case("m8-cat-01-b1", seed_current=13),
        ],
    )

    summary = run_seed_hunting(catalog_dir, snapshot_provider=_snapshot_always_match)
    assert summary.processed_test_ids == ["m8-cat-01-a1", "m8-cat-01-a2", "m8-cat-01-b1"]


def test_m8_cat_02_only_enabled_and_seed_required_are_processed(tmp_path: Path) -> None:
    """CAT-02: only enabled=true && seed_required=true cases should be processed and written back."""
    catalog_dir = tmp_path / "seed-catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    fixed_now = datetime(2026, 3, 3, 12, 30, 0, tzinfo=UTC)
    catalog_path = catalog_dir / "catalog.json"
    disabled_case = _candidate_case("m8-cat-02-disabled", seed_current=2)
    disabled_case["enabled"] = False
    no_seed_required_case = _candidate_case("m8-cat-02-no-seed", seed_current=None)
    no_seed_required_case["seed_required"] = False
    no_seed_required_case["seed_current"] = None

    _write_catalog(
        catalog_path,
        [
            _candidate_case("m8-cat-02-candidate", seed_current=None, search_range=(7, 8)),
            disabled_case,
            no_seed_required_case,
        ],
    )

    def _snapshot_only_seed7(seed: int) -> dict[str, object]:
        hand = {"R_SHI": 1} if seed == 7 else {}
        return {"first_turn_seat": 0, "hands_by_seat": {0: hand, 1: {}, 2: {}}}

    summary = run_seed_hunting(
        catalog_dir,
        snapshot_provider=_snapshot_only_seed7,
        now_provider=lambda: fixed_now,
    )

    assert summary.case_total == 1
    assert summary.processed_test_ids == ["m8-cat-02-candidate"]
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    cases = payload["cases"]
    assert cases[0]["seed_current"] == 7
    assert cases[0]["updated_at"] == "2026-03-03T12:30:00Z"
    assert cases[1]["seed_current"] == 2
    assert cases[1]["updated_at"] == "2026-01-01"
    assert cases[2]["seed_current"] is None
    assert cases[2]["updated_at"] == "2026-01-01"


def test_m8_cat_03_duplicate_test_id_in_directory_should_fail(tmp_path: Path) -> None:
    """CAT-03: duplicate test_id across catalog files should fail fast."""
    catalog_dir = tmp_path / "seed-catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    _write_catalog(catalog_dir / "a.json", [_candidate_case("m8-cat-03-dup", seed_current=1)])
    _write_catalog(catalog_dir / "b.json", [_candidate_case("m8-cat-03-dup", seed_current=2)])

    with pytest.raises(ValueError, match="duplicate test_id in seed catalog"):
        run_seed_hunting(catalog_dir, snapshot_provider=_snapshot_always_match)


def test_m8_cat_04_invalid_candidate_field_should_fail(tmp_path: Path) -> None:
    """CAT-04: invalid candidate fields should be treated as catalog contract errors."""
    catalog_dir = tmp_path / "seed-catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    invalid_case = _candidate_case("m8-cat-04-invalid")
    invalid_case["fallback_policy"]["search_range"] = [5, 5]
    _write_catalog(catalog_dir / "invalid.json", [invalid_case])

    with pytest.raises(ValueError, match="search_range is invalid"):
        run_seed_hunting(catalog_dir, snapshot_provider=_snapshot_always_match)


def test_m8_cat_05_seed_not_required_requires_null_seed_current(tmp_path: Path) -> None:
    """CAT-05: when seed_required=false, seed_current must be null (expected red)."""
    catalog_dir = tmp_path / "seed-catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    case = _candidate_case("m8-cat-05-no-seed-required", seed_current=99)
    case["seed_required"] = False
    _write_catalog(catalog_dir / "catalog.json", [case])

    with pytest.raises(ValueError, match="seed_required=false.*seed_current.*null"):
        run_seed_hunting(catalog_dir, snapshot_provider=_snapshot_always_match)
