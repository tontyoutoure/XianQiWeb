"""Red-phase WebSocket tests against a live M1 backend service."""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
from collections.abc import Generator
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path

import httpx
import jwt
import pytest
import websockets

BACKEND_ROOT = Path(__file__).resolve().parents[3]
JWT_SECRET = "m1-rs-red-test-secret-key-32-bytes-minimum"


def _pick_free_port() -> int:
    """Reserve a free localhost TCP port for the live test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server_ready(*, base_url: str, process: subprocess.Popen[str], timeout_seconds: float) -> None:
    """Poll the API until the live server starts accepting requests."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("uvicorn exited before becoming ready")

        try:
            response = httpx.get(
                f"{base_url}/api/auth/me",
                timeout=0.3,
                trust_env=False,
            )
            if response.status_code == 401:
                return
        except httpx.HTTPError:
            pass

        time.sleep(0.1)

    raise RuntimeError("uvicorn did not become ready before timeout")


def _assert_ws_closed_unauthorized(*, ws_url: str) -> None:
    """Connect and assert the server closes with 4401/UNAUTHORIZED."""

    async def _run() -> tuple[int | None, str | None]:
        ws = await websockets.connect(ws_url, open_timeout=3, close_timeout=3, ping_interval=None)
        await ws.wait_closed()
        return ws.close_code, ws.close_reason

    close_code, close_reason = asyncio.run(_run())
    assert close_code == 4401
    assert close_reason == "UNAUTHORIZED"


def _assert_ws_connectable(*, ws_url: str) -> None:
    """Connect with a valid token and verify the socket remains open."""

    async def _run() -> bool:
        async with websockets.connect(
            ws_url,
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
        ) as ws:
            await ws.send("ping")
            return ws.close_code is None

    assert asyncio.run(_run()) is True


def _register_user(*, base_url: str, username: str = "Alice") -> tuple[str, int]:
    """Register one user and return (access_token, user_id)."""
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(
            "/api/auth/register",
            json={"username": username, "password": "123"},
        )
    assert response.status_code == 200
    payload = response.json()
    return str(payload["access_token"]), int(payload["user"]["id"])


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[tuple[str, str], None, None]:
    """Start a real uvicorn process for one test case."""
    port = _pick_free_port()
    base_url = f"http://127.0.0.1:{port}"
    ws_base_url = f"ws://127.0.0.1:{port}"
    db_path = tmp_path / "m1_rs_ws_red.sqlite3"

    env = os.environ.copy()
    env["XQWEB_SQLITE_PATH"] = str(db_path)
    env["XQWEB_JWT_SECRET"] = JWT_SECRET

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(BACKEND_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    _wait_for_server_ready(base_url=base_url, process=process, timeout_seconds=10)

    try:
        yield base_url, ws_base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_m1_rs_ws_01_lobby_connects_with_valid_access_token(live_server: tuple[str, str]) -> None:
    """M1-RS-WS-01: /ws/lobby accepts valid access token."""
    base_url, ws_base_url = live_server
    access_token, _ = _register_user(base_url=base_url)
    _assert_ws_connectable(ws_url=f"{ws_base_url}/ws/lobby?token={access_token}")


def test_m1_rs_ws_02_room_connects_with_valid_access_token(live_server: tuple[str, str]) -> None:
    """M1-RS-WS-02: /ws/rooms/{room_id} accepts valid access token."""
    base_url, ws_base_url = live_server
    access_token, _ = _register_user(base_url=base_url)
    _assert_ws_connectable(ws_url=f"{ws_base_url}/ws/rooms/0?token={access_token}")


def test_m1_rs_ws_03_lobby_rejects_missing_token(live_server: tuple[str, str]) -> None:
    """M1-RS-WS-03: /ws/lobby rejects missing token with 4401/UNAUTHORIZED."""
    _, ws_base_url = live_server
    _assert_ws_closed_unauthorized(ws_url=f"{ws_base_url}/ws/lobby")


def test_m1_rs_ws_04_lobby_rejects_invalid_token(live_server: tuple[str, str]) -> None:
    """M1-RS-WS-04: /ws/lobby rejects invalid token with 4401/UNAUTHORIZED."""
    _, ws_base_url = live_server
    _assert_ws_closed_unauthorized(ws_url=f"{ws_base_url}/ws/lobby?token=invalid-token")


def test_m1_rs_ws_05_lobby_rejects_expired_token(live_server: tuple[str, str]) -> None:
    """M1-RS-WS-05: /ws/lobby rejects expired token with 4401/UNAUTHORIZED."""
    base_url, ws_base_url = live_server
    _, user_id = _register_user(base_url=base_url)
    expired_token = jwt.encode(
        {
            "sub": str(user_id),
            "exp": int((datetime.now(tz=timezone.utc) - timedelta(hours=1)).timestamp()),
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    _assert_ws_closed_unauthorized(ws_url=f"{ws_base_url}/ws/lobby?token={expired_token}")


def test_m1_rs_ws_06_room_rejects_invalid_or_expired_token(live_server: tuple[str, str]) -> None:
    """M1-RS-WS-06: /ws/rooms/{room_id} rejects invalid and expired token with 4401/UNAUTHORIZED."""
    base_url, ws_base_url = live_server
    _, user_id = _register_user(base_url=base_url)
    expired_token = jwt.encode(
        {
            "sub": str(user_id),
            "exp": int((datetime.now(tz=timezone.utc) - timedelta(hours=1)).timestamp()),
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    _assert_ws_closed_unauthorized(ws_url=f"{ws_base_url}/ws/rooms/0?token=invalid-token")
    _assert_ws_closed_unauthorized(ws_url=f"{ws_base_url}/ws/rooms/0?token={expired_token}")
