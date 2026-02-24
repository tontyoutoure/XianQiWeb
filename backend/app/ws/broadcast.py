"""Snapshot and broadcast helpers for lobby/room/game websocket streams."""

from __future__ import annotations

import asyncio
from typing import Any

import app.runtime as runtime
from app.api.room_views import room_detail
from app.api.room_views import room_summary
from app.rooms.registry import GameForbiddenError
from app.rooms.registry import GameNotFoundError
from app.rooms.registry import GameStateConflictError

from .protocol import ws_send_event


async def send_lobby_snapshot(websocket: Any) -> None:
    rooms = [room_summary(room) for room in runtime.room_registry.list_rooms()]
    await ws_send_event(websocket, "ROOM_LIST", {"rooms": rooms})


async def send_room_snapshot(websocket: Any, room_id: int) -> None:
    room = runtime.room_registry.get_room(room_id)
    await ws_send_event(websocket, "ROOM_UPDATE", {"room": room_detail(room)})


def build_game_public_payload(game_id: int) -> dict[str, Any]:
    game = runtime.room_registry.get_game(game_id)
    if not game.seat_to_user_id:
        raise GameNotFoundError(f"game_id={game_id} has no players")
    sample_user_id = next(iter(game.seat_to_user_id.values()))
    state_payload = runtime.room_registry.get_game_state_for_user(game_id=game_id, user_id=sample_user_id)
    return {
        "game_id": game_id,
        "public_state": state_payload["public_state"],
    }


def build_game_private_payload(*, game_id: int, user_id: int) -> dict[str, Any]:
    state_payload = runtime.room_registry.get_game_state_for_user(game_id=game_id, user_id=user_id)
    return {
        "game_id": game_id,
        "self_seat": state_payload["self_seat"],
        "private_state": state_payload["private_state"],
        "legal_actions": state_payload["legal_actions"],
    }


def build_settlement_payload(*, game_id: int, user_id: int) -> dict[str, Any]:
    settlement_payload = runtime.room_registry.get_game_settlement_for_user(game_id=game_id, user_id=user_id)
    return {"game_id": game_id, **settlement_payload}


async def send_game_public_state(websocket: Any, game_id: int) -> None:
    await ws_send_event(websocket, "GAME_PUBLIC_STATE", build_game_public_payload(game_id))


async def send_game_private_state(websocket: Any, *, game_id: int, user_id: int) -> None:
    try:
        payload = build_game_private_payload(game_id=game_id, user_id=user_id)
    except (GameForbiddenError, GameNotFoundError):
        return
    await ws_send_event(websocket, "GAME_PRIVATE_STATE", payload)


async def send_settlement_event(websocket: Any, *, game_id: int, user_id: int) -> None:
    try:
        payload = build_settlement_payload(game_id=game_id, user_id=user_id)
    except (GameForbiddenError, GameNotFoundError, GameStateConflictError):
        return
    await ws_send_event(websocket, "SETTLEMENT", payload)


async def send_room_initial_snapshot(websocket: Any, *, room_id: int, user_id: int) -> None:
    await send_room_snapshot(websocket, room_id)
    room = runtime.room_registry.get_room(room_id)
    game_id = room.current_game_id
    if game_id is None:
        return
    try:
        await send_game_public_state(websocket, game_id)
    except GameNotFoundError:
        return
    await send_game_private_state(websocket, game_id=game_id, user_id=user_id)


def dispatch_async(coro: Any) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return
    loop.create_task(coro)


async def broadcast_lobby_rooms() -> None:
    stale: list[Any] = []
    for websocket in list(runtime.lobby_connections):
        try:
            await send_lobby_snapshot(websocket)
        except Exception:
            stale.append(websocket)
    for websocket in stale:
        runtime.lobby_connections.discard(websocket)


async def broadcast_room_update(room_id: int) -> None:
    listeners = runtime.room_connections.get(room_id)
    if not listeners:
        return

    stale: list[Any] = []
    for websocket in list(listeners):
        try:
            await send_room_snapshot(websocket, room_id)
        except Exception:
            stale.append(websocket)

    for websocket in stale:
        listeners.discard(websocket)
    if not listeners:
        runtime.room_connections.pop(room_id, None)


async def broadcast_room_changes(room_ids: list[int]) -> None:
    seen: set[int] = set()
    for room_id in room_ids:
        if room_id in seen:
            continue
        seen.add(room_id)
        await broadcast_room_update(room_id)
    await broadcast_lobby_rooms()


async def broadcast_game_public_state(*, room_id: int, game_id: int) -> None:
    listeners = runtime.room_connections.get(room_id)
    if not listeners:
        return

    stale: list[Any] = []
    for websocket in list(listeners):
        try:
            await send_game_public_state(websocket, game_id)
        except Exception:
            stale.append(websocket)

    for websocket in stale:
        listeners.discard(websocket)
        runtime.room_connection_users.pop(websocket, None)
    if not listeners:
        runtime.room_connections.pop(room_id, None)


async def broadcast_game_private_states(*, room_id: int, game_id: int) -> None:
    listeners = runtime.room_connections.get(room_id)
    if not listeners:
        return

    stale: list[Any] = []
    for websocket in list(listeners):
        user_id = runtime.room_connection_users.get(websocket)
        if user_id is None:
            continue
        try:
            await send_game_private_state(websocket, game_id=game_id, user_id=user_id)
        except Exception:
            stale.append(websocket)

    for websocket in stale:
        listeners.discard(websocket)
        runtime.room_connection_users.pop(websocket, None)
    if not listeners:
        runtime.room_connections.pop(room_id, None)


async def broadcast_settlement(*, room_id: int, game_id: int) -> None:
    listeners = runtime.room_connections.get(room_id)
    if not listeners:
        return

    stale: list[Any] = []
    for websocket in list(listeners):
        user_id = runtime.room_connection_users.get(websocket)
        if user_id is None:
            continue
        try:
            await send_settlement_event(websocket, game_id=game_id, user_id=user_id)
        except Exception:
            stale.append(websocket)

    for websocket in stale:
        listeners.discard(websocket)
        runtime.room_connection_users.pop(websocket, None)
    if not listeners:
        runtime.room_connections.pop(room_id, None)


async def broadcast_game_progress(game_id: int) -> None:
    try:
        game = runtime.room_registry.get_game(game_id)
    except GameNotFoundError:
        return

    room_id = int(game.room_id)
    await broadcast_game_public_state(room_id=room_id, game_id=game_id)
    await broadcast_game_private_states(room_id=room_id, game_id=game_id)

    if game.phase == "settlement":
        await broadcast_room_changes([room_id])
        await broadcast_settlement(room_id=room_id, game_id=game_id)


async def broadcast_room_changes_then_game_progress(*, room_id: int, game_id: int) -> None:
    """Keep room snapshot and fresh game frames in one ordered push."""
    await broadcast_room_changes([room_id])
    await broadcast_game_progress(game_id)
