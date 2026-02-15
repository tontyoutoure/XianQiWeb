"""Shared live-server runner for real-service integration tests."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Generator
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class LiveServer:
    """Endpoints for one launched backend test server."""

    base_url: str
    ws_base_url: str


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


@contextmanager
def run_live_server(
    *,
    tmp_path: Path,
    db_filename: str,
    jwt_secret: str,
    env_overrides: Mapping[str, str] | None = None,
    startup_timeout_seconds: float = 10.0,
) -> Generator[LiveServer, None, None]:
    """Launch uvicorn and yield HTTP/WS endpoints for the test duration."""
    port = _pick_free_port()
    base_url = f"http://127.0.0.1:{port}"
    ws_base_url = f"ws://127.0.0.1:{port}"
    db_path = tmp_path / db_filename

    env = os.environ.copy()
    env["XQWEB_SQLITE_PATH"] = str(db_path)
    env["XQWEB_JWT_SECRET"] = jwt_secret
    if env_overrides:
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
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    _wait_for_server_ready(base_url=base_url, process=process, timeout_seconds=startup_timeout_seconds)

    try:
        yield LiveServer(base_url=base_url, ws_base_url=ws_base_url)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

