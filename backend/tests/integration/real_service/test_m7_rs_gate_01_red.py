"""Real-service gate test for M7 frontend closure prerequisites."""

from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
import websockets
from tests.integration.real_service.live_server import run_live_server

JWT_SECRET = "m7-rs-gate-01-secret-key-32-bytes-minimum"


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[tuple[str, str], None, None]:
    """Start one live backend for M7 gate checks."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m7_rs_gate_01.sqlite3",
        jwt_secret=JWT_SECRET,
    ) as server:
        yield server.base_url, server.ws_base_url


def test_m7_gate_01_backend_core_capabilities_are_ready(live_server: tuple[str, str]) -> None:
    """M7-GATE-01: register/login/rooms succeed and lobby WS can establish."""
    base_url, ws_base_url = live_server
    username = f"g{secrets.token_hex(3)}"
    password = "123"

    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        register_response = client.post(
            "/api/auth/register",
            json={"username": username, "password": password},
        )
        login_response = client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )

    assert register_response.status_code == 200
    assert login_response.status_code == 200

    login_payload = login_response.json()
    access_token = str(login_payload["access_token"])
    assert access_token

    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        rooms_response = client.get(
            "/api/rooms",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert rooms_response.status_code == 200
    rooms_payload = rooms_response.json()
    assert isinstance(rooms_payload, list)

    async def _run() -> dict[str, object]:
        async with websockets.connect(
            f"{ws_base_url}/ws/lobby?token={access_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=3)

        assert isinstance(raw, str)
        return dict(json.loads(raw))

    first_event = asyncio.run(_run())
    assert first_event.get("type") == "ROOM_LIST"
