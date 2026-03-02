"""M8-SEED-CFG-01~05 startup config contract tests (RED phase)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from tests.integration.real_service.live_server import BACKEND_ROOT
from tests.integration.real_service.live_server import run_live_server

JWT_SECRET = "m8-seed-cfg-red-secret-key-32-bytes-minimum"


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_backend_process(
    *,
    tmp_path: Path,
    db_filename: str,
    env_overrides: dict[str, str],
) -> tuple[subprocess.Popen[str], str]:
    port = _pick_free_port()
    base_url = f"http://127.0.0.1:{port}"
    db_path = tmp_path / db_filename

    env = os.environ.copy()
    env["XQWEB_APP_HOST"] = "127.0.0.1"
    env["XQWEB_APP_PORT"] = str(port)
    env["XQWEB_SQLITE_PATH"] = str(db_path)
    env["XQWEB_JWT_SECRET"] = JWT_SECRET
    env.update(env_overrides)

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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process, base_url


def _wait_for_exit(process: subprocess.Popen[str], *, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return True
        time.sleep(0.05)
    return False


def _is_http_reachable(base_url: str) -> bool:
    try:
        response = httpx.get(f"{base_url}/api/auth/me", timeout=0.3, trust_env=False)
    except httpx.HTTPError:
        return False
    return response.status_code in {200, 401}


def _stop_process(process: subprocess.Popen[str]) -> tuple[str, str]:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    stdout, stderr = process.communicate(timeout=1)
    return stdout, stderr


def test_m8_seed_cfg_01_invalid_injection_bool_fails_startup(tmp_path: Path) -> None:
    """Input: invalid bool env -> Output: startup fails with non-zero exit."""
    process, _ = _start_backend_process(
        tmp_path=tmp_path,
        db_filename="m8_seed_cfg_01.sqlite3",
        env_overrides={"XQWEB_SEED_ENABLE_SEED_INJECTION": "not-bool"},
    )
    try:
        assert _wait_for_exit(process, timeout_seconds=3.0)
        assert process.returncode is not None
        assert process.returncode != 0
    finally:
        _stop_process(process)


def test_m8_seed_cfg_02_catalog_mode_does_not_start_http_server(tmp_path: Path) -> None:
    """Input: only catalog dir set -> Output: process exits and HTTP server stays unreachable."""
    catalog_dir = tmp_path / "seed-catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)

    process, base_url = _start_backend_process(
        tmp_path=tmp_path,
        db_filename="m8_seed_cfg_02.sqlite3",
        env_overrides={"XQWEB_SEED_CATALOG_DIR": str(catalog_dir)},
    )
    try:
        exited = _wait_for_exit(process, timeout_seconds=3.0)
        reachable = _is_http_reachable(base_url)
        assert exited
        assert not reachable
    finally:
        _stop_process(process)


def test_m8_seed_cfg_03_injection_enabled_keeps_normal_service_mode(tmp_path: Path) -> None:
    """Input: only injection=true -> Output: service starts and seed-injection endpoint is exposed."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m8_seed_cfg_03.sqlite3",
        jwt_secret=JWT_SECRET,
        env_overrides={"XQWEB_SEED_ENABLE_SEED_INJECTION": "true"},
    ) as server:
        with httpx.Client(base_url=server.base_url, timeout=3, trust_env=False) as client:
            response = client.post("/api/games/seed-injection", json={"seed": 12345})

    assert response.status_code in {200, 400, 401, 422}
    assert response.status_code not in {403, 404}


def test_m8_seed_cfg_04_catalog_mode_takes_priority_over_injection_mode(tmp_path: Path) -> None:
    """Input: catalog+injection set -> Output: catalog mode wins and HTTP server remains unreachable."""
    catalog_dir = tmp_path / "seed-catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)

    process, base_url = _start_backend_process(
        tmp_path=tmp_path,
        db_filename="m8_seed_cfg_04.sqlite3",
        env_overrides={
            "XQWEB_SEED_CATALOG_DIR": str(catalog_dir),
            "XQWEB_SEED_ENABLE_SEED_INJECTION": "true",
        },
    )
    try:
        exited = _wait_for_exit(process, timeout_seconds=3.0)
        reachable = _is_http_reachable(base_url)
        assert exited
        assert not reachable
    finally:
        _stop_process(process)


def test_m8_seed_cfg_05_catalog_dir_missing_fails_startup(tmp_path: Path) -> None:
    """Input: non-existent catalog dir -> Output: startup fails with non-zero exit."""
    missing_dir = tmp_path / "missing-seed-catalog"

    process, _ = _start_backend_process(
        tmp_path=tmp_path,
        db_filename="m8_seed_cfg_05.sqlite3",
        env_overrides={"XQWEB_SEED_CATALOG_DIR": str(missing_dir)},
    )
    try:
        assert _wait_for_exit(process, timeout_seconds=3.0)
        assert process.returncode is not None
        assert process.returncode != 0
    finally:
        _stop_process(process)
