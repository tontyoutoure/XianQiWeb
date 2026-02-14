"""M2-UT-01~03 room registry contract tests (RED phase)."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

import pytest


def _load_rooms_module() -> ModuleType:
    """Load the M2 room domain module; fail clearly if not implemented yet."""
    try:
        return import_module("app.rooms.registry")
    except ModuleNotFoundError as exc:
        pytest.fail(f"M2 room module is not implemented yet: {exc}")


def _new_registry(room_count: int = 3):
    module = _load_rooms_module()
    room_registry_cls = getattr(module, "RoomRegistry", None)
    if room_registry_cls is None:
        pytest.fail("RoomRegistry class is missing in app.rooms.registry")
    return room_registry_cls(room_count=room_count)


def _get_room(registry, room_id: int):
    get_room = getattr(registry, "get_room", None)
    if get_room is None:
        pytest.fail("RoomRegistry.get_room(room_id) is missing")
    return get_room(room_id)


def test_m2_ut_01_preset_room_initialization() -> None:
    """Input: room_count=4 -> Output: rooms id=0..3 in waiting defaults."""
    registry = _new_registry(room_count=4)

    for room_id in range(4):
        room = _get_room(registry, room_id)
        assert room.room_id == room_id
        assert room.status == "waiting"
        assert room.owner_id is None
        assert room.current_game_id is None
        assert room.members == []


def test_m2_ut_02_seat_assignment_and_recycle() -> None:
    """Input: join/join/join/leave/join -> Output: seats 0,1,2 then recycled 1."""
    registry = _new_registry()

    room_after_u1 = registry.join(room_id=0, user_id=101, username="u1")
    room_after_u2 = registry.join(room_id=0, user_id=102, username="u2")
    room_after_u3 = registry.join(room_id=0, user_id=103, username="u3")

    seat_by_user = {member.user_id: member.seat for member in room_after_u3.members}
    assert seat_by_user == {101: 0, 102: 1, 103: 2}

    registry.leave(room_id=0, user_id=102)
    room_after_u4 = registry.join(room_id=0, user_id=104, username="u4")
    seat_by_user = {member.user_id: member.seat for member in room_after_u4.members}

    assert seat_by_user[104] == 1
    assert sorted(seat_by_user.values()) == [0, 1, 2]
    assert room_after_u1 is not None and room_after_u2 is not None


def test_m2_ut_03_owner_assignment_and_transfer() -> None:
    """Input: owner leaves repeatedly -> Output: owner moves to earliest joined member."""
    registry = _new_registry()

    room = registry.join(room_id=0, user_id=201, username="owner")
    assert room.owner_id == 201

    registry.join(room_id=0, user_id=202, username="second")
    registry.join(room_id=0, user_id=203, username="third")

    room = registry.leave(room_id=0, user_id=201)
    assert room.owner_id == 202

    room = registry.leave(room_id=0, user_id=202)
    assert room.owner_id == 203

    room = registry.leave(room_id=0, user_id=203)
    assert room.owner_id is None
    assert room.members == []
