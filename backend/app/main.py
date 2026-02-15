"""FastAPI application entrypoint for M1 auth contracts."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
from typing import Any

from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.auth.errors import raise_token_invalid
from app.auth.http import handle_http_exception
from app.auth.http import api_error
from app.auth.models import LogoutRequest
from app.auth.models import LoginRequest
from app.auth.models import RefreshRequest
from app.auth.models import RegisterRequest
from app.auth.service import login_user
from app.auth.service import logout_user
from app.auth.service import me_user
from app.auth.service import refresh_user
from app.auth.service import register_user
from app.auth.service import startup_auth_schema
from app.core.config import Settings
from app.core.config import load_settings
from app.rooms.models import ReadyRequest
from app.rooms.registry import MAX_ROOM_MEMBERS
from app.rooms.registry import Room
from app.rooms.registry import RoomFullError
from app.rooms.registry import RoomMember
from app.rooms.registry import RoomNotFoundError
from app.rooms.registry import RoomNotMemberError
from app.rooms.registry import RoomNotWaitingError
from app.rooms.registry import RoomRegistry

settings = load_settings()
room_registry = RoomRegistry(room_count=settings.xqweb_room_count)
_lobby_connections: set[Any] = set()
_room_connections: dict[int, set[Any]] = {}
WS_PROTOCOL_VERSION = 1


def startup() -> None:
    """Ensure M1 auth tables exist before handling traffic."""
    global room_registry, _lobby_connections, _room_connections
    startup_auth_schema(settings)
    room_registry = RoomRegistry(room_count=settings.xqweb_room_count)
    _lobby_connections = set()
    _room_connections = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    startup()
    yield


app = FastAPI(lifespan=lifespan)


def _require_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    if authorization is None:
        raise_token_invalid()

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise_token_invalid()
    return me(token)


def _room_summary(room: Room) -> dict[str, object]:
    return {
        "room_id": room.room_id,
        "status": room.status,
        "player_count": len(room.members),
        "ready_count": sum(1 for member in room.members if member.ready),
    }


def _room_member_detail(member: RoomMember) -> dict[str, object]:
    return {
        "user_id": member.user_id,
        "username": member.username,
        "seat": member.seat,
        "ready": member.ready,
        "chips": member.chips,
    }


def _room_detail(room: Room) -> dict[str, object]:
    return {
        "room_id": room.room_id,
        "status": room.status,
        "owner_id": room.owner_id,
        "members": [_room_member_detail(member) for member in room.members],
        "current_game_id": room.current_game_id,
    }


def _raise_room_error(
    *,
    status_code: int,
    code: str,
    message: str,
    detail: dict[str, Any],
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=api_error(code=code, message=message, detail=detail),
    )


def _start_game_hook_if_all_ready(room: Room) -> None:
    # M2 keeps this as a hook placeholder until game-engine integration in M3+.
    if len(room.members) != MAX_ROOM_MEMBERS:
        return
    if not all(member.ready for member in room.members):
        return


def _ws_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"v": WS_PROTOCOL_VERSION, "type": event_type, "payload": payload}


async def _ws_send_event(websocket: Any, event_type: str, payload: dict[str, Any]) -> None:
    message = _ws_event(event_type, payload)
    if hasattr(websocket, "send_json"):
        await websocket.send_json(message)
        return
    if hasattr(websocket, "send_text"):
        await websocket.send_text(json.dumps(message))


async def _send_lobby_snapshot(websocket: Any) -> None:
    rooms = [_room_summary(room) for room in room_registry.list_rooms()]
    await _ws_send_event(websocket, "ROOM_LIST", {"rooms": rooms})


async def _send_room_snapshot(websocket: Any, room_id: int) -> None:
    room = room_registry.get_room(room_id)
    await _ws_send_event(websocket, "ROOM_UPDATE", {"room": _room_detail(room)})


async def _send_heartbeat_ping(websocket: Any) -> None:
    await _ws_send_event(websocket, "PING", {})


async def _heartbeat_loop(websocket: Any, interval_seconds: float = 30.0) -> None:
    await _send_heartbeat_ping(websocket)
    while True:
        await asyncio.sleep(interval_seconds)
        await _send_heartbeat_ping(websocket)


async def _ws_message_loop(websocket: Any) -> None:
    heartbeat_task = asyncio.create_task(_heartbeat_loop(websocket))
    try:
        while True:
            message = await websocket.receive_text()
            if message == "PING":
                await _ws_send_event(websocket, "PONG", {})
    except WebSocketDisconnect:
        return
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


def _dispatch_async(coro: Any) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return
    loop.create_task(coro)


async def _broadcast_lobby_rooms() -> None:
    stale: list[Any] = []
    for websocket in list(_lobby_connections):
        try:
            await _send_lobby_snapshot(websocket)
        except Exception:
            stale.append(websocket)
    for websocket in stale:
        _lobby_connections.discard(websocket)


async def _broadcast_room_update(room_id: int) -> None:
    listeners = _room_connections.get(room_id)
    if not listeners:
        return

    stale: list[Any] = []
    for websocket in list(listeners):
        try:
            await _send_room_snapshot(websocket, room_id)
        except Exception:
            stale.append(websocket)

    for websocket in stale:
        listeners.discard(websocket)
    if not listeners:
        _room_connections.pop(room_id, None)


async def _broadcast_room_changes(room_ids: list[int]) -> None:
    seen: set[int] = set()
    for room_id in room_ids:
        if room_id in seen:
            continue
        seen.add(room_id)
        await _broadcast_room_update(room_id)
    await _broadcast_lobby_rooms()


@app.exception_handler(HTTPException)
async def handle_http_exception_route(request: Request, exc: HTTPException) -> JSONResponse:
    """Adapter used by FastAPI exception handling."""
    return await handle_http_exception(request, exc)


@app.post("/api/auth/register")
def register(payload: RegisterRequest) -> dict[str, object]:
    """Create user + auth session for MVP register flow."""
    return register_user(settings=settings, payload=payload)


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, object]:
    """Authenticate user and issue a fresh auth session."""
    return login_user(settings=settings, payload=payload)


def me(access_token: str) -> dict[str, object]:
    """Return current user profile for a valid access token."""
    return me_user(settings=settings, access_token=access_token)


@app.get("/api/rooms")
def list_rooms(authorization: str | None = Header(default=None, alias="Authorization")) -> list[dict[str, object]]:
    """Return lobby room summary list."""
    _require_current_user(authorization)
    return [_room_summary(room) for room in room_registry.list_rooms()]


@app.get("/api/rooms/{room_id}")
def get_room_detail(
    room_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    """Return one room detail."""
    _require_current_user(authorization)
    try:
        room = room_registry.get_room(room_id)
    except RoomNotFoundError:
        _raise_room_error(
            status_code=404,
            code="ROOM_NOT_FOUND",
            message="room not found",
            detail={"room_id": room_id},
        )
    return _room_detail(room)


@app.post("/api/rooms/{room_id}/join")
def join_room(
    room_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    """Join target room."""
    user = _require_current_user(authorization)
    user_id = int(user["id"])
    username = str(user["username"])
    previous_room_id = room_registry.find_room_id_by_user(user_id)
    lock_room_ids = [room_id]
    if previous_room_id is not None and previous_room_id != room_id:
        lock_room_ids.append(previous_room_id)

    try:
        with room_registry.lock_rooms(lock_room_ids):
            previous_room_id = room_registry.find_room_id_by_user(user_id)
            room = room_registry.join(room_id=room_id, user_id=user_id, username=username)
    except RoomNotFoundError:
        _raise_room_error(
            status_code=404,
            code="ROOM_NOT_FOUND",
            message="room not found",
            detail={"room_id": room_id},
        )
    except RoomFullError:
        _raise_room_error(
            status_code=409,
            code="ROOM_FULL",
            message="room is full",
            detail={"room_id": room_id},
        )
    changed_room_ids = [room_id]
    if previous_room_id is not None and previous_room_id != room_id:
        changed_room_ids.append(previous_room_id)
    _dispatch_async(_broadcast_room_changes(changed_room_ids))
    return _room_detail(room)


@app.post("/api/rooms/{room_id}/leave")
def leave_room(
    room_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, bool]:
    """Leave one room."""
    user = _require_current_user(authorization)
    user_id = int(user["id"])

    try:
        with room_registry.lock_room(room_id):
            room_registry.leave(room_id=room_id, user_id=user_id)
    except RoomNotFoundError:
        _raise_room_error(
            status_code=404,
            code="ROOM_NOT_FOUND",
            message="room not found",
            detail={"room_id": room_id},
        )
    except RoomNotMemberError:
        _raise_room_error(
            status_code=403,
            code="ROOM_NOT_MEMBER",
            message="user is not a room member",
            detail={"room_id": room_id, "user_id": user_id},
        )
    _dispatch_async(_broadcast_room_changes([room_id]))
    return {"ok": True}


@app.post("/api/rooms/{room_id}/ready")
def set_room_ready(
    room_id: int,
    payload: ReadyRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    """Update room ready state."""
    user = _require_current_user(authorization)
    user_id = int(user["id"])
    was_all_ready = False

    try:
        with room_registry.lock_room(room_id):
            room_before = room_registry.get_room(room_id)
            was_all_ready = (
                len(room_before.members) == MAX_ROOM_MEMBERS
                and all(member.ready for member in room_before.members)
            )
            room = room_registry.set_ready(room_id=room_id, user_id=user_id, ready=payload.ready)
    except RoomNotFoundError:
        _raise_room_error(
            status_code=404,
            code="ROOM_NOT_FOUND",
            message="room not found",
            detail={"room_id": room_id},
        )
    except RoomNotMemberError:
        _raise_room_error(
            status_code=403,
            code="ROOM_NOT_MEMBER",
            message="user is not a room member",
            detail={"room_id": room_id, "user_id": user_id},
        )
    except RoomNotWaitingError:
        _raise_room_error(
            status_code=409,
            code="ROOM_NOT_WAITING",
            message="room is not in waiting status",
            detail={"room_id": room_id},
        )
    is_all_ready = len(room.members) == MAX_ROOM_MEMBERS and all(member.ready for member in room.members)
    if is_all_ready and not was_all_ready:
        _start_game_hook_if_all_ready(room)
    _dispatch_async(_broadcast_room_changes([room_id]))
    return _room_detail(room)


async def _close_ws_unauthorized(websocket: WebSocket) -> None:
    """Close websocket with unified unauthorized semantics."""
    await websocket.accept()
    await websocket.close(code=4401, reason="UNAUTHORIZED")


@app.post("/api/auth/refresh")
def refresh(payload: RefreshRequest) -> dict[str, object]:
    """Rotate refresh token and issue a new access/refresh pair."""
    return refresh_user(settings=settings, payload=payload)


@app.post("/api/auth/logout")
def logout(payload: LogoutRequest) -> dict[str, bool]:
    """Revoke the provided refresh token idempotently."""
    return logout_user(settings=settings, payload=payload)


@app.get("/api/auth/me")
def me_route(authorization: str | None = Header(default=None, alias="Authorization")) -> dict[str, object]:
    """HTTP wrapper for /api/auth/me Bearer auth."""
    return _require_current_user(authorization)


@app.websocket("/ws/lobby")
async def ws_lobby(websocket: WebSocket) -> None:
    """Lobby websocket: auth + initial ROOM_LIST + incremental room updates."""
    token = websocket.query_params.get("token")
    if token is None or token == "":
        await _close_ws_unauthorized(websocket)
        return

    try:
        me(token)
    except HTTPException:
        await _close_ws_unauthorized(websocket)
        return

    await websocket.accept()
    _lobby_connections.add(websocket)
    try:
        await _send_lobby_snapshot(websocket)
        await _ws_message_loop(websocket)
    except WebSocketDisconnect:
        return
    finally:
        _lobby_connections.discard(websocket)


@app.websocket("/ws/rooms/{room_id}")
async def ws_room(websocket: WebSocket, room_id: int) -> None:
    """Room websocket: auth + initial ROOM_UPDATE + incremental room updates."""
    token = websocket.query_params.get("token")
    if token is None or token == "":
        await _close_ws_unauthorized(websocket)
        return

    try:
        me(token)
    except HTTPException:
        await _close_ws_unauthorized(websocket)
        return

    try:
        room_registry.get_room(room_id)
    except RoomNotFoundError:
        await websocket.accept()
        await websocket.close(code=4404, reason="ROOM_NOT_FOUND")
        return

    await websocket.accept()
    listeners = _room_connections.setdefault(room_id, set())
    listeners.add(websocket)
    try:
        await _send_room_snapshot(websocket, room_id)
        await _ws_message_loop(websocket)
    except WebSocketDisconnect:
        return
    finally:
        listeners.discard(websocket)
        if not listeners:
            _room_connections.pop(room_id, None)


__all__ = [
    "Settings",
    "RegisterRequest",
    "LoginRequest",
    "LogoutRequest",
    "RefreshRequest",
    "app",
    "handle_http_exception",
    "login",
    "logout",
    "me",
    "refresh",
    "register",
    "settings",
    "startup",
    "ws_lobby",
    "ws_room",
]
