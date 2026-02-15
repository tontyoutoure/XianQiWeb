"""M2-WS-01~06 rooms websocket contract tests (RED phase)."""

from __future__ import annotations

import asyncio
import importlib
from collections import deque
from pathlib import Path
from typing import Any

import pytest
from starlette.websockets import WebSocketDisconnect


class _FakeWebSocket:
    def __init__(
        self,
        *,
        token: str | None,
        disconnect_immediately: bool = False,
    ) -> None:
        self.query_params: dict[str, str] = {}
        if token is not None:
            self.query_params["token"] = token

        self.accept_count = 0
        self.close_code: int | None = None
        self.close_reason: str | None = None
        self.sent_messages: list[tuple[str, Any]] = []

        self._accepted_event = asyncio.Event()
        self._disconnect_event = asyncio.Event()
        self._inbound_texts: deque[str] = deque()
        if disconnect_immediately:
            self.disconnect()

    async def accept(self) -> None:
        self.accept_count += 1
        self._accepted_event.set()

    async def close(self, *, code: int = 1000, reason: str | None = None) -> None:
        self.close_code = code
        self.close_reason = reason

    async def send_json(self, payload: Any) -> None:
        self.sent_messages.append(("json", payload))

    async def send_text(self, payload: str) -> None:
        self.sent_messages.append(("text", payload))

    async def receive_text(self) -> str:
        if self._inbound_texts:
            return self._inbound_texts.popleft()
        await self._disconnect_event.wait()
        raise WebSocketDisconnect(code=1000)

    async def wait_accepted(self) -> None:
        await asyncio.wait_for(self._accepted_event.wait(), timeout=1.0)

    def push_text(self, text: str) -> None:
        self._inbound_texts.append(text)

    def disconnect(self) -> None:
        self._disconnect_event.set()


def _setup_app(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_name: str,
):
    db_path = tmp_path / db_name
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "m2-ws-test-secret-key-32-bytes-minimum")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    return app_main


def _register_and_get_access_token(app_main, username: str) -> tuple[int, str]:
    result = app_main.register(app_main.RegisterRequest(username=username, password="123"))
    return int(result["user"]["id"]), str(result["access_token"])


def _find_json_messages_by_type(websocket: _FakeWebSocket, event_type: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for mode, payload in websocket.sent_messages:
        if mode == "json" and isinstance(payload, dict) and payload.get("type") == event_type:
            matches.append(payload)
    return matches


def test_m2_ws_01_lobby_pushes_initial_room_list_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: /ws/lobby sends ROOM_LIST snapshot right after connect."""
    app_main = _setup_app(tmp_path=tmp_path, monkeypatch=monkeypatch, db_name="m2_ws_01.sqlite3")
    _, access_token = _register_and_get_access_token(app_main, username="m2ws01u")
    expected_rooms = app_main.list_rooms(authorization=f"Bearer {access_token}")
    websocket = _FakeWebSocket(token=access_token, disconnect_immediately=True)

    asyncio.run(app_main.ws_lobby(websocket))

    room_list_events = _find_json_messages_by_type(websocket, "ROOM_LIST")
    assert room_list_events, "expected ROOM_LIST event on connect"
    assert room_list_events[0]["payload"]["rooms"] == expected_rooms


def test_m2_ws_02_room_channel_pushes_initial_room_update_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: /ws/rooms/{room_id} sends ROOM_UPDATE snapshot on connect."""
    app_main = _setup_app(tmp_path=tmp_path, monkeypatch=monkeypatch, db_name="m2_ws_02.sqlite3")
    _, access_token = _register_and_get_access_token(app_main, username="m2ws02u")
    headers = f"Bearer {access_token}"
    app_main.join_room(room_id=0, authorization=headers)
    expected_room = app_main.get_room_detail(room_id=0, authorization=headers)
    websocket = _FakeWebSocket(token=access_token, disconnect_immediately=True)

    asyncio.run(app_main.ws_room(websocket, room_id=0))

    room_update_events = _find_json_messages_by_type(websocket, "ROOM_UPDATE")
    assert room_update_events, "expected ROOM_UPDATE event on connect"
    assert room_update_events[0]["payload"]["room"] == expected_room


def test_m2_ws_03_join_triggers_lobby_and_room_updates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: join success should trigger ROOM_LIST and ROOM_UPDATE pushes."""

    async def _run() -> tuple[_FakeWebSocket, _FakeWebSocket]:
        app_main = _setup_app(tmp_path=tmp_path, monkeypatch=monkeypatch, db_name="m2_ws_03.sqlite3")
        _, listener_token = _register_and_get_access_token(app_main, username="m2ws03l")
        actor_id, actor_token = _register_and_get_access_token(app_main, username="m2ws03a")

        lobby_ws = _FakeWebSocket(token=listener_token)
        room_ws = _FakeWebSocket(token=listener_token)

        lobby_task = asyncio.create_task(app_main.ws_lobby(lobby_ws))
        room_task = asyncio.create_task(app_main.ws_room(room_ws, room_id=0))
        await lobby_ws.wait_accepted()
        await room_ws.wait_accepted()

        app_main.join_room(room_id=0, authorization=f"Bearer {actor_token}")
        await asyncio.sleep(0)

        lobby_ws.disconnect()
        room_ws.disconnect()
        await asyncio.wait_for(asyncio.gather(lobby_task, room_task), timeout=1.0)

        room_update_events = _find_json_messages_by_type(room_ws, "ROOM_UPDATE")
        assert any(
            any(member["user_id"] == actor_id for member in event["payload"]["room"]["members"])
            for event in room_update_events
        ), "expected ROOM_UPDATE containing joined actor"
        assert _find_json_messages_by_type(lobby_ws, "ROOM_LIST"), "expected ROOM_LIST update after join"
        return lobby_ws, room_ws

    asyncio.run(_run())


def test_m2_ws_04_ready_triggers_lobby_and_room_updates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: ready change should trigger ROOM_LIST and ROOM_UPDATE pushes."""

    async def _run() -> tuple[_FakeWebSocket, _FakeWebSocket]:
        app_main = _setup_app(tmp_path=tmp_path, monkeypatch=monkeypatch, db_name="m2_ws_04.sqlite3")
        actor_id, actor_token = _register_and_get_access_token(app_main, username="m2ws04a")

        app_main.join_room(room_id=0, authorization=f"Bearer {actor_token}")

        lobby_ws = _FakeWebSocket(token=actor_token)
        room_ws = _FakeWebSocket(token=actor_token)
        lobby_task = asyncio.create_task(app_main.ws_lobby(lobby_ws))
        room_task = asyncio.create_task(app_main.ws_room(room_ws, room_id=0))
        await lobby_ws.wait_accepted()
        await room_ws.wait_accepted()

        app_main.set_room_ready(
            room_id=0,
            payload=app_main.ReadyRequest(ready=True),
            authorization=f"Bearer {actor_token}",
        )
        await asyncio.sleep(0)

        lobby_ws.disconnect()
        room_ws.disconnect()
        await asyncio.wait_for(asyncio.gather(lobby_task, room_task), timeout=1.0)

        room_updates = _find_json_messages_by_type(room_ws, "ROOM_UPDATE")
        assert any(
            any(member["user_id"] == actor_id and member["ready"] for member in event["payload"]["room"]["members"])
            for event in room_updates
        ), "expected ROOM_UPDATE with ready=true for actor"
        assert _find_json_messages_by_type(lobby_ws, "ROOM_LIST"), "expected ROOM_LIST update after ready"
        return lobby_ws, room_ws

    asyncio.run(_run())


def test_m2_ws_05_leave_from_playing_triggers_room_cold_end_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: leave in playing room should push ROOM_UPDATE with waiting + null game id."""

    async def _run() -> _FakeWebSocket:
        app_main = _setup_app(tmp_path=tmp_path, monkeypatch=monkeypatch, db_name="m2_ws_05.sqlite3")
        users = [_register_and_get_access_token(app_main, username=f"m2ws05u{idx}") for idx in range(3)]

        for _, token in users:
            app_main.join_room(room_id=0, authorization=f"Bearer {token}")

        room = app_main.room_registry.get_room(0)
        room.status = "playing"
        room.current_game_id = 505
        for member in room.members:
            member.ready = True

        listener_token = users[1][1]
        leaver_token = users[0][1]

        room_ws = _FakeWebSocket(token=listener_token)
        room_task = asyncio.create_task(app_main.ws_room(room_ws, room_id=0))
        await room_ws.wait_accepted()

        app_main.leave_room(room_id=0, authorization=f"Bearer {leaver_token}")
        await asyncio.sleep(0)

        room_ws.disconnect()
        await asyncio.wait_for(room_task, timeout=1.0)

        room_updates = _find_json_messages_by_type(room_ws, "ROOM_UPDATE")
        assert any(
            event["payload"]["room"]["status"] == "waiting"
            and event["payload"]["room"]["current_game_id"] is None
            for event in room_updates
        ), "expected ROOM_UPDATE carrying cold-end reset state"
        return room_ws

    asyncio.run(_run())


def test_m2_ws_06_server_ping_and_client_pong_heartbeat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: server should send PING and accept client PONG heartbeat."""

    async def _run() -> _FakeWebSocket:
        app_main = _setup_app(tmp_path=tmp_path, monkeypatch=monkeypatch, db_name="m2_ws_06.sqlite3")
        _, access_token = _register_and_get_access_token(app_main, username="m2ws06u")

        lobby_ws = _FakeWebSocket(token=access_token)
        lobby_task = asyncio.create_task(app_main.ws_lobby(lobby_ws))
        await lobby_ws.wait_accepted()

        await asyncio.sleep(0)
        lobby_ws.push_text("PONG")
        await asyncio.sleep(0)

        lobby_ws.disconnect()
        await asyncio.wait_for(lobby_task, timeout=1.0)

        ping_json = _find_json_messages_by_type(lobby_ws, "PING")
        ping_text = [payload for mode, payload in lobby_ws.sent_messages if mode == "text" and payload == "PING"]
        assert ping_json or ping_text, "expected server heartbeat PING"
        return lobby_ws

    asyncio.run(_run())
