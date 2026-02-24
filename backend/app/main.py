"""FastAPI application entrypoint for M1 auth contracts."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from datetime import timezone
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
from app.core.tokens import AccessTokenExpiredError
from app.core.tokens import AccessTokenInvalidError
from app.core.tokens import decode_access_token
from app.rooms.models import ReadyRequest
from app.rooms.models import GameActionRequest
from app.rooms.registry import MAX_ROOM_MEMBERS
from app.rooms.registry import GameForbiddenError
from app.rooms.registry import GameInvalidActionError
from app.rooms.registry import GameNotFoundError
from app.rooms.registry import GameStateConflictError
from app.rooms.registry import GameVersionConflictError
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
_room_connection_users: dict[Any, int] = {}
WS_PROTOCOL_VERSION = 1


def startup() -> None:
    """Ensure M1 auth tables exist before handling traffic."""
    global room_registry, _lobby_connections, _room_connections, _room_connection_users
    startup_auth_schema(settings)
    room_registry = RoomRegistry(room_count=settings.xqweb_room_count)
    _lobby_connections = set()
    _room_connections = {}
    _room_connection_users = {}


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


def _build_game_public_payload(game_id: int) -> dict[str, Any]:
    game = room_registry.get_game(game_id)
    if not game.seat_to_user_id:
        raise GameNotFoundError(f"game_id={game_id} has no players")
    sample_user_id = next(iter(game.seat_to_user_id.values()))
    state_payload = room_registry.get_game_state_for_user(game_id=game_id, user_id=sample_user_id)
    return {
        "game_id": game_id,
        "public_state": state_payload["public_state"],
    }


def _build_game_private_payload(*, game_id: int, user_id: int) -> dict[str, Any]:
    state_payload = room_registry.get_game_state_for_user(game_id=game_id, user_id=user_id)
    return {
        "game_id": game_id,
        "self_seat": state_payload["self_seat"],
        "private_state": state_payload["private_state"],
        "legal_actions": state_payload["legal_actions"],
    }


def _build_settlement_payload(*, game_id: int, user_id: int) -> dict[str, Any]:
    settlement_payload = room_registry.get_game_settlement_for_user(game_id=game_id, user_id=user_id)
    return {"game_id": game_id, **settlement_payload}


async def _send_game_public_state(websocket: Any, game_id: int) -> None:
    await _ws_send_event(websocket, "GAME_PUBLIC_STATE", _build_game_public_payload(game_id))


async def _send_game_private_state(websocket: Any, *, game_id: int, user_id: int) -> None:
    try:
        payload = _build_game_private_payload(game_id=game_id, user_id=user_id)
    except (GameForbiddenError, GameNotFoundError):
        return
    await _ws_send_event(websocket, "GAME_PRIVATE_STATE", payload)


async def _send_settlement_event(websocket: Any, *, game_id: int, user_id: int) -> None:
    try:
        payload = _build_settlement_payload(game_id=game_id, user_id=user_id)
    except (GameForbiddenError, GameNotFoundError, GameStateConflictError):
        return
    await _ws_send_event(websocket, "SETTLEMENT", payload)


async def _send_room_initial_snapshot(websocket: Any, *, room_id: int, user_id: int) -> None:
    await _send_room_snapshot(websocket, room_id)
    room = room_registry.get_room(room_id)
    game_id = room.current_game_id
    if game_id is None:
        return
    try:
        await _send_game_public_state(websocket, game_id)
    except GameNotFoundError:
        return
    await _send_game_private_state(websocket, game_id=game_id, user_id=user_id)


async def _send_heartbeat_ping(websocket: Any) -> None:
    await _ws_send_event(websocket, "PING", {})


class _HeartbeatState:
    """Track one websocket heartbeat ping/pong lifecycle."""

    def __init__(self) -> None:
        self.last_ping_at: float | None = None
        self.last_pong_at: float | None = None
        self.missed_pong_count = 0
        self._awaiting_pong = False
        self._pong_event = asyncio.Event()

    def mark_ping_sent(self) -> None:
        self.last_ping_at = datetime.now(timezone.utc).timestamp()
        self._awaiting_pong = True
        self._pong_event.clear()

    def mark_pong_received(self) -> None:
        self.last_pong_at = datetime.now(timezone.utc).timestamp()
        if not self._awaiting_pong:
            return
        self._awaiting_pong = False
        self.missed_pong_count = 0
        self._pong_event.set()

    async def wait_for_pong(self, *, timeout_seconds: float) -> bool:
        if not self._awaiting_pong:
            return True
        try:
            await asyncio.wait_for(self._pong_event.wait(), timeout=timeout_seconds)
        except TimeoutError:
            self._awaiting_pong = False
            self.missed_pong_count += 1
            return False
        return True


def _is_pong_message(message: str) -> bool:
    if message == "PONG":
        return True
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return payload.get("type") == "PONG"


def _token_expiry_epoch(access_token: str) -> int | None:
    now = datetime.now(timezone.utc)
    try:
        payload = decode_access_token(access_token, now=now)
    except (AccessTokenInvalidError, AccessTokenExpiredError):
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int):
        return None
    return exp


async def _heartbeat_loop(
    websocket: Any,
    *,
    heartbeat_state: _HeartbeatState,
    interval_seconds: float = 30.0,
    pong_timeout_seconds: float = 10.0,
    max_missed_pongs: int = 2,
) -> None:
    sleep_after_probe = max(interval_seconds - pong_timeout_seconds, 0.0)
    while True:
        await _send_heartbeat_ping(websocket)
        heartbeat_state.mark_ping_sent()
        pong_received = await heartbeat_state.wait_for_pong(timeout_seconds=pong_timeout_seconds)
        if (not pong_received) and heartbeat_state.missed_pong_count >= max_missed_pongs:
            await websocket.close(code=4408, reason="HEARTBEAT_TIMEOUT")
            return
        if sleep_after_probe > 0:
            await asyncio.sleep(sleep_after_probe)


async def _reply_with_pong(websocket: Any) -> None:
    await _ws_send_event(websocket, "PONG", {})


async def _handle_ws_message(*, websocket: Any, heartbeat_state: _HeartbeatState, message: str) -> None:
    if message == "PING":
        await _reply_with_pong(websocket)
        return
    if _is_pong_message(message):
        heartbeat_state.mark_pong_received()


async def _close_ws_on_token_expire(websocket: Any, *, expire_epoch: int) -> None:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    delay_seconds = max(float(expire_epoch - now_ts), 0.0)
    await asyncio.sleep(delay_seconds)
    try:
        await websocket.close(code=4401, reason="UNAUTHORIZED")
    except Exception:
        return


async def _ws_message_loop(websocket: Any, *, token_expire_epoch: int | None = None) -> None:
    heartbeat_state = _HeartbeatState()
    heartbeat_task = asyncio.create_task(_heartbeat_loop(websocket, heartbeat_state=heartbeat_state))
    token_expiry_task: asyncio.Task[Any] | None = None
    if token_expire_epoch is not None:
        token_expiry_task = asyncio.create_task(
            _close_ws_on_token_expire(websocket, expire_epoch=token_expire_epoch)
        )
    try:
        while True:
            message = await websocket.receive_text()
            await _handle_ws_message(websocket=websocket, heartbeat_state=heartbeat_state, message=message)
    except WebSocketDisconnect:
        return
    finally:
        heartbeat_task.cancel()
        if token_expiry_task is not None:
            token_expiry_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        if token_expiry_task is not None:
            try:
                await token_expiry_task
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


async def _broadcast_game_public_state(*, room_id: int, game_id: int) -> None:
    listeners = _room_connections.get(room_id)
    if not listeners:
        return

    stale: list[Any] = []
    for websocket in list(listeners):
        try:
            await _send_game_public_state(websocket, game_id)
        except Exception:
            stale.append(websocket)

    for websocket in stale:
        listeners.discard(websocket)
        _room_connection_users.pop(websocket, None)
    if not listeners:
        _room_connections.pop(room_id, None)


async def _broadcast_game_private_states(*, room_id: int, game_id: int) -> None:
    listeners = _room_connections.get(room_id)
    if not listeners:
        return

    stale: list[Any] = []
    for websocket in list(listeners):
        user_id = _room_connection_users.get(websocket)
        if user_id is None:
            continue
        try:
            await _send_game_private_state(websocket, game_id=game_id, user_id=user_id)
        except Exception:
            stale.append(websocket)

    for websocket in stale:
        listeners.discard(websocket)
        _room_connection_users.pop(websocket, None)
    if not listeners:
        _room_connections.pop(room_id, None)


async def _broadcast_settlement(*, room_id: int, game_id: int) -> None:
    listeners = _room_connections.get(room_id)
    if not listeners:
        return

    stale: list[Any] = []
    for websocket in list(listeners):
        user_id = _room_connection_users.get(websocket)
        if user_id is None:
            continue
        try:
            await _send_settlement_event(websocket, game_id=game_id, user_id=user_id)
        except Exception:
            stale.append(websocket)

    for websocket in stale:
        listeners.discard(websocket)
        _room_connection_users.pop(websocket, None)
    if not listeners:
        _room_connections.pop(room_id, None)


async def _broadcast_game_progress(game_id: int) -> None:
    try:
        game = room_registry.get_game(game_id)
    except GameNotFoundError:
        return

    room_id = int(game.room_id)
    await _broadcast_game_public_state(room_id=room_id, game_id=game_id)
    await _broadcast_game_private_states(room_id=room_id, game_id=game_id)

    if game.phase == "settlement":
        await _broadcast_room_changes([room_id])
        await _broadcast_settlement(room_id=room_id, game_id=game_id)


async def _broadcast_room_changes_then_game_progress(*, room_id: int, game_id: int) -> None:
    """Keep room snapshot and fresh game frames in one ordered push."""
    await _broadcast_room_changes([room_id])
    await _broadcast_game_progress(game_id)


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
    previous_game_id: int | None = None

    try:
        with room_registry.lock_room(room_id):
            room_before = room_registry.get_room(room_id)
            previous_game_id = room_before.current_game_id
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
    started_game_id: int | None = None
    if is_all_ready and not was_all_ready:
        _start_game_hook_if_all_ready(room)
        if room.status == "playing" and room.current_game_id is not None and room.current_game_id != previous_game_id:
            started_game_id = int(room.current_game_id)
    if started_game_id is None:
        _dispatch_async(_broadcast_room_changes([room_id]))
    else:
        _dispatch_async(_broadcast_room_changes_then_game_progress(room_id=room_id, game_id=started_game_id))
    return _room_detail(room)


@app.get("/api/games/{game_id}/state")
def get_game_state(
    game_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    """Return one game snapshot for a room member."""
    user = _require_current_user(authorization)
    user_id = int(user["id"])
    try:
        return room_registry.get_game_state_for_user(game_id=game_id, user_id=user_id)
    except GameNotFoundError:
        _raise_room_error(
            status_code=404,
            code="GAME_NOT_FOUND",
            message="game not found",
            detail={"game_id": game_id},
        )
    except GameForbiddenError:
        _raise_room_error(
            status_code=403,
            code="GAME_FORBIDDEN",
            message="user is not a game member",
            detail={"game_id": game_id, "user_id": user_id},
        )


@app.post("/api/games/{game_id}/actions", status_code=204)
def post_game_action(
    game_id: int,
    payload: GameActionRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    """Apply one action to an in-progress game."""
    user = _require_current_user(authorization)
    user_id = int(user["id"])
    try:
        room_registry.apply_game_action(
            game_id=game_id,
            user_id=user_id,
            action_idx=int(payload.action_idx),
            client_version=payload.client_version,
            cover_list=payload.cover_list,
        )
    except GameNotFoundError:
        _raise_room_error(
            status_code=404,
            code="GAME_NOT_FOUND",
            message="game not found",
            detail={"game_id": game_id},
        )
    except GameForbiddenError:
        _raise_room_error(
            status_code=403,
            code="GAME_FORBIDDEN",
            message="user is not a game member",
            detail={"game_id": game_id, "user_id": user_id},
        )
    except GameVersionConflictError:
        _raise_room_error(
            status_code=409,
            code="GAME_VERSION_CONFLICT",
            message="game version conflict",
            detail={"game_id": game_id},
        )
    except GameInvalidActionError:
        _raise_room_error(
            status_code=409,
            code="GAME_INVALID_ACTION",
            message="game action is invalid",
            detail={"game_id": game_id},
        )
    _dispatch_async(_broadcast_game_progress(game_id))


@app.get("/api/games/{game_id}/settlement")
def get_game_settlement(
    game_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    """Return settlement payload for a room member in settlement phase."""
    user = _require_current_user(authorization)
    user_id = int(user["id"])
    try:
        return room_registry.get_game_settlement_for_user(game_id=game_id, user_id=user_id)
    except GameNotFoundError:
        _raise_room_error(
            status_code=404,
            code="GAME_NOT_FOUND",
            message="game not found",
            detail={"game_id": game_id},
        )
    except GameForbiddenError:
        _raise_room_error(
            status_code=403,
            code="GAME_FORBIDDEN",
            message="user is not a game member",
            detail={"game_id": game_id, "user_id": user_id},
        )
    except GameStateConflictError:
        _raise_room_error(
            status_code=409,
            code="GAME_STATE_CONFLICT",
            message="game state conflict",
            detail={"game_id": game_id},
        )


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
    token_expire_epoch = _token_expiry_epoch(token)
    if token_expire_epoch is None:
        await _close_ws_unauthorized(websocket)
        return

    await websocket.accept()
    _lobby_connections.add(websocket)
    try:
        await _send_lobby_snapshot(websocket)
        await _ws_message_loop(websocket, token_expire_epoch=token_expire_epoch)
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
        user = me(token)
    except HTTPException:
        await _close_ws_unauthorized(websocket)
        return
    token_expire_epoch = _token_expiry_epoch(token)
    if token_expire_epoch is None:
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
    user_id = int(user["id"])
    _room_connection_users[websocket] = user_id
    try:
        await _send_room_initial_snapshot(websocket, room_id=room_id, user_id=user_id)
        await _ws_message_loop(websocket, token_expire_epoch=token_expire_epoch)
    except WebSocketDisconnect:
        return
    finally:
        listeners.discard(websocket)
        _room_connection_users.pop(websocket, None)
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
