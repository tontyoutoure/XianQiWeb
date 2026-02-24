"""Room REST routes."""

from __future__ import annotations

import sys
from collections.abc import Callable

from fastapi import APIRouter
from fastapi import Header

import app.runtime as runtime
from app.api.deps import require_current_user
from app.api.errors import raise_api_error
from app.api.room_views import room_detail
from app.api.room_views import room_summary
from app.rooms.models import ReadyRequest
from app.rooms.registry import MAX_ROOM_MEMBERS
from app.rooms.registry import Room
from app.rooms.registry import RoomFullError
from app.rooms.registry import RoomNotFoundError
from app.rooms.registry import RoomNotMemberError
from app.rooms.registry import RoomNotWaitingError
from app.ws.broadcast import broadcast_room_changes
from app.ws.broadcast import broadcast_room_changes_then_game_progress
from app.ws.broadcast import dispatch_async

router = APIRouter()


def _start_game_hook_if_all_ready(room: Room) -> None:
    # M2 keeps this as a hook placeholder until game-engine integration in M3+.
    if len(room.members) != MAX_ROOM_MEMBERS:
        return
    if not all(member.ready for member in room.members):
        return


def _resolve_start_game_hook() -> Callable[[Room], None]:
    """Keep backward-compatible monkeypatch hook via app.main for legacy tests."""
    main_module = sys.modules.get("app.main")
    if main_module is None:
        return _start_game_hook_if_all_ready
    candidate = getattr(main_module, "_start_game_hook_if_all_ready", None)
    if callable(candidate):
        return candidate
    return _start_game_hook_if_all_ready


@router.get("/api/rooms")
def list_rooms(authorization: str | None = Header(default=None, alias="Authorization")) -> list[dict[str, object]]:
    """Return lobby room summary list."""
    require_current_user(authorization)
    return [room_summary(room) for room in runtime.room_registry.list_rooms()]


@router.get("/api/rooms/{room_id}")
def get_room_detail(
    room_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    """Return one room detail."""
    require_current_user(authorization)
    try:
        room = runtime.room_registry.get_room(room_id)
    except RoomNotFoundError:
        raise_api_error(
            status_code=404,
            code="ROOM_NOT_FOUND",
            message="room not found",
            detail={"room_id": room_id},
        )
    return room_detail(room)


@router.post("/api/rooms/{room_id}/join")
def join_room(
    room_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    """Join target room."""
    user = require_current_user(authorization)
    user_id = int(user["id"])
    username = str(user["username"])
    previous_room_id = runtime.room_registry.find_room_id_by_user(user_id)
    lock_room_ids = [room_id]
    if previous_room_id is not None and previous_room_id != room_id:
        lock_room_ids.append(previous_room_id)

    try:
        with runtime.room_registry.lock_rooms(lock_room_ids):
            previous_room_id = runtime.room_registry.find_room_id_by_user(user_id)
            room = runtime.room_registry.join(room_id=room_id, user_id=user_id, username=username)
    except RoomNotFoundError:
        raise_api_error(
            status_code=404,
            code="ROOM_NOT_FOUND",
            message="room not found",
            detail={"room_id": room_id},
        )
    except RoomFullError:
        raise_api_error(
            status_code=409,
            code="ROOM_FULL",
            message="room is full",
            detail={"room_id": room_id},
        )
    changed_room_ids = [room_id]
    if previous_room_id is not None and previous_room_id != room_id:
        changed_room_ids.append(previous_room_id)
    dispatch_async(broadcast_room_changes(changed_room_ids))
    return room_detail(room)


@router.post("/api/rooms/{room_id}/leave")
def leave_room(
    room_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, bool]:
    """Leave one room."""
    user = require_current_user(authorization)
    user_id = int(user["id"])

    try:
        with runtime.room_registry.lock_room(room_id):
            runtime.room_registry.leave(room_id=room_id, user_id=user_id)
    except RoomNotFoundError:
        raise_api_error(
            status_code=404,
            code="ROOM_NOT_FOUND",
            message="room not found",
            detail={"room_id": room_id},
        )
    except RoomNotMemberError:
        raise_api_error(
            status_code=403,
            code="ROOM_NOT_MEMBER",
            message="user is not a room member",
            detail={"room_id": room_id, "user_id": user_id},
        )
    dispatch_async(broadcast_room_changes([room_id]))
    return {"ok": True}


@router.post("/api/rooms/{room_id}/ready")
def set_room_ready(
    room_id: int,
    payload: ReadyRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    """Update room ready state."""
    user = require_current_user(authorization)
    user_id = int(user["id"])
    was_all_ready = False
    previous_game_id: int | None = None

    try:
        with runtime.room_registry.lock_room(room_id):
            room_before = runtime.room_registry.get_room(room_id)
            previous_game_id = room_before.current_game_id
            was_all_ready = (
                len(room_before.members) == MAX_ROOM_MEMBERS
                and all(member.ready for member in room_before.members)
            )
            room = runtime.room_registry.set_ready(room_id=room_id, user_id=user_id, ready=payload.ready)
    except RoomNotFoundError:
        raise_api_error(
            status_code=404,
            code="ROOM_NOT_FOUND",
            message="room not found",
            detail={"room_id": room_id},
        )
    except RoomNotMemberError:
        raise_api_error(
            status_code=403,
            code="ROOM_NOT_MEMBER",
            message="user is not a room member",
            detail={"room_id": room_id, "user_id": user_id},
        )
    except RoomNotWaitingError:
        raise_api_error(
            status_code=409,
            code="ROOM_NOT_WAITING",
            message="room is not in waiting status",
            detail={"room_id": room_id},
        )
    is_all_ready = len(room.members) == MAX_ROOM_MEMBERS and all(member.ready for member in room.members)
    started_game_id: int | None = None
    if is_all_ready and not was_all_ready:
        _resolve_start_game_hook()(room)
        if room.status == "playing" and room.current_game_id is not None and room.current_game_id != previous_game_id:
            started_game_id = int(room.current_game_id)
    if started_game_id is None:
        dispatch_async(broadcast_room_changes([room_id]))
    else:
        dispatch_async(broadcast_room_changes_then_game_progress(room_id=room_id, game_id=started_game_id))
    return room_detail(room)
