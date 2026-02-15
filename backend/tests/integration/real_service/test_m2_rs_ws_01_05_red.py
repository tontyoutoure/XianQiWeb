"""Red-phase WebSocket tests against a live M2 backend service (Rooms WS 01~05)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from pathlib import Path

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
        db_filename="m2_rs_ws_01_05_red.sqlite3",
        jwt_secret=JWT_SECRET,
        env_overrides={"XQWEB_ROOM_COUNT": str(ROOM_COUNT)},
    ) as server:
        yield server.base_url, server.ws_base_url


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


def _assert_ws_closed(*, ws_url: str, expected_code: int, expected_reason: str) -> None:
    """Connect and assert the server closes with the expected code/reason."""

    async def _run() -> tuple[int | None, str | None]:
        ws = await websockets.connect(
            ws_url,
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        )
        await ws.wait_closed()
        return ws.close_code, ws.close_reason

    close_code, close_reason = asyncio.run(_run())
    assert close_code == expected_code
    assert close_reason == expected_reason


def test_m2_rs_ws_01_lobby_connect_sends_initial_room_list_snapshot(live_server: tuple[str, str]) -> None:
    """M2-RS-WS-01: /ws/lobby sends ROOM_LIST snapshot consistent with REST rooms list."""
    base_url, ws_base_url = live_server
    _, access_token = _register_user(base_url=base_url, username="r2ws01u")

    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        rooms_response = client.get(
            "/api/rooms",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert rooms_response.status_code == 200
    expected_rooms = rooms_response.json()

    async def _run() -> dict[str, object]:
        async with websockets.connect(
            f"{ws_base_url}/ws/lobby?token={access_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            message = await asyncio.wait_for(ws.recv(), timeout=3)
        assert isinstance(message, str)
        return dict(json.loads(message))

    event = asyncio.run(_run())
    assert event["type"] == "ROOM_LIST"
    assert event["payload"]["rooms"] == expected_rooms


def test_m2_rs_ws_02_room_connect_sends_initial_room_update_snapshot(live_server: tuple[str, str]) -> None:
    """M2-RS-WS-02: /ws/rooms/{id} sends ROOM_UPDATE snapshot consistent with REST room detail."""
    base_url, ws_base_url = live_server
    _, access_token = _register_user(base_url=base_url, username="r2ws02u")

    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        join_response = client.post(
            "/api/rooms/0/join",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert join_response.status_code == 200

        room_response = client.get(
            "/api/rooms/0",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert room_response.status_code == 200
    expected_room = room_response.json()

    async def _run() -> dict[str, object]:
        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={access_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            message = await asyncio.wait_for(ws.recv(), timeout=3)
        assert isinstance(message, str)
        return dict(json.loads(message))

    event = asyncio.run(_run())
    assert event["type"] == "ROOM_UPDATE"
    assert event["payload"]["room"] == expected_room


def test_m2_rs_ws_03_lobby_rejects_missing_token(live_server: tuple[str, str]) -> None:
    """M2-RS-WS-03: /ws/lobby rejects missing token with 4401/UNAUTHORIZED."""
    _, ws_base_url = live_server
    _assert_ws_closed(
        ws_url=f"{ws_base_url}/ws/lobby",
        expected_code=4401,
        expected_reason="UNAUTHORIZED",
    )


def test_m2_rs_ws_04_room_rejects_invalid_token(live_server: tuple[str, str]) -> None:
    """M2-RS-WS-04: /ws/rooms/{id} rejects invalid token with 4401/UNAUTHORIZED."""
    _, ws_base_url = live_server
    _assert_ws_closed(
        ws_url=f"{ws_base_url}/ws/rooms/0?token=invalid-token",
        expected_code=4401,
        expected_reason="UNAUTHORIZED",
    )


def test_m2_rs_ws_05_room_rejects_non_existing_room_id(live_server: tuple[str, str]) -> None:
    """M2-RS-WS-05: /ws/rooms/{id} rejects non-existing room with 4404/ROOM_NOT_FOUND."""
    base_url, ws_base_url = live_server
    _, access_token = _register_user(base_url=base_url, username="r2ws05u")

    _assert_ws_closed(
        ws_url=f"{ws_base_url}/ws/rooms/9999?token={access_token}",
        expected_code=4404,
        expected_reason="ROOM_NOT_FOUND",
    )
