"""Red-phase unit tests for M8 matching semantics (MATCH-01~03)."""

from __future__ import annotations

from app.seed_hunter import SeedRequirement
from app.seed_hunter import _matches_requirement


def test_m8_match_01_first_turn_seat_must_match_exactly() -> None:
    """MATCH-01: first_turn_seat mismatch should fail even when hands satisfy requirements."""
    requirement = SeedRequirement(
        first_turn_seat=0,
        hands_at_least_by_seat={0: {"R_SHI": 1}, 1: {}, 2: {}},
    )

    def _snapshot_provider(seed: int) -> dict[str, object]:
        assert seed == 101
        return {
            "first_turn_seat": 1,
            "hands_by_seat": {0: {"R_SHI": 2}, 1: {}, 2: {}},
        }

    assert _matches_requirement(
        requirement=requirement,
        seed=101,
        snapshot_provider=_snapshot_provider,
    ) is False


def test_m8_match_02_hands_should_use_at_least_matching() -> None:
    """MATCH-02: allow extra cards, but reject when any required card count is insufficient."""
    requirement = SeedRequirement(
        first_turn_seat=0,
        hands_at_least_by_seat={
            0: {"R_SHI": 1, "B_ZU": 1},
            1: {"B_XIANG": 1},
            2: {},
        },
    )

    def _snapshot_provider_match(seed: int) -> dict[str, object]:
        assert seed == 202
        return {
            "first_turn_seat": 0,
            "hands_by_seat": {
                0: {"R_SHI": 1, "B_ZU": 2, "R_MA": 1},
                1: {"B_XIANG": 1, "R_SHI": 1},
                2: {"R_JU": 1},
            },
        }

    def _snapshot_provider_miss(seed: int) -> dict[str, object]:
        assert seed == 203
        return {
            "first_turn_seat": 0,
            "hands_by_seat": {
                0: {"R_SHI": 1, "R_MA": 1},
                1: {"B_XIANG": 1},
                2: {},
            },
        }

    assert _matches_requirement(
        requirement=requirement,
        seed=202,
        snapshot_provider=_snapshot_provider_match,
    ) is True
    assert _matches_requirement(
        requirement=requirement,
        seed=203,
        snapshot_provider=_snapshot_provider_miss,
    ) is False


def test_m8_match_03_match_should_only_depend_on_opening_snapshot() -> None:
    """MATCH-03: matcher should only use opening snapshot fields and ignore extra payload."""
    requirement = SeedRequirement(
        first_turn_seat=2,
        hands_at_least_by_seat={0: {"R_SHI": 1}, 1: {}, 2: {}},
    )
    calls: list[int] = []

    def _snapshot_provider(seed: int) -> dict[str, object]:
        calls.append(seed)
        return {
            "first_turn_seat": 2,
            "hands_by_seat": {0: {"R_SHI": 1}, 1: {}, 2: {}},
            "phase": "in_round",
            "later_actions": [{"action_idx": 9}],
        }

    assert _matches_requirement(
        requirement=requirement,
        seed=303,
        snapshot_provider=_snapshot_provider,
    ) is True
    assert calls == [303]
