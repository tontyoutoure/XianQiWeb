"""M2-UT-04~08 room registry contract tests (RED phase)."""

from __future__ import annotations

import pytest

from app.rooms.registry import RoomFullError
from app.rooms.registry import RoomRegistry


def _ready_count(room) -> int:
    return sum(1 for member in room.members if member.ready)


def _find_member(room, user_id: int):
    for member in room.members:
        if member.user_id == user_id:
            return member
    return None


def test_m2_ut_04_ready_count_consistency() -> None:
    """Input: members toggle ready and one leaves -> Output: ready_count stays correct."""
    registry = RoomRegistry(room_count=3)
    registry.join(room_id=0, user_id=401, username="u401")
    registry.join(room_id=0, user_id=402, username="u402")
    registry.join(room_id=0, user_id=403, username="u403")

    set_ready = getattr(registry, "set_ready", None)
    if set_ready is None:
        pytest.fail("RoomRegistry.set_ready(room_id, user_id, ready) is missing")

    set_ready(room_id=0, user_id=401, ready=True)
    set_ready(room_id=0, user_id=402, ready=True)

    room = registry.get_room(0)
    assert _ready_count(room) == 2

    registry.leave(room_id=0, user_id=402)
    room = registry.get_room(0)
    assert _ready_count(room) == 1
    assert _find_member(room, 401).ready is True


def test_m2_ut_05_join_idempotent_in_same_room() -> None:
    """Input: same user joins same room twice -> Output: no duplicate member and seat stable."""
    registry = RoomRegistry(room_count=3)

    room_first = registry.join(room_id=0, user_id=501, username="u501")
    room_second = registry.join(room_id=0, user_id=501, username="u501")

    assert room_first is room_second
    assert len(room_second.members) == 1
    member = room_second.members[0]
    assert member.user_id == 501
    assert member.seat == 0
    assert room_second.owner_id == 501


def test_m2_ut_06_cross_room_migration_success() -> None:
    """Input: user joins room A then room B -> Output: user exists only in room B."""
    registry = RoomRegistry(room_count=3)

    registry.join(room_id=0, user_id=601, username="migrator")
    registry.join(room_id=0, user_id=602, username="other")

    room_b = registry.join(room_id=1, user_id=601, username="migrator")
    room_a = registry.get_room(0)

    assert _find_member(room_a, 601) is None
    migrated = _find_member(room_b, 601)
    assert migrated is not None
    assert migrated.seat == 0
    assert sum(1 for m in room_b.members if m.user_id == 601) == 1


def test_m2_ut_07_cross_room_migration_atomic_when_target_full() -> None:
    """Input: migrate to full room -> Output: migration fails and source membership kept."""
    registry = RoomRegistry(room_count=3)

    registry.join(room_id=0, user_id=701, username="source-user")
    source_before = registry.get_room(0)
    source_seat = _find_member(source_before, 701).seat

    registry.join(room_id=1, user_id=711, username="b1")
    registry.join(room_id=1, user_id=712, username="b2")
    registry.join(room_id=1, user_id=713, username="b3")

    with pytest.raises(RoomFullError):
        registry.join(room_id=1, user_id=701, username="source-user")

    source_after = registry.get_room(0)
    member = _find_member(source_after, 701)
    assert member is not None
    assert member.seat == source_seat


def test_m2_ut_08_cold_end_reset_on_leave_from_playing_room() -> None:
    """Input: leave from playing room -> Output: waiting state + game cleared + ready reset."""
    registry = RoomRegistry(room_count=3)

    registry.join(room_id=0, user_id=801, username="u801")
    registry.join(room_id=0, user_id=802, username="u802")
    registry.join(room_id=0, user_id=803, username="u803")

    room = registry.get_room(0)
    room.status = "playing"
    room.current_game_id = 99
    chips_before = {member.user_id: member.chips for member in room.members}
    for member in room.members:
        member.ready = True

    room_after = registry.leave(room_id=0, user_id=801)

    assert room_after.status == "waiting"
    assert room_after.current_game_id is None
    assert all(member.ready is False for member in room_after.members)
    assert {member.user_id: member.chips for member in room_after.members} == {
        user_id: chips
        for user_id, chips in chips_before.items()
        if user_id in {802, 803}
    }
