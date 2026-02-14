"""Red-phase REST tests against a live M1 backend service."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]


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
            response = httpx.get(f"{base_url}/api/auth/me", timeout=0.3)
            if response.status_code == 401:
                return
        except httpx.HTTPError:
            pass

        time.sleep(0.1)

    raise RuntimeError("uvicorn did not become ready before timeout")


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[str, None, None]:
    """Start a real uvicorn process for one test case."""
    port = _pick_free_port()
    base_url = f"http://127.0.0.1:{port}"
    db_path = tmp_path / "m1_rs_red.sqlite3"

    env = os.environ.copy()
    env["XQWEB_SQLITE_PATH"] = str(db_path)
    env["XQWEB_JWT_SECRET"] = "m1-rs-red-test-secret"

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
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _assert_error_payload(*, response: httpx.Response, expected_status: int) -> None:
    """Assert unified REST error contract."""
    assert response.status_code == expected_status
    payload = response.json()
    assert {"code", "message", "detail"} <= set(payload)


def test_m1_rs_rest_01_register_success(live_server: str) -> None:
    """M1-RS-REST-01: register returns auth session fields."""
    with httpx.Client(base_url=live_server, timeout=3) as client:
        response = client.post(
            "/api/auth/register",
            json={"username": "Alice", "password": "123"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert {"access_token", "refresh_token", "expires_in", "refresh_expires_in", "user"} <= set(payload)
    assert payload["user"]["username"] == "Alice"


def test_m1_rs_rest_02_register_duplicate_nfc_conflict(live_server: str) -> None:
    """M1-RS-REST-02: NFC-equivalent usernames conflict."""
    with httpx.Client(base_url=live_server, timeout=3) as client:
        first = client.post(
            "/api/auth/register",
            json={"username": "é", "password": "123"},
        )
        second = client.post(
            "/api/auth/register",
            json={"username": "é", "password": "123"},
        )

    assert first.status_code == 200
    _assert_error_payload(response=second, expected_status=409)


def test_m1_rs_rest_03_register_case_sensitive(live_server: str) -> None:
    """M1-RS-REST-03: username matching is case-sensitive."""
    with httpx.Client(base_url=live_server, timeout=3) as client:
        tom_upper = client.post(
            "/api/auth/register",
            json={"username": "Tom", "password": "123"},
        )
        tom_lower = client.post(
            "/api/auth/register",
            json={"username": "tom", "password": "123"},
        )

    assert tom_upper.status_code == 200
    assert tom_lower.status_code == 200
    assert tom_upper.json()["user"]["id"] != tom_lower.json()["user"]["id"]


def test_m1_rs_rest_04_empty_password_register_and_login(live_server: str) -> None:
    """M1-RS-REST-04: MVP allows empty password for register/login."""
    with httpx.Client(base_url=live_server, timeout=3) as client:
        register_response = client.post(
            "/api/auth/register",
            json={"username": "NoPwd", "password": ""},
        )
        login_response = client.post(
            "/api/auth/login",
            json={"username": "NoPwd", "password": ""},
        )

    assert register_response.status_code == 200
    assert login_response.status_code == 200


def test_m1_rs_rest_05_login_success_returns_fresh_token_pair(live_server: str) -> None:
    """M1-RS-REST-05: login returns a fresh token pair for registered user."""
    with httpx.Client(base_url=live_server, timeout=3) as client:
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

    register_payload = register_response.json()
    login_payload = login_response.json()

    assert {"access_token", "refresh_token", "expires_in", "refresh_expires_in", "user"} <= set(login_payload)
    assert login_payload["user"]["username"] == "Alice"
    assert login_payload["access_token"] != register_payload["access_token"]
    assert login_payload["refresh_token"] != register_payload["refresh_token"]
