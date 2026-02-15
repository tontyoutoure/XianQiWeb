"""Red-phase WebSocket tests against a live M2 backend service (Rooms WS 06~10)."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from collections.abc import Generator
from pathlib import Path
from typing import Any

import httpx
import pytest
import websockets
from tests.integration.real_service.live_server import run_live_server

JWT_SECRET = "m2-rs-red-test-secret-key-32-bytes-minimum"
ROOM_COUNT = 3


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[tuple[str, str], None, None]:
    """Start a real uvicorn process for one test case."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m2_rs_ws_06_10_red.sqlite3",
        jwt_secret=JWT_SECRET,
        env_overrides={"XQWEB_ROOM_COUNT": str(ROOM_COUNT)},
    ) as server:
        yield server.base_url, server.ws_base_url


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_user(*, base_url: str, username: str) -> tuple[int, str]:
    """Register one user and return (user_id, access_token)."""
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(
            "/api/auth/register",
            json={"username": username, "password": "123"},
        )
    assert response.status_code == 200
    payload = response.json()
    return int(payload["user"]["id"]), str(payload["access_token"])


def _join_room(*, base_url: str, token: str, room_id: int) -> dict[str, Any]:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(f"/api/rooms/{room_id}/join", headers=_headers(token))
    assert response.status_code == 200
    return dict(response.json())


def _ready_room(*, base_url: str, token: str, room_id: int, ready: bool) -> dict[str, Any]:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(
            f"/api/rooms/{room_id}/ready",
            headers=_headers(token),
            json={"ready": ready},
        )
    assert response.status_code == 200
    return dict(response.json())


def _leave_room(*, base_url: str, token: str, room_id: int) -> None:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(f"/api/rooms/{room_id}/leave", headers=_headers(token))
    assert response.status_code == 200
    assert response.json() == {"ok": True}


async def _recv_until(
    ws: Any,
    *,
    event_type: str,
    timeout_seconds: float = 5.0,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    """Receive websocket JSON events until matching type/predicate appears."""
    deadline = time.monotonic() + timeout_seconds

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(f"timeout waiting for event_type={event_type}")

        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        event = dict(json.loads(raw))

        if event.get("type") != event_type:
            continue
        if predicate is not None and not predicate(event):
            continue
        return event


def test_m2_rs_ws_06_join_triggers_lobby_and_room_updates(live_server: tuple[str, str]) -> None:
    """M2-RS-WS-06: join should push ROOM_LIST and ROOM_UPDATE."""
    base_url, ws_base_url = live_server
    _, listener_token = _register_user(base_url=base_url, username="r2ws06l")
    actor_id, actor_token = _register_user(base_url=base_url, username="r2ws06a")

    async def _run() -> None:
        async with (
            websockets.connect(
                f"{ws_base_url}/ws/lobby?token={listener_token}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as lobby_ws,
            websockets.connect(
                f"{ws_base_url}/ws/rooms/0?token={listener_token}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as room_ws,
        ):
            await _recv_until(lobby_ws, event_type="ROOM_LIST")
            await _recv_until(room_ws, event_type="ROOM_UPDATE")

            await asyncio.to_thread(_join_room, base_url=base_url, token=actor_token, room_id=0)

            lobby_event = await _recv_until(
                lobby_ws,
                event_type="ROOM_LIST",
                predicate=lambda event: any(
                    room["room_id"] == 0 and room["player_count"] >= 1
                    for room in event["payload"]["rooms"]
                ),
            )
            room_event = await _recv_until(
                room_ws,
                event_type="ROOM_UPDATE",
                predicate=lambda event: any(
                    member["user_id"] == actor_id for member in event["payload"]["room"]["members"]
                ),
            )

            assert any(
                room["room_id"] == 0 and room["player_count"] >= 1
                for room in lobby_event["payload"]["rooms"]
            )
            assert any(member["user_id"] == actor_id for member in room_event["payload"]["room"]["members"])

    asyncio.run(_run())


def test_m2_rs_ws_07_ready_triggers_lobby_and_room_updates(live_server: tuple[str, str]) -> None:
    """M2-RS-WS-07: ready should push ROOM_LIST and ROOM_UPDATE."""
    base_url, ws_base_url = live_server
    actor_id, actor_token = _register_user(base_url=base_url, username="r2ws07a")
    _join_room(base_url=base_url, token=actor_token, room_id=0)

    async def _run() -> None:
        async with (
            websockets.connect(
                f"{ws_base_url}/ws/lobby?token={actor_token}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as lobby_ws,
            websockets.connect(
                f"{ws_base_url}/ws/rooms/0?token={actor_token}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as room_ws,
        ):
            await _recv_until(lobby_ws, event_type="ROOM_LIST")
            await _recv_until(room_ws, event_type="ROOM_UPDATE")

            await asyncio.to_thread(_ready_room, base_url=base_url, token=actor_token, room_id=0, ready=True)

            lobby_event = await _recv_until(
                lobby_ws,
                event_type="ROOM_LIST",
                predicate=lambda event: any(
                    room["room_id"] == 0 and room["ready_count"] >= 1
                    for room in event["payload"]["rooms"]
                ),
            )
            room_event = await _recv_until(
                room_ws,
                event_type="ROOM_UPDATE",
                predicate=lambda event: any(
                    member["user_id"] == actor_id and member["ready"]
                    for member in event["payload"]["room"]["members"]
                ),
            )

            assert any(
                room["room_id"] == 0 and room["ready_count"] >= 1
                for room in lobby_event["payload"]["rooms"]
            )
            assert any(
                member["user_id"] == actor_id and member["ready"]
                for member in room_event["payload"]["room"]["members"]
            )

    asyncio.run(_run())


def test_m2_rs_ws_08_leave_pushes_owner_and_player_count_updates(live_server: tuple[str, str]) -> None:
    """M2-RS-WS-08: owner leave should push updated owner_id and player_count."""
    base_url, ws_base_url = live_server
    owner_id, owner_token = _register_user(base_url=base_url, username="r2ws08o")
    next_owner_id, next_owner_token = _register_user(base_url=base_url, username="r2ws08n")
    _, third_token = _register_user(base_url=base_url, username="r2ws08t")

    _join_room(base_url=base_url, token=owner_token, room_id=0)
    _join_room(base_url=base_url, token=next_owner_token, room_id=0)
    _join_room(base_url=base_url, token=third_token, room_id=0)

    async def _run() -> None:
        async with (
            websockets.connect(
                f"{ws_base_url}/ws/lobby?token={next_owner_token}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as lobby_ws,
            websockets.connect(
                f"{ws_base_url}/ws/rooms/0?token={next_owner_token}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as room_ws,
        ):
            await _recv_until(lobby_ws, event_type="ROOM_LIST")
            await _recv_until(room_ws, event_type="ROOM_UPDATE")

            await asyncio.to_thread(_leave_room, base_url=base_url, token=owner_token, room_id=0)

            lobby_event = await _recv_until(
                lobby_ws,
                event_type="ROOM_LIST",
                predicate=lambda event: any(
                    room["room_id"] == 0 and room["player_count"] == 2
                    for room in event["payload"]["rooms"]
                ),
            )
            room_event = await _recv_until(
                room_ws,
                event_type="ROOM_UPDATE",
                predicate=lambda event: (
                    event["payload"]["room"]["owner_id"] == next_owner_id
                    and all(member["user_id"] != owner_id for member in event["payload"]["room"]["members"])
                ),
            )

            assert any(
                room["room_id"] == 0 and room["player_count"] == 2
                for room in lobby_event["payload"]["rooms"]
            )
            room_payload = room_event["payload"]["room"]
            assert room_payload["owner_id"] == next_owner_id
            assert all(member["user_id"] != owner_id for member in room_payload["members"])

    asyncio.run(_run())


def test_m2_rs_ws_09_cross_room_migration_pushes_both_rooms_and_lobby(live_server: tuple[str, str]) -> None:
    """M2-RS-WS-09: cross-room migration should push updates to room0, room1 and lobby."""
    base_url, ws_base_url = live_server
    _, listener_token = _register_user(base_url=base_url, username="r2ws09l")
    actor_id, actor_token = _register_user(base_url=base_url, username="r2ws09a")
    _join_room(base_url=base_url, token=actor_token, room_id=0)

    async def _run() -> None:
        async with (
            websockets.connect(
                f"{ws_base_url}/ws/lobby?token={listener_token}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as lobby_ws,
            websockets.connect(
                f"{ws_base_url}/ws/rooms/0?token={listener_token}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as room0_ws,
            websockets.connect(
                f"{ws_base_url}/ws/rooms/1?token={listener_token}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as room1_ws,
        ):
            await _recv_until(lobby_ws, event_type="ROOM_LIST")
            await _recv_until(room0_ws, event_type="ROOM_UPDATE")
            await _recv_until(room1_ws, event_type="ROOM_UPDATE")

            await asyncio.to_thread(_join_room, base_url=base_url, token=actor_token, room_id=1)

            room0_event = await _recv_until(
                room0_ws,
                event_type="ROOM_UPDATE",
                predicate=lambda event: all(
                    member["user_id"] != actor_id for member in event["payload"]["room"]["members"]
                ),
            )
            room1_event = await _recv_until(
                room1_ws,
                event_type="ROOM_UPDATE",
                predicate=lambda event: any(
                    member["user_id"] == actor_id for member in event["payload"]["room"]["members"]
                ),
            )
            lobby_event = await _recv_until(
                lobby_ws,
                event_type="ROOM_LIST",
                predicate=lambda event: any(
                    room["room_id"] == 0 and room["player_count"] == 0 for room in event["payload"]["rooms"]
                )
                and any(
                    room["room_id"] == 1 and room["player_count"] >= 1 for room in event["payload"]["rooms"]
                ),
            )

            assert all(member["user_id"] != actor_id for member in room0_event["payload"]["room"]["members"])
            assert any(member["user_id"] == actor_id for member in room1_event["payload"]["room"]["members"])
            assert any(room["room_id"] == 0 and room["player_count"] == 0 for room in lobby_event["payload"]["rooms"])
            assert any(room["room_id"] == 1 and room["player_count"] >= 1 for room in lobby_event["payload"]["rooms"])

    asyncio.run(_run())


def test_m2_rs_ws_10_server_ping_and_client_pong_keeps_connection_alive(live_server: tuple[str, str]) -> None:
    """M2-RS-WS-10: server sends PING and client PONG keeps socket alive."""
    base_url, ws_base_url = live_server
    _, access_token = _register_user(base_url=base_url, username="r2ws10u")

    async def _run() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/lobby?token={access_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            await _recv_until(ws, event_type="ROOM_LIST")
            await _recv_until(ws, event_type="PING")
            await ws.send("PONG")
            await asyncio.sleep(0.1)
            assert ws.close_code is None

    asyncio.run(_run())
