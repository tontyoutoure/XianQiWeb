"""M1 WebSocket auth contract tests."""

from __future__ import annotations

import asyncio
import importlib
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path

import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.tokens import create_access_token


class _FakeWebSocket:
    def __init__(self, *, token: str | None) -> None:
        self.query_params: dict[str, str] = {}
        if token is not None:
            self.query_params["token"] = token

        self.accept_count = 0
        self.close_code: int | None = None
        self.close_reason: str | None = None
        self.receive_count = 0

    async def accept(self) -> None:
        self.accept_count += 1

    async def close(self, *, code: int = 1000, reason: str | None = None) -> None:
        self.close_code = code
        self.close_reason = reason

    async def receive_text(self) -> str:
        self.receive_count += 1
        raise WebSocketDisconnect(code=1000)


def _setup_app(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_name: str,
) -> tuple[object, str, int]:
    db_path = tmp_path / db_name
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "ws-test-secret-key-32-bytes-minimum")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    register_result = app_main.register(app_main.RegisterRequest(username="Alice", password="123"))
    return app_main, str(register_result["access_token"]), int(register_result["user"]["id"])


def test_m1_ws_01_ws_connects_with_valid_access_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: WS with valid access token should connect successfully."""
    app_main, access_token, _ = _setup_app(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        db_name="m1_ws_01.sqlite3",
    )
    websocket = _FakeWebSocket(token=access_token)

    asyncio.run(app_main.ws_lobby(websocket))

    assert websocket.accept_count == 1
    assert websocket.close_code is None
    assert websocket.close_reason is None
    assert websocket.receive_count == 1


def test_m1_ws_02_ws_rejects_invalid_token_with_4401(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: WS auth failure closes with code 4401 and UNAUTHORIZED reason."""
    app_main, _, _ = _setup_app(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        db_name="m1_ws_02.sqlite3",
    )
    websocket = _FakeWebSocket(token="invalid-token")

    asyncio.run(app_main.ws_lobby(websocket))

    assert websocket.accept_count == 1
    assert websocket.close_code == 4401
    assert websocket.close_reason == "UNAUTHORIZED"
    assert websocket.receive_count == 0


def test_m1_ws_03_ws_rejects_expired_token_with_4401(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: expired access token cannot establish WS connection."""
    app_main, _, user_id = _setup_app(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        db_name="m1_ws_03.sqlite3",
    )
    websocket = _FakeWebSocket(
        token=create_access_token(
            user_id=user_id,
            now=datetime(2026, 2, 14, tzinfo=timezone.utc) - timedelta(hours=2),
            expires_in_seconds=3600,
        )
    )

    asyncio.run(app_main.ws_lobby(websocket))

    assert websocket.accept_count == 1
    assert websocket.close_code == 4401
    assert websocket.close_reason == "UNAUTHORIZED"
    assert websocket.receive_count == 0
