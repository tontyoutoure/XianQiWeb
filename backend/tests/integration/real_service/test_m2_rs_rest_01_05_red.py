"""Red-phase REST tests against a live M2 backend service (Rooms 01~05)."""

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
JWT_SECRET = "m2-rs-red-test-secret-key-32-bytes-minimum"
ROOM_COUNT = 3


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


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[str, None, None]:
    """Start a real uvicorn process for one test case."""
    port = _pick_free_port()
    base_url = f"http://127.0.0.1:{port}"
    db_path = tmp_path / "m2_rs_rest_01_05_red.sqlite3"

    env = os.environ.copy()
    env["XQWEB_SQLITE_PATH"] = str(db_path)
    env["XQWEB_JWT_SECRET"] = JWT_SECRET
    env["XQWEB_ROOM_COUNT"] = str(ROOM_COUNT)

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


def _assert_error_payload(*, response: httpx.Response, expected_status: int) -> dict[str, object]:
    """Assert unified REST error contract and return parsed payload."""
    assert response.status_code == expected_status
    payload = response.json()
    assert {"code", "message", "detail"} <= set(payload)
    return payload


def _register_user(*, client: httpx.Client, username: str) -> tuple[int, str]:
    """Register one user and return (user_id, access_token)."""
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "123"},
    )
    assert response.status_code == 200
    payload = response.json()
    return int(payload["user"]["id"]), str(payload["access_token"])


def test_m2_rs_rest_01_rooms_initialized_as_preset_waiting_rooms(live_server: str) -> None:
    """M2-RS-REST-01: /api/rooms reflects preset room initialization."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        _, access_token = _register_user(client=client, username="r201u")
        response = client.get(
            "/api/rooms",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == ROOM_COUNT
    assert [room["room_id"] for room in payload] == list(range(ROOM_COUNT))

    for room in payload:
        assert {"room_id", "status", "player_count", "ready_count"} <= set(room)
        assert room["status"] == "waiting"
        assert room["player_count"] == 0
        assert room["ready_count"] == 0


def test_m2_rs_rest_02_rooms_list_rejects_missing_token(live_server: str) -> None:
    """M2-RS-REST-02: /api/rooms rejects missing token with 401."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        response = client.get("/api/rooms")

    _assert_error_payload(response=response, expected_status=401)


def test_m2_rs_rest_03_room_detail_success(live_server: str) -> None:
    """M2-RS-REST-03: /api/rooms/{room_id} returns room_detail for valid room."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        _, access_token = _register_user(client=client, username="r203u")
        response = client.get(
            "/api/rooms/0",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["room_id"] == 0
    assert payload["status"] == "waiting"
    assert payload["owner_id"] is None
    assert payload["members"] == []
    assert payload["current_game_id"] is None


def test_m2_rs_rest_04_room_detail_404_for_invalid_room_id(live_server: str) -> None:
    """M2-RS-REST-04: /api/rooms/{room_id} returns ROOM_NOT_FOUND for invalid room."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        _, access_token = _register_user(client=client, username="r204u")
        response = client.get(
            "/api/rooms/9999",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    payload = _assert_error_payload(response=response, expected_status=404)
    assert payload["code"] == "ROOM_NOT_FOUND"
    assert payload["message"] == "room not found"
    assert payload["detail"] == {"room_id": 9999}


def test_m2_rs_rest_05_first_join_sets_owner_seat_and_initial_chips(live_server: str) -> None:
    """M2-RS-REST-05: first join sets owner, seat=0, and chips=20."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        user_id, access_token = _register_user(client=client, username="r205u")
        response = client.post(
            "/api/rooms/0/join",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["room_id"] == 0
    assert payload["status"] == "waiting"
    assert payload["owner_id"] == user_id
    assert payload["current_game_id"] is None

    assert len(payload["members"]) == 1
    member = payload["members"][0]
    assert member["user_id"] == user_id
    assert member["username"] == "r205u"
    assert member["seat"] == 0
    assert member["ready"] is False
    assert member["chips"] == 20
