"""WebSocket route handlers for lobby and room channels."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import WebSocket
from fastapi import WebSocketDisconnect

import app.runtime as runtime
from app.api.deps import me
from app.rooms.registry import RoomNotFoundError

from .broadcast import send_lobby_snapshot
from .broadcast import send_room_initial_snapshot
from .heartbeat import token_expiry_epoch
from .heartbeat import ws_message_loop

router = APIRouter()


async def close_ws_unauthorized(websocket: WebSocket) -> None:
    """Close websocket with unified unauthorized semantics."""
    await websocket.accept()
    await websocket.close(code=4401, reason="UNAUTHORIZED")


@router.websocket("/ws/lobby")
async def ws_lobby(websocket: WebSocket) -> None:
    """Lobby websocket: auth + initial ROOM_LIST + incremental room updates."""
    token = websocket.query_params.get("token")
    if token is None or token == "":
        await close_ws_unauthorized(websocket)
        return

    try:
        me(token)
    except HTTPException:
        await close_ws_unauthorized(websocket)
        return
    token_expire = token_expiry_epoch(token)
    if token_expire is None:
        await close_ws_unauthorized(websocket)
        return

    await websocket.accept()
    runtime.lobby_connections.add(websocket)
    try:
        await send_lobby_snapshot(websocket)
        await ws_message_loop(websocket, token_expire_epoch_value=token_expire)
    except WebSocketDisconnect:
        return
    finally:
        runtime.lobby_connections.discard(websocket)


@router.websocket("/ws/rooms/{room_id}")
async def ws_room(websocket: WebSocket, room_id: int) -> None:
    """Room websocket: auth + initial ROOM_UPDATE + incremental room updates."""
    token = websocket.query_params.get("token")
    if token is None or token == "":
        await close_ws_unauthorized(websocket)
        return

    try:
        user = me(token)
    except HTTPException:
        await close_ws_unauthorized(websocket)
        return
    token_expire = token_expiry_epoch(token)
    if token_expire is None:
        await close_ws_unauthorized(websocket)
        return

    try:
        runtime.room_registry.get_room(room_id)
    except RoomNotFoundError:
        await websocket.accept()
        await websocket.close(code=4404, reason="ROOM_NOT_FOUND")
        return

    await websocket.accept()
    listeners = runtime.room_connections.setdefault(room_id, set())
    listeners.add(websocket)
    user_id = int(user["id"])
    runtime.room_connection_users[websocket] = user_id
    try:
        await send_room_initial_snapshot(websocket, room_id=room_id, user_id=user_id)
        await ws_message_loop(websocket, token_expire_epoch_value=token_expire)
    except WebSocketDisconnect:
        return
    finally:
        listeners.discard(websocket)
        runtime.room_connection_users.pop(websocket, None)
        if not listeners:
            runtime.room_connections.pop(room_id, None)
