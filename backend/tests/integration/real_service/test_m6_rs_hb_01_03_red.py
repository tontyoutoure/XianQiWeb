"""Red-phase heartbeat tests against a live M6 backend service (HB 01~03)."""

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
from websockets.exceptions import ConnectionClosed

from tests.integration.real_service.live_server import run_live_server

JWT_SECRET = "m6-rs-hb-red-test-secret-key-32-bytes-minimum"
ROOM_COUNT = 3


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[tuple[str, str], None, None]:
    """Start one real uvicorn backend per test case."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m6_rs_hb_01_03_red.sqlite3",
        jwt_secret=JWT_SECRET,
        env_overrides={"XQWEB_ROOM_COUNT": str(ROOM_COUNT)},
    ) as server:
        yield server.base_url, server.ws_base_url


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_user(*, base_url: str, username: str) -> tuple[int, str]:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(
            "/api/auth/register",
            json={"username": username, "password": "123"},
        )
    assert response.status_code == 200
    payload = response.json()
    return int(payload["user"]["id"]), str(payload["access_token"])


def _join_room(*, base_url: str, access_token: str, room_id: int) -> dict[str, Any]:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(
            f"/api/rooms/{room_id}/join",
            headers=_auth_headers(access_token),
        )
    assert response.status_code == 200
    return dict(response.json())


async def _recv_json_event(ws: Any, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return dict(json.loads(raw))


async def _recv_until(
    ws: Any,
    *,
    event_type: str,
    timeout_seconds: float = 5.0,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(f"timeout waiting for event_type={event_type}")
        event = await _recv_json_event(ws, timeout_seconds=remaining)
        if event.get("type") != event_type:
            continue
        if predicate is not None and not predicate(event):
            continue
        return event


async def _recv_optional_business_event(ws: Any, *, timeout_seconds: float = 0.6) -> dict[str, Any] | None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        try:
            event = await _recv_json_event(ws, timeout_seconds=remaining)
        except TimeoutError:
            return None
        if event.get("type") in {"PING", "PONG"}:
            continue
        return event


async def _wait_for_disconnect(ws: Any, *, timeout_seconds: float) -> ConnectionClosed:
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError("timeout waiting for websocket disconnect")
        try:
            await _recv_json_event(ws, timeout_seconds=remaining)
        except ConnectionClosed as exc:
            return exc


def test_m6_rs_hb_01_ping_pong_keepalive(live_server: tuple[str, str]) -> None:
    """M6-RS-HB-01: respond PONG within 10s after PING should keep websocket alive."""
    base_url, ws_base_url = live_server
    _, access_token = _register_user(base_url=base_url, username="m6rshb01")

    async def _run() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/lobby?token={access_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            await _recv_until(ws, event_type="ROOM_LIST")
            await _recv_until(ws, event_type="PING", timeout_seconds=5.0)
            await ws.send("PONG")
            await asyncio.sleep(0.3)
            assert ws.close_code is None

    asyncio.run(_run())


def test_m6_rs_hb_02_missing_pong_leads_disconnect(live_server: tuple[str, str]) -> None:
    """M6-RS-HB-02: missing PONG twice should trigger server-side disconnect."""
    base_url, ws_base_url = live_server
    _, access_token = _register_user(base_url=base_url, username="m6rshb02")

    async def _run() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/lobby?token={access_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            await _recv_until(ws, event_type="ROOM_LIST")
            await _recv_until(ws, event_type="PING", timeout_seconds=5.0)
            await _recv_until(ws, event_type="PING", timeout_seconds=35.0)
            closed = await _wait_for_disconnect(ws, timeout_seconds=12.0)
            assert closed.code is not None

    asyncio.run(_run())


def test_m6_rs_hb_03_multi_connection_heartbeat_stable(live_server: tuple[str, str]) -> None:
    """M6-RS-HB-03: multi-room connections should keep heartbeat stable without cross-room noise."""
    base_url, ws_base_url = live_server

    _, token0 = _register_user(base_url=base_url, username="m6rshb03u0")
    user1_id, token1 = _register_user(base_url=base_url, username="m6rshb03u1")
    user2_id, token2 = _register_user(base_url=base_url, username="m6rshb03u2")

    _join_room(base_url=base_url, access_token=token0, room_id=0)
    _join_room(base_url=base_url, access_token=token1, room_id=1)

    async def _run() -> None:
        async with (
            websockets.connect(
                f"{ws_base_url}/ws/rooms/0?token={token0}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as room0_ws_1,
            websockets.connect(
                f"{ws_base_url}/ws/rooms/0?token={token0}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as room0_ws_2,
            websockets.connect(
                f"{ws_base_url}/ws/rooms/1?token={token1}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as room1_ws_1,
            websockets.connect(
                f"{ws_base_url}/ws/rooms/1?token={token1}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as room1_ws_2,
        ):
            await _recv_until(room0_ws_1, event_type="ROOM_UPDATE")
            await _recv_until(room0_ws_2, event_type="ROOM_UPDATE")
            await _recv_until(room1_ws_1, event_type="ROOM_UPDATE")
            await _recv_until(room1_ws_2, event_type="ROOM_UPDATE")

            room0_ping_1 = await _recv_until(room0_ws_1, event_type="PING")
            room0_ping_2 = await _recv_until(room0_ws_2, event_type="PING")
            room1_ping_1 = await _recv_until(room1_ws_1, event_type="PING")
            room1_ping_2 = await _recv_until(room1_ws_2, event_type="PING")
            assert room0_ping_1["type"] == "PING"
            assert room0_ping_2["type"] == "PING"
            assert room1_ping_1["type"] == "PING"
            assert room1_ping_2["type"] == "PING"

            await room0_ws_1.send("PONG")
            await room0_ws_2.send("PONG")
            await room1_ws_1.send("PONG")
            await room1_ws_2.send("PONG")

            await asyncio.to_thread(_join_room, base_url=base_url, access_token=token2, room_id=1)

            room1_update_1 = await _recv_until(
                room1_ws_1,
                event_type="ROOM_UPDATE",
                predicate=lambda event: any(member["user_id"] == user2_id for member in event["payload"]["room"]["members"]),
            )
            room1_update_2 = await _recv_until(
                room1_ws_2,
                event_type="ROOM_UPDATE",
                predicate=lambda event: any(member["user_id"] == user2_id for member in event["payload"]["room"]["members"]),
            )
            assert any(member["user_id"] == user1_id for member in room1_update_1["payload"]["room"]["members"])
            assert any(member["user_id"] == user1_id for member in room1_update_2["payload"]["room"]["members"])

            room0_unexpected_1 = await _recv_optional_business_event(room0_ws_1, timeout_seconds=0.6)
            room0_unexpected_2 = await _recv_optional_business_event(room0_ws_2, timeout_seconds=0.6)
            assert room0_unexpected_1 is None
            assert room0_unexpected_2 is None

            assert room0_ws_1.close_code is None
            assert room0_ws_2.close_code is None
            assert room1_ws_1.close_code is None
            assert room1_ws_2.close_code is None

    asyncio.run(_run())
