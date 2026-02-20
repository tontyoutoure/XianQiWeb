"""M3 Red tests: M3-UT-01~05 engine basics."""

from __future__ import annotations

from pathlib import Path
import random
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
        pytest.fail(f"M3-UT: missing engine module/class: {exc}")
    return XianqiGameEngine


def _hand_count(hand: dict[str, int]) -> int:
    return sum(int(v) for v in hand.values())


def _extract_state_after_init(engine: Any, output: Any) -> dict[str, Any]:
    if isinstance(output, dict):
        state = output.get("new_state")
        if isinstance(state, dict):
            return state
    dumped = engine.dump_state()
    if isinstance(dumped, dict) and dumped:
        return dumped
    pytest.fail("init_game should expose state via output.new_state or dump_state()")


def _has_black_hand(hand: dict[str, int]) -> bool:
    shi_xiang = hand.get("R_SHI", 0) + hand.get("B_SHI", 0) + hand.get("R_XIANG", 0) + hand.get("B_XIANG", 0)
    return shi_xiang == 0


def _seed_has_black_opening(seed: int) -> bool:
    deck_template = {
        "R_SHI": 2,
        "B_SHI": 2,
        "R_XIANG": 2,
        "B_XIANG": 2,
        "R_MA": 2,
        "B_MA": 2,
        "R_CHE": 2,
        "B_CHE": 2,
        "R_GOU": 1,
        "B_GOU": 1,
        "R_NIU": 3,
        "B_NIU": 3,
    }
    deck: list[str] = []
    for card_type, count in deck_template.items():
        deck.extend([card_type] * count)
    rng = random.Random(seed)
    rng.shuffle(deck)

    hands: list[dict[str, int]] = [{}, {}, {}]
    for idx, card in enumerate(deck):
        seat = idx % 3
        hands[seat][card] = int(hands[seat].get(card, 0)) + 1
    return any(_has_black_hand(hand) for hand in hands)


def test_m3_ut_01_init_game_deal_counts() -> None:
    """M3-UT-01: total cards = 24 and each seat starts with 8 cards."""

    Engine = _load_engine_class()
    engine = Engine()

    output = engine.init_game({"player_count": 3}, rng_seed=20260216)
    state = _extract_state_after_init(engine, output)
    players = state.get("players", [])

    assert len(players) == 3
    hand_counts = [_hand_count(player.get("hand", {})) for player in players]
    assert hand_counts == [8, 8, 8]
    assert sum(hand_counts) == 24


def test_m3_ut_02_seed_is_reproducible() -> None:
    """M3-UT-02: same seed should reproduce deal and first acting seat."""

    Engine = _load_engine_class()
    seed = 314159

    engine_a = Engine()
    engine_b = Engine()

    out_a = engine_a.init_game({"player_count": 3}, rng_seed=seed)
    out_b = engine_b.init_game({"player_count": 3}, rng_seed=seed)

    state_a = _extract_state_after_init(engine_a, out_a)
    state_b = _extract_state_after_init(engine_b, out_b)

    hands_a = [player.get("hand", {}) for player in state_a.get("players", [])]
    hands_b = [player.get("hand", {}) for player in state_b.get("players", [])]
    assert hands_a == hands_b

    seat_a = (state_a.get("turn") or {}).get("current_seat")
    seat_b = (state_b.get("turn") or {}).get("current_seat")
    assert seat_a == seat_b


def test_m3_ut_03_black_chess_triggers_seed_plus_one_reroll() -> None:
    """M3-UT-03: black opening should reroll by seed+1 until non-black."""

    Engine = _load_engine_class()

    for seed in range(0, 2048):
        if not _seed_has_black_opening(seed):
            continue
        engine = Engine()
        output = engine.init_game({"player_count": 3}, rng_seed=seed)
        state = _extract_state_after_init(engine, output)
        players = state.get("players", [])

        assert state.get("phase") == "buckle_flow"
        assert len(players) == 3
        assert not any(_has_black_hand(player.get("hand", {})) for player in players)
        return

    pytest.fail("did not find a black-opening seed in [0, 2048)")


def test_m3_ut_04_version_increment_and_invalid_action_no_change() -> None:
    """M3-UT-04: valid action increments version, invalid action keeps version."""

    Engine = _load_engine_class()
    engine = Engine()

    output = engine.init_game({"player_count": 3}, rng_seed=7)
    state = _extract_state_after_init(engine, output)

    version_before = int(state.get("version", 0))
    current_seat = int((state.get("turn") or {}).get("current_seat", 0))

    legal_actions = engine.get_legal_actions(current_seat)
    actions = legal_actions.get("actions", [])
    assert actions, "current acting seat should have legal actions"

    engine.apply_action(action_idx=0, cover_list=None, client_version=version_before)
    version_after_valid = int(engine.dump_state().get("version", 0))
    assert version_after_valid == version_before + 1

    with pytest.raises(Exception):
        engine.apply_action(action_idx=999, cover_list=None, client_version=version_after_valid)

    version_after_invalid = int(engine.dump_state().get("version", 0))
    assert version_after_invalid == version_after_valid


def test_m3_ut_05_dump_load_consistency() -> None:
    """M3-UT-05: dump then load should preserve public/private/legal outputs."""

    Engine = _load_engine_class()
    engine = Engine()

    output = engine.init_game({"player_count": 3}, rng_seed=99)
    state = _extract_state_after_init(engine, output)

    acting_seat = int((state.get("turn") or {}).get("current_seat", 0))

    public_before = engine.get_public_state()
    private_before = engine.get_private_state(acting_seat)
    legal_before = engine.get_legal_actions(acting_seat)
    dumped = engine.dump_state()

    restored = Engine()
    restored.load_state(dumped)

    assert restored.get_public_state() == public_before
    assert restored.get_private_state(acting_seat) == private_before
    assert restored.get_legal_actions(acting_seat) == legal_before
