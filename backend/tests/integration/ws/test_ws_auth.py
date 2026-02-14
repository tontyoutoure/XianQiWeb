"""M1 WebSocket auth contract tests (RED phase)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

PROBE_SCRIPT = Path(__file__).with_name("ws_probe.py")
BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _run_ws_probe(*, mode: str, tmp_path: Path) -> dict[str, object]:
    db_path = tmp_path / f"m1_{mode}.sqlite3"
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{BACKEND_ROOT}:{existing_pythonpath}" if existing_pythonpath else str(
        BACKEND_ROOT
    )
    env["XQWEB_SQLITE_PATH"] = str(db_path)
    env["XQWEB_JWT_SECRET"] = "ws-test-secret-key-32-bytes-minimum"

    try:
        completed = subprocess.run(
            [sys.executable, str(PROBE_SCRIPT), mode],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=8,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"WS probe timed out in mode={mode}: {exc}")

    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        pytest.fail(
            f"WS probe returned no stdout in mode={mode}, rc={completed.returncode}, stderr={completed.stderr}"
        )

    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"WS probe returned non-JSON output in mode={mode}: {lines[-1]!r}, stderr={completed.stderr}"
        ) from exc

    payload["_returncode"] = completed.returncode
    payload["_stderr"] = completed.stderr
    return payload


def test_m1_ws_01_ws_connects_with_valid_access_token(
    tmp_path: Path,
) -> None:
    """Contract: WS with valid access token should connect successfully."""
    payload = _run_ws_probe(mode="valid", tmp_path=tmp_path)
    assert payload["result"] == "connected"


def test_m1_ws_02_ws_rejects_invalid_token_with_4401(
    tmp_path: Path,
) -> None:
    """Contract: WS auth failure closes with code 4401 and UNAUTHORIZED reason."""
    payload = _run_ws_probe(mode="invalid", tmp_path=tmp_path)
    assert payload["result"] == "disconnect"
    assert payload["code"] == 4401
    assert payload["reason"] == "UNAUTHORIZED"


def test_m1_ws_03_ws_rejects_expired_token_with_4401(
    tmp_path: Path,
) -> None:
    """Contract: expired access token cannot establish WS connection."""
    payload = _run_ws_probe(mode="expired", tmp_path=tmp_path)
    assert payload["result"] == "disconnect"
    assert payload["code"] == 4401
    assert payload["reason"] == "UNAUTHORIZED"
