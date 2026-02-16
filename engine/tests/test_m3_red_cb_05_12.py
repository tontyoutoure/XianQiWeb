"""M3 Red tests: M3-CB-05~12."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



def _load_enumerate_combos():
    try:
        from engine.combos import enumerate_combos  # type: ignore
    except ModuleNotFoundError as exc:
        pytest.fail(f"M3-CB: missing module/function: {exc}")
    return enumerate_combos



def _cards_signature(cards: list[dict[str, Any]]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((str(card["type"]), int(card["count"])) for card in cards))



def _combo_signature(combo: dict[str, Any]) -> tuple[tuple[str, int], ...]:
    cards = combo.get("cards")
    if not isinstance(cards, list):
        pytest.fail(f"combo.cards must be list, got: {combo}")
    return _cards_signature(cards)



def _signatures(combos: list[dict[str, Any]]) -> list[tuple[tuple[str, int], ...]]:
    return [_combo_signature(combo) for combo in combos]



def test_m3_cb_05_triple_niu_enumeration() -> None:
    """M3-CB-05: only legal red/black triple niu combos should be emitted."""

    enumerate_combos = _load_enumerate_combos()

    combos_red = enumerate_combos({"R_NIU": 3, "B_NIU": 2}, round_kind=3)
    assert _signatures(combos_red) == [(("R_NIU", 3),)]

    combos_black = enumerate_combos({"R_NIU": 2, "B_NIU": 3}, round_kind=3)
    assert _signatures(combos_black) == [(("B_NIU", 3),)]



def test_m3_cb_06_invalid_triples_must_not_be_emitted() -> None:
    """M3-CB-06: non-niu/mixed 3-card sets are not legal triples."""

    enumerate_combos = _load_enumerate_combos()
    combos = enumerate_combos({"R_SHI": 2, "R_NIU": 2, "B_NIU": 1}, round_kind=3)

    assert combos == []



def test_m3_cb_07_pair_power_order() -> None:
    """M3-CB-07: dog_pair == red shi pair > black shi pair > other pairs."""

    enumerate_combos = _load_enumerate_combos()
    hand = {"R_GOU": 1, "B_GOU": 1, "R_SHI": 2, "B_SHI": 2, "R_MA": 2}

    combos = enumerate_combos(hand, round_kind=2)
    signatures = _signatures(combos)
    power_by_sig = { _combo_signature(combo): int(combo["power"]) for combo in combos }

    idx = {sig: i for i, sig in enumerate(signatures)}

    dog_pair = (("B_GOU", 1), ("R_GOU", 1))
    red_shi_pair = (("R_SHI", 2),)
    black_shi_pair = (("B_SHI", 2),)
    red_ma_pair = (("R_MA", 2),)

    assert dog_pair in idx
    assert red_shi_pair in idx
    assert black_shi_pair in idx
    assert red_ma_pair in idx
    assert power_by_sig[dog_pair] == power_by_sig[red_shi_pair]
    assert power_by_sig[red_shi_pair] > power_by_sig[black_shi_pair] > power_by_sig[red_ma_pair]
    assert idx[dog_pair] < idx[black_shi_pair]
    assert idx[red_shi_pair] < idx[black_shi_pair]



def test_m3_cb_08_triple_power_order() -> None:
    """M3-CB-08: red triple niu must be ordered before black triple niu."""

    enumerate_combos = _load_enumerate_combos()
    combos = enumerate_combos({"R_NIU": 3, "B_NIU": 3}, round_kind=3)

    assert _signatures(combos) == [(("R_NIU", 3),), (("B_NIU", 3),)]



def test_m3_cb_09_single_power_order() -> None:
    """M3-CB-09: single-card order follows interface power table."""

    enumerate_combos = _load_enumerate_combos()
    hand = {
        "R_SHI": 1,
        "B_SHI": 1,
        "R_XIANG": 1,
        "B_XIANG": 1,
        "R_MA": 1,
        "B_MA": 1,
        "R_CHE": 1,
        "B_CHE": 1,
        "R_GOU": 1,
        "B_GOU": 1,
        "R_NIU": 1,
        "B_NIU": 1,
    }

    combos = enumerate_combos(hand, round_kind=1)
    signatures = _signatures(combos)

    assert signatures == [
        (("R_SHI", 1),),
        (("B_SHI", 1),),
        (("R_XIANG", 1),),
        (("B_XIANG", 1),),
        (("R_MA", 1),),
        (("B_MA", 1),),
        (("R_CHE", 1),),
        (("R_GOU", 1),),
        (("B_CHE", 1),),
        (("B_GOU", 1),),
        (("R_NIU", 1),),
        (("B_NIU", 1),),
    ]



def test_m3_cb_10_enumeration_order_stability() -> None:
    """M3-CB-10: repeated calls must produce identical sequence."""

    enumerate_combos = _load_enumerate_combos()
    hand = {"R_GOU": 1, "B_GOU": 1, "R_SHI": 2, "B_SHI": 2, "R_MA": 2}

    seq_1 = _signatures(enumerate_combos(hand, round_kind=2))
    seq_2 = _signatures(enumerate_combos(hand, round_kind=2))
    seq_3 = _signatures(enumerate_combos(hand, round_kind=2))

    assert seq_1 == seq_2 == seq_3



def test_m3_cb_11_round_kind_filtering() -> None:
    """M3-CB-11: round_kind should strictly filter by card count."""

    enumerate_combos = _load_enumerate_combos()
    hand = {"R_SHI": 2, "R_GOU": 1, "B_GOU": 1, "R_NIU": 3}

    combos_1 = enumerate_combos(hand, round_kind=1)
    combos_2 = enumerate_combos(hand, round_kind=2)
    combos_3 = enumerate_combos(hand, round_kind=3)

    for sig in _signatures(combos_1):
        assert sum(count for _, count in sig) == 1
    for sig in _signatures(combos_2):
        assert sum(count for _, count in sig) == 2
    for sig in _signatures(combos_3):
        assert sum(count for _, count in sig) == 3

    assert (("B_GOU", 1), ("R_GOU", 1)) in _signatures(combos_2)
    assert (("R_NIU", 3),) in _signatures(combos_3)



def test_m3_cb_12_strictly_greater_only_for_beating() -> None:
    """M3-CB-12: only combos with power > last power are beatable."""

    enumerate_combos = _load_enumerate_combos()
    hand = {"R_SHI": 1, "B_SHI": 1, "R_NIU": 1, "B_NIU": 1}

    combos = enumerate_combos(hand, round_kind=1)
    beatable = [combo for combo in combos if int(combo["power"]) > 8]

    assert _signatures(beatable) == [(("R_SHI", 1),)]
