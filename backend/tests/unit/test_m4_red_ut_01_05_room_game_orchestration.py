"""M4-UT-01~05 room/game orchestration contract tests (RED phase)."""

from __future__ import annotations

import pytest

from app.rooms.registry import RoomNotWaitingError
from app.rooms.registry import RoomRegistry


def _seed_three_members(registry: RoomRegistry) -> list[int]:
    user_ids = [4101, 4102, 4103]
    for user_id in user_ids:
        registry.join(room_id=0, user_id=user_id, username=f"u{user_id}")
    return user_ids


def _set_all_ready(registry: RoomRegistry, user_ids: list[int]) -> None:
    for user_id in user_ids:
        registry.set_ready(room_id=0, user_id=user_id, ready=True)


def _require_get_game(registry: RoomRegistry):
    get_game = getattr(registry, "get_game", None)
    if get_game is None:
        pytest.fail("RoomRegistry.get_game(game_id) is missing for M4 game lifecycle")
    return get_game


def _require_mark_game_settlement(registry: RoomRegistry):
    mark_game_settlement = getattr(registry, "mark_game_settlement", None)
    if mark_game_settlement is None:
        pytest.fail(
            "RoomRegistry.mark_game_settlement(game_id) is missing for M4 settlement transition"
        )
    return mark_game_settlement


def test_m4_ut_01_all_ready_transition_starts_game() -> None:
    """Input: third ready=true -> Output: room enters playing with non-empty current_game_id."""
    registry = RoomRegistry(room_count=3)
    user_ids = _seed_three_members(registry)

    registry.set_ready(room_id=0, user_id=user_ids[0], ready=True)
    registry.set_ready(room_id=0, user_id=user_ids[1], ready=True)
    room_before = registry.get_room(0)
    assert room_before.status == "waiting"
    assert room_before.current_game_id is None

    registry.set_ready(room_id=0, user_id=user_ids[2], ready=True)
    room_after = registry.get_room(0)
    assert room_after.status == "playing"
    assert room_after.current_game_id is not None


def test_m4_ut_02_seat_mapping_is_bidirectional_and_covers_three_seats() -> None:
    """Input: game created from room members -> Output: seat/user maps are reversible for 0/1/2."""
    registry = RoomRegistry(room_count=3)
    user_ids = _seed_three_members(registry)

    _set_all_ready(registry, user_ids)
    room = registry.get_room(0)
    assert room.current_game_id is not None

    get_game = _require_get_game(registry)
    game = get_game(room.current_game_id)

    assert game.seat_to_user_id == {0: user_ids[0], 1: user_ids[1], 2: user_ids[2]}
    assert game.user_id_to_seat == {user_id: seat for seat, user_id in game.seat_to_user_id.items()}
    assert set(game.seat_to_user_id) == {0, 1, 2}


def test_m4_ut_03_leave_from_playing_marks_game_aborted_and_clears_room_current_game() -> None:
    """Input: leave during playing -> Output: game aborted + room waiting/current_game_id cleared."""
    registry = RoomRegistry(room_count=3)
    user_ids = _seed_three_members(registry)

    _set_all_ready(registry, user_ids)
    room_before = registry.get_room(0)
    game_id = room_before.current_game_id
    assert game_id is not None

    room_after = registry.leave(room_id=0, user_id=user_ids[0])
    assert room_after.status == "waiting"
    assert room_after.current_game_id is None

    get_game = _require_get_game(registry)
    game = get_game(game_id)
    assert game.status == "aborted"


def test_m4_ut_04_entering_settlement_resets_all_member_ready_flags() -> None:
    """Input: game enters settlement -> Output: all three room members ready=false."""
    registry = RoomRegistry(room_count=3)
    user_ids = _seed_three_members(registry)

    _set_all_ready(registry, user_ids)
    room = registry.get_room(0)
    game_id = room.current_game_id
    assert game_id is not None

    mark_game_settlement = _require_mark_game_settlement(registry)
    mark_game_settlement(game_id=game_id)

    room_after = registry.get_room(0)
    assert room_after.status == "settlement"
    assert all(member.ready is False for member in room_after.members)


def test_m4_ut_05_settlement_ready_transition_to_all_ready_starts_only_one_new_game() -> None:
    """Input: settlement room re-ready from partial->all -> Output: one new game starts exactly once."""
    registry = RoomRegistry(room_count=3)
    user_ids = _seed_three_members(registry)

    _set_all_ready(registry, user_ids)
    first_game_id = registry.get_room(0).current_game_id
    assert first_game_id is not None

    mark_game_settlement = _require_mark_game_settlement(registry)
    mark_game_settlement(game_id=first_game_id)

    registry.set_ready(room_id=0, user_id=user_ids[0], ready=True)
    registry.set_ready(room_id=0, user_id=user_ids[0], ready=True)
    registry.set_ready(room_id=0, user_id=user_ids[1], ready=True)
    registry.set_ready(room_id=0, user_id=user_ids[2], ready=True)

    room_after_restart = registry.get_room(0)
    second_game_id = room_after_restart.current_game_id

    assert room_after_restart.status == "playing"
    assert second_game_id is not None
    assert second_game_id != first_game_id

    with pytest.raises(RoomNotWaitingError):
        registry.set_ready(room_id=0, user_id=user_ids[2], ready=True)

    assert registry.get_room(0).current_game_id == second_game_id
