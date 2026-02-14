"""Red-phase REST+WS E2E tests against a live M1 backend service."""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
from collections.abc import Generator
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
            proxy=None,
        ) as ws:
            await ws.send("ping")
            return ws.close_code is None

    assert asyncio.run(_run()) is True


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[tuple[str, str], None, None]:
    """Start a real uvicorn process for one test case."""
    port = _pick_free_port()
    base_url = f"http://127.0.0.1:{port}"
    ws_base_url = f"ws://127.0.0.1:{port}"
    db_path = tmp_path / "m1_rs_e2e_red.sqlite3"

    env = os.environ.copy()
    env["XQWEB_SQLITE_PATH"] = str(db_path)
    env["XQWEB_JWT_SECRET"] = JWT_SECRET
    env["XQWEB_ACCESS_TOKEN_EXPIRE_SECONDS"] = "8"
    env["XQWEB_ACCESS_TOKEN_REFRESH_INTERVAL_SECONDS"] = "4"

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


def test_m1_rs_e2e_01_rest_login_access_token_can_connect_ws(live_server: tuple[str, str]) -> None:
    """M1-RS-E2E-01: access token from REST login is usable on lobby and room WS."""
    base_url, ws_base_url = live_server
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        register_response = client.post(
            "/api/auth/register",
            json={"username": "Alice", "password": "123"},
        )
        login_response = client.post(
            "/api/auth/login",
            json={"username": "Alice", "password": "123"},
        )

    assert register_response.status_code == 200
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    _assert_ws_connectable(ws_url=f"{ws_base_url}/ws/lobby?token={access_token}")
    _assert_ws_connectable(ws_url=f"{ws_base_url}/ws/rooms/0?token={access_token}")


def test_m1_rs_e2e_02_refresh_new_access_works_old_access_rejected_after_expiry(
    live_server: tuple[str, str],
) -> None:
    """M1-RS-E2E-02: refreshed access works; old access is rejected after expiry."""
    base_url, ws_base_url = live_server
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        register_response = client.post(
            "/api/auth/register",
            json={"username": "Alice", "password": "123"},
        )
        old_access_token = register_response.json()["access_token"]
        old_refresh_token = register_response.json()["refresh_token"]

        refresh_response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": old_refresh_token},
        )

    assert register_response.status_code == 200
    assert refresh_response.status_code == 200
    new_access_token = refresh_response.json()["access_token"]

    _assert_ws_connectable(ws_url=f"{ws_base_url}/ws/lobby?token={new_access_token}")

    old_payload = jwt.decode(
        old_access_token,
        options={"verify_signature": False, "verify_exp": False},
        algorithms=["HS256"],
    )
    sleep_seconds = max(0, int(old_payload["exp"]) - int(time.time()) + 1)
    time.sleep(float(sleep_seconds))

    _assert_ws_closed_unauthorized(ws_url=f"{ws_base_url}/ws/lobby?token={old_access_token}")


def test_m1_rs_e2e_03_logout_only_revokes_refresh_not_current_access(
    live_server: tuple[str, str],
) -> None:
    """M1-RS-E2E-03: logout invalidates refresh while current access remains usable before expiry."""
    base_url, ws_base_url = live_server
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        register_response = client.post(
            "/api/auth/register",
            json={"username": "Alice", "password": "123"},
        )
        access_token = register_response.json()["access_token"]
        refresh_token = register_response.json()["refresh_token"]

        logout_response = client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
        )
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        refresh_after_logout = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )

    assert register_response.status_code == 200
    assert logout_response.status_code == 200
    assert logout_response.json() == {"ok": True}
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "Alice"
    assert refresh_after_logout.status_code == 401
    assert refresh_after_logout.json()["code"] == "AUTH_REFRESH_REVOKED"

    _assert_ws_connectable(ws_url=f"{ws_base_url}/ws/lobby?token={access_token}")
