"""Red-phase REST tests against a live M1 backend service."""

from __future__ import annotations

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

BACKEND_ROOT = Path(__file__).resolve().parents[3]
JWT_SECRET = "m1-rs-red-test-secret"


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
    db_path = tmp_path / "m1_rs_red.sqlite3"

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
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
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
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
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
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
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
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
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
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
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


def test_m1_rs_rest_06_login_failure_returns_401_with_unified_error(live_server: str) -> None:
    """M1-RS-REST-06: invalid credentials return unified 401 errors."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        register_response = client.post(
            "/api/auth/register",
            json={"username": "Alice", "password": "123"},
        )
        wrong_password = client.post(
            "/api/auth/login",
            json={"username": "Alice", "password": "wrong"},
        )
        wrong_username = client.post(
            "/api/auth/login",
            json={"username": "Bob", "password": "123"},
        )

    assert register_response.status_code == 200
    for response in (wrong_password, wrong_username):
        _assert_error_payload(response=response, expected_status=401)
        payload = response.json()
        assert payload["code"] == "AUTH_INVALID_CREDENTIALS"
        assert payload["message"] == "invalid username or password"


def test_m1_rs_rest_07_me_success_with_valid_bearer_token(live_server: str) -> None:
    """M1-RS-REST-07: /me returns current profile with valid access token."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        register_response = client.post(
            "/api/auth/register",
            json={"username": "Alice", "password": "123"},
        )
        access_token = register_response.json()["access_token"]
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert register_response.status_code == 200
    assert me_response.status_code == 200
    payload = me_response.json()
    assert payload["username"] == "Alice"
    assert {"id", "username", "created_at"} <= set(payload)


def test_m1_rs_rest_08_me_unauthorized_for_missing_or_invalid_token(live_server: str) -> None:
    """M1-RS-REST-08: /me rejects missing token and forged token."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        missing_token = client.get("/api/auth/me")
        forged_token = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer not-a-jwt"},
        )

    for response in (missing_token, forged_token):
        _assert_error_payload(response=response, expected_status=401)


def test_m1_rs_rest_09_me_unauthorized_for_expired_token(live_server: str) -> None:
    """M1-RS-REST-09: /me rejects expired access token."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        register_response = client.post(
            "/api/auth/register",
            json={"username": "Alice", "password": "123"},
        )
        user_id = int(register_response.json()["user"]["id"])

        expired_token = jwt.encode(
            {
                "sub": str(user_id),
                "exp": int((datetime.now(tz=timezone.utc) - timedelta(hours=1)).timestamp()),
            },
            JWT_SECRET,
            algorithm="HS256",
        )
        expired_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

    assert register_response.status_code == 200
    _assert_error_payload(response=expired_response, expected_status=401)
    assert expired_response.json()["code"] == "AUTH_TOKEN_EXPIRED"


def test_m1_rs_rest_10_refresh_rotates_and_revokes_old_refresh_token(live_server: str) -> None:
    """M1-RS-REST-10: /refresh issues new token pair and invalidates old refresh."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        register_response = client.post(
            "/api/auth/register",
            json={"username": "Alice", "password": "123"},
        )
        old_refresh_token = register_response.json()["refresh_token"]

        refresh_response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": old_refresh_token},
        )
        old_refresh_reuse = client.post(
            "/api/auth/refresh",
            json={"refresh_token": old_refresh_token},
        )

    assert register_response.status_code == 200
    assert refresh_response.status_code == 200
    refreshed_payload = refresh_response.json()
    assert {"access_token", "refresh_token", "expires_in", "refresh_expires_in"} <= set(refreshed_payload)
    assert refreshed_payload["refresh_token"] != old_refresh_token
    _assert_error_payload(response=old_refresh_reuse, expected_status=401)
