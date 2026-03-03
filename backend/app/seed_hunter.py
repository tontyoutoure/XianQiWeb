"""Seed hunting implementation for M8 catalog mode."""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from typing import Callable


SnapshotProvider = Callable[[int], dict[str, object]]
NowProvider = Callable[[], datetime]


@dataclass(slots=True)
class SeedRequirement:
    first_turn_seat: int
    hands_at_least_by_seat: dict[int, dict[str, int]]


@dataclass(slots=True)
class SeedCaseConfig:
    test_id: str
    seed_current: int | None
    requirement: SeedRequirement
    search_start: int
    search_end: int


@dataclass(slots=True)
class CatalogFile:
    path: Path
    payload: dict[str, Any]
    cases: list[dict[str, Any]]
    dirty: bool = False


@dataclass(slots=True)
class CatalogCaseRef:
    catalog_file: CatalogFile
    case: dict[str, Any]


@dataclass(slots=True)
class SeedHuntSummary:
    case_total: int
    case_success: int
    case_fail: int
    failed_test_ids: list[str]
    processed_test_ids: list[str]


def _parse_seat(raw: object, *, field_name: str, test_id: str) -> int:
    if isinstance(raw, bool):
        raise ValueError(f"{test_id}: {field_name} must be int seat")
    if isinstance(raw, int):
        seat = raw
    elif isinstance(raw, str) and raw.isdigit():
        seat = int(raw)
    else:
        raise ValueError(f"{test_id}: {field_name} must be int seat")
    if seat not in {0, 1, 2}:
        raise ValueError(f"{test_id}: {field_name} must be 0..2")
    return seat


def _parse_positive_int(raw: object, *, field_name: str, test_id: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(f"{test_id}: {field_name} must be int")
    if raw < 1:
        raise ValueError(f"{test_id}: {field_name} must be >= 1")
    return raw


def _parse_card_counts(raw: object, *, field_name: str, test_id: str) -> dict[str, int]:
    if not isinstance(raw, dict):
        raise ValueError(f"{test_id}: {field_name} must be object")
    out: dict[str, int] = {}
    for card_type, count_raw in raw.items():
        if not isinstance(card_type, str) or not card_type:
            raise ValueError(f"{test_id}: {field_name} card key must be non-empty string")
        out[card_type] = _parse_positive_int(
            count_raw,
            field_name=f"{field_name}.{card_type}",
            test_id=test_id,
        )
    return out


def _parse_case_config(case: dict[str, Any]) -> SeedCaseConfig:
    test_id = case.get("test_id")
    if not isinstance(test_id, str) or not test_id:
        raise ValueError("seed catalog case.test_id must be non-empty string")

    enabled = case.get("enabled")
    seed_required = case.get("seed_required")
    if not isinstance(enabled, bool):
        raise ValueError(f"{test_id}: enabled must be bool")
    if not isinstance(seed_required, bool):
        raise ValueError(f"{test_id}: seed_required must be bool")

    if not (enabled and seed_required):
        raise ValueError(f"{test_id}: case is not seed-hunting candidate")

    seed_current_raw = case.get("seed_current")
    seed_current: int | None
    if seed_current_raw is None:
        seed_current = None
    elif isinstance(seed_current_raw, bool) or not isinstance(seed_current_raw, int) or seed_current_raw < 0:
        raise ValueError(f"{test_id}: seed_current must be null or int >= 0")
    else:
        seed_current = seed_current_raw

    requirement_raw = case.get("seed_requirement")
    if not isinstance(requirement_raw, dict):
        raise ValueError(f"{test_id}: seed_requirement must be object")
    first_turn_seat = _parse_seat(
        requirement_raw.get("first_turn_seat"),
        field_name="seed_requirement.first_turn_seat",
        test_id=test_id,
    )
    hands_raw = requirement_raw.get("hands_at_least_by_seat", {})
    if not isinstance(hands_raw, dict):
        raise ValueError(f"{test_id}: seed_requirement.hands_at_least_by_seat must be object")
    hands_at_least_by_seat: dict[int, dict[str, int]] = {}
    for seat_raw, card_counts_raw in hands_raw.items():
        seat = _parse_seat(
            seat_raw,
            field_name="seed_requirement.hands_at_least_by_seat.<seat>",
            test_id=test_id,
        )
        hands_at_least_by_seat[seat] = _parse_card_counts(
            card_counts_raw,
            field_name=f"seed_requirement.hands_at_least_by_seat[{seat}]",
            test_id=test_id,
        )

    fallback_policy = case.get("fallback_policy")
    if not isinstance(fallback_policy, dict):
        raise ValueError(f"{test_id}: fallback_policy must be object")
    search_range = fallback_policy.get("search_range")
    if not isinstance(search_range, list) or len(search_range) != 2:
        raise ValueError(f"{test_id}: fallback_policy.search_range must be [start, end)")
    start_raw, end_raw = search_range
    if isinstance(start_raw, bool) or not isinstance(start_raw, int):
        raise ValueError(f"{test_id}: fallback_policy.search_range.start must be int")
    if isinstance(end_raw, bool) or not isinstance(end_raw, int):
        raise ValueError(f"{test_id}: fallback_policy.search_range.end must be int")
    if start_raw < 0 or end_raw <= start_raw:
        raise ValueError(f"{test_id}: fallback_policy.search_range is invalid")

    return SeedCaseConfig(
        test_id=test_id,
        seed_current=seed_current,
        requirement=SeedRequirement(
            first_turn_seat=first_turn_seat,
            hands_at_least_by_seat=hands_at_least_by_seat,
        ),
        search_start=start_raw,
        search_end=end_raw,
    )


def _load_catalog_files(catalog_dir: Path) -> list[CatalogFile]:
    files: list[CatalogFile] = []
    for path in sorted(catalog_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"seed catalog file must provide object payload: {path}")
        cases = payload.get("cases", [])
        if not isinstance(cases, list):
            raise ValueError(f"seed catalog file must provide list cases: {path}")
        normalized_cases: list[dict[str, Any]] = []
        for idx, case in enumerate(cases):
            if not isinstance(case, dict):
                raise ValueError(f"seed catalog case must be object: {path}[{idx}]")
            normalized_cases.append(case)
        files.append(CatalogFile(path=path, payload=payload, cases=normalized_cases))
    return files


def _collect_case_refs(files: list[CatalogFile]) -> list[CatalogCaseRef]:
    refs: list[CatalogCaseRef] = []
    seen_test_ids: set[str] = set()
    for catalog_file in files:
        for case in catalog_file.cases:
            test_id = case.get("test_id")
            if not isinstance(test_id, str) or not test_id:
                raise ValueError(f"seed catalog case test_id must be non-empty string: {catalog_file.path}")
            if test_id in seen_test_ids:
                raise ValueError(f"duplicate test_id in seed catalog: {test_id}")
            seen_test_ids.add(test_id)
            refs.append(CatalogCaseRef(catalog_file=catalog_file, case=case))
    return refs


def _load_engine_class() -> type:
    try:
        module = importlib.import_module("engine.core")
        return getattr(module, "XianqiGameEngine")
    except ModuleNotFoundError:
        repo_root = Path(__file__).resolve().parents[2]
        repo_root_text = str(repo_root)
        if repo_root_text not in sys.path:
            sys.path.insert(0, repo_root_text)
        module = importlib.import_module("engine.core")
        return getattr(module, "XianqiGameEngine")


def build_engine_snapshot(seed: int) -> dict[str, object]:
    engine_cls = _load_engine_class()
    engine = engine_cls()
    engine.init_game({"player_count": 3}, rng_seed=int(seed))
    public_state = engine.get_public_state()
    if not isinstance(public_state, dict):
        raise RuntimeError("engine public_state must be object")
    turn = public_state.get("turn")
    if not isinstance(turn, dict):
        raise RuntimeError("engine public_state.turn must be object")
    first_turn_seat = _parse_seat(
        turn.get("current_seat"),
        field_name="engine.public_state.turn.current_seat",
        test_id=f"seed={seed}",
    )

    hands_by_seat: dict[int, dict[str, int]] = {}
    for seat in range(3):
        private_state = engine.get_private_state(seat)
        if not isinstance(private_state, dict):
            raise RuntimeError(f"engine private_state[{seat}] must be object")
        hand_raw = private_state.get("hand", {})
        hands_by_seat[seat] = _parse_card_counts(
            hand_raw,
            field_name=f"engine.private_state[{seat}].hand",
            test_id=f"seed={seed}",
        )
    return {
        "first_turn_seat": first_turn_seat,
        "hands_by_seat": hands_by_seat,
    }


def _parse_snapshot(snapshot: dict[str, object], *, seed: int) -> tuple[int, dict[int, dict[str, int]]]:
    first_turn_seat = _parse_seat(
        snapshot.get("first_turn_seat"),
        field_name="snapshot.first_turn_seat",
        test_id=f"seed={seed}",
    )
    hands_raw = snapshot.get("hands_by_seat")
    if not isinstance(hands_raw, dict):
        raise ValueError(f"seed={seed}: snapshot.hands_by_seat must be object")

    hands_by_seat: dict[int, dict[str, int]] = {}
    for seat_raw, hand_raw in hands_raw.items():
        seat = _parse_seat(
            seat_raw,
            field_name="snapshot.hands_by_seat.<seat>",
            test_id=f"seed={seed}",
        )
        hands_by_seat[seat] = _parse_card_counts(
            hand_raw,
            field_name=f"snapshot.hands_by_seat[{seat}]",
            test_id=f"seed={seed}",
        )
    return first_turn_seat, hands_by_seat


def _matches_requirement(
    *,
    requirement: SeedRequirement,
    seed: int,
    snapshot_provider: SnapshotProvider,
) -> bool:
    snapshot = snapshot_provider(seed)
    first_turn_seat, hands_by_seat = _parse_snapshot(snapshot, seed=seed)
    if first_turn_seat != requirement.first_turn_seat:
        return False
    for seat, required_hand in requirement.hands_at_least_by_seat.items():
        actual_hand = hands_by_seat.get(seat, {})
        for card_type, min_count in required_hand.items():
            if int(actual_hand.get(card_type, 0)) < min_count:
                return False
    return True


def _format_updated_at(now_value: datetime) -> str:
    utc_value = now_value.astimezone(UTC).replace(microsecond=0)
    return utc_value.isoformat().replace("+00:00", "Z")


def _write_catalog_file(catalog_file: CatalogFile) -> None:
    tmp_path = catalog_file.path.with_suffix(catalog_file.path.suffix + ".tmp")
    content = json.dumps(catalog_file.payload, ensure_ascii=False, indent=2) + "\n"
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(catalog_file.path)


def run_seed_hunting(
    catalog_dir: Path,
    *,
    snapshot_provider: SnapshotProvider | None = None,
    now_provider: NowProvider | None = None,
) -> SeedHuntSummary:
    provider = snapshot_provider or build_engine_snapshot
    now_fn = now_provider or (lambda: datetime.now(UTC))

    files = _load_catalog_files(catalog_dir)
    refs = _collect_case_refs(files)

    processed_test_ids: list[str] = []
    failed_test_ids: list[str] = []
    case_total = 0

    for ref in refs:
        case = ref.case
        test_id = str(case.get("test_id"))
        enabled = case.get("enabled")
        seed_required = case.get("seed_required")
        if not isinstance(enabled, bool):
            raise ValueError(f"{test_id}: enabled must be bool")
        if not isinstance(seed_required, bool):
            raise ValueError(f"{test_id}: seed_required must be bool")
        if not (enabled and seed_required):
            continue

        case_total += 1
        processed_test_ids.append(test_id)
        case_config = _parse_case_config(case)

        matched_seed: int | None = None
        if case_config.seed_current is not None and _matches_requirement(
            requirement=case_config.requirement,
            seed=case_config.seed_current,
            snapshot_provider=provider,
        ):
            matched_seed = case_config.seed_current
        else:
            for seed in range(case_config.search_start, case_config.search_end):
                if _matches_requirement(
                    requirement=case_config.requirement,
                    seed=seed,
                    snapshot_provider=provider,
                ):
                    matched_seed = seed
                    break

        if matched_seed is None:
            failed_test_ids.append(test_id)
            continue

        case["seed_current"] = matched_seed
        case["updated_at"] = _format_updated_at(now_fn())
        ref.catalog_file.dirty = True

    for catalog_file in files:
        if catalog_file.dirty:
            _write_catalog_file(catalog_file)

    case_fail = len(failed_test_ids)
    case_success = case_total - case_fail
    return SeedHuntSummary(
        case_total=case_total,
        case_success=case_success,
        case_fail=case_fail,
        failed_test_ids=failed_test_ids,
        processed_test_ids=processed_test_ids,
    )


def run_seed_hunting_mode(
    catalog_dir: Path,
    *,
    snapshot_provider: SnapshotProvider | None = None,
    now_provider: NowProvider | None = None,
) -> int:
    summary = run_seed_hunting(
        catalog_dir,
        snapshot_provider=snapshot_provider,
        now_provider=now_provider,
    )
    if summary.case_fail > 0:
        return 1
    return 0


__all__ = [
    "SeedHuntSummary",
    "build_engine_snapshot",
    "run_seed_hunting",
    "run_seed_hunting_mode",
]
