"""Red-phase startup-mode tests for M8 seed mode matrix (MODE-01~04)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest

from tests.integration.real_service.live_server import run_live_server

JWT_SECRET = "m8-rs-mode-red-test-secret-key-32-bytes-minimum"


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run_uvicorn_once(
    *,
    tmp_path: Path,
    db_filename: str,
    env_overrides: dict[str, str],
    timeout_seconds: float = 8.0,
) -> subprocess.CompletedProcess[str]:
    backend_root = Path(__file__).resolve().parents[3]
    port = _pick_free_port()
    env = os.environ.copy()
    env.update(
        {
            "XQWEB_SQLITE_PATH": str(tmp_path / db_filename),
            "XQWEB_JWT_SECRET": JWT_SECRET,
            "XQWEB_APP_HOST": "127.0.0.1",
            "XQWEB_APP_PORT": str(port),
        }
    )
    env.update(env_overrides)
    return subprocess.run(
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
        cwd=str(backend_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


@pytest.fixture
def live_server_seed_injection_enabled(tmp_path: Path) -> Generator[str, None, None]:
    """Start regular-service backend with seed injection explicitly enabled."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m8_rs_mode_02.sqlite3",
        jwt_secret=JWT_SECRET,
        env_overrides={"XQWEB_SEED_ENABLE_SEED_INJECTION": "true"},
    ) as server:
        yield server.base_url


@pytest.fixture
def live_server_seed_injection_disabled(tmp_path: Path) -> Generator[str, None, None]:
    """Start regular-service backend with seed injection explicitly disabled."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m8_rs_mode_03.sqlite3",
        jwt_secret=JWT_SECRET,
        env_overrides={"XQWEB_SEED_ENABLE_SEED_INJECTION": "false"},
    ) as server:
        yield server.base_url


def test_m8_mode_01_seed_catalog_mode_exits_zero_without_http(tmp_path: Path) -> None:
    """M8-MODE-01: catalog mode should complete and exit 0 instead of startup failure."""
    catalog_dir = tmp_path / "seed-catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)

    completed = _run_uvicorn_once(
        tmp_path=tmp_path,
        db_filename="m8_rs_mode_01.sqlite3",
        env_overrides={"XQWEB_SEED_CATALOG_DIR": str(catalog_dir)},
    )

    assert completed.returncode == 0
    assert "Application startup failed" not in (completed.stderr + completed.stdout)


def test_m8_mode_02_seed_injection_enabled_returns_200(
    live_server_seed_injection_enabled: str,
) -> None:
    """M8-MODE-02: regular mode + injection enabled should allow seed injection endpoint."""
    with httpx.Client(base_url=live_server_seed_injection_enabled, timeout=3, trust_env=False) as client:
        response = client.post("/api/games/seed-injection", json={"seed": 123456})

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"ok": True, "injected_seed": 123456, "apply_scope": "next_game_once"}


def test_m8_mode_03_seed_injection_disabled_returns_403(
    live_server_seed_injection_disabled: str,
) -> None:
    """M8-MODE-03: regular mode + injection disabled should reject with 403."""
    with httpx.Client(base_url=live_server_seed_injection_disabled, timeout=3, trust_env=False) as client:
        response = client.post("/api/games/seed-injection", json={"seed": 42})

    assert response.status_code == 403
    payload = response.json()
    assert payload["code"] == "SEED_INJECTION_DISABLED"


def test_m8_mode_04_invalid_seed_catalog_dir_startup_fails_nonzero(tmp_path: Path) -> None:
    """M8-MODE-04: invalid seed config should fail startup with a diagnosable error."""
    invalid_catalog_dir = tmp_path / "not-found-dir"

    completed = _run_uvicorn_once(
        tmp_path=tmp_path,
        db_filename="m8_rs_mode_04.sqlite3",
        env_overrides={"XQWEB_SEED_CATALOG_DIR": str(invalid_catalog_dir)},
    )

    assert completed.returncode != 0
    combined_output = completed.stdout + completed.stderr
    assert "XQWEB_SEED_CATALOG_DIR must be an existing directory" in combined_output
