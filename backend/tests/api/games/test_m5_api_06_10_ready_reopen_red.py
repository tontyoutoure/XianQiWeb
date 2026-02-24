"""M5-BE-06~10 API/WS contract tests for settlement re-ready reopen (RED phase)."""

from __future__ import annotations

import asyncio
import importlib
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
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

    def disconnect(self) -> None:
        self._disconnect_event.set()


def _bootstrap_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_name: str):
    db_path = tmp_path / db_name
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "m5-api-test-secret-key-32-bytes-minimum")
    monkeypatch.setenv("XQWEB_ROOM_COUNT", "3")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    return app_main


def _register_and_get_access_token(app_main: Any, username: str) -> tuple[int, str]:
    payload = app_main.register(
        app_main.RegisterRequest(username=username, password="123"),
    )
    return int(payload["user"]["id"]), str(payload["access_token"])


def _auth_header(token: str) -> str:
    return f"Bearer {token}"


def _setup_three_players_and_start_game(app_main: Any, username_prefix: str) -> dict[str, Any]:
    users: list[tuple[int, str]] = []
    for idx in range(3):
        users.append(_register_and_get_access_token(app_main, username=f"{username_prefix}{idx}"))

    user_token_by_id = {user_id: token for user_id, token in users}

    for _, token in users:
        app_main.join_room(room_id=0, authorization=_auth_header(token))

    for _, token in users:
        app_main.set_room_ready(
            room_id=0,
            payload=app_main.ReadyRequest(ready=True),
            authorization=_auth_header(token),
        )

    room_payload = app_main.get_room_detail(room_id=0, authorization=_auth_header(users[0][1]))
    assert room_payload["status"] == "playing"
    game_id = int(room_payload["current_game_id"])

    token_by_seat: dict[int, str] = {}
    for member in room_payload["members"]:
        token_by_seat[int(member["seat"])] = user_token_by_id[int(member["user_id"])]
    assert set(token_by_seat.keys()) == {0, 1, 2}
    return {"game_id": game_id, "token_by_seat": token_by_seat}


def _find_json_messages_by_type(websocket: _FakeWebSocket, event_type: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for mode, payload in websocket.sent_messages:
        if mode == "json" and isinstance(payload, dict) and payload.get("type") == event_type:
            matches.append(payload)
    return matches


def test_m5_be_06_all_members_ready_in_settlement_starts_next_game(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M5-BE-06: third ready in settlement should create a new game and move room to playing."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m5_api_06.sqlite3")
    context = _setup_three_players_and_start_game(app_main, username_prefix="m5a06")
    old_game_id = int(context["game_id"])
    app_main.room_registry.mark_game_settlement(old_game_id)

    for seat in (0, 1):
        interim = app_main.set_room_ready(
            room_id=0,
            payload=app_main.ReadyRequest(ready=True),
            authorization=_auth_header(context["token_by_seat"][seat]),
        )
        assert interim["status"] == "settlement"
        assert int(interim["current_game_id"]) == old_game_id

    third_payload = app_main.set_room_ready(
        room_id=0,
        payload=app_main.ReadyRequest(ready=True),
        authorization=_auth_header(context["token_by_seat"][2]),
    )
    new_game_id = int(third_payload["current_game_id"])
    assert third_payload["status"] == "playing"
    assert new_game_id == old_game_id + 1

    state_payload = app_main.get_game_state(
        game_id=new_game_id,
        authorization=_auth_header(context["token_by_seat"][0]),
    )
    assert state_payload["game_id"] == new_game_id
    assert state_payload["public_state"]["phase"] in {"buckle_flow", "in_round"}


def test_m5_be_07_partial_ready_in_settlement_does_not_start_next_game(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M5-BE-07: only partial ready in settlement should keep room in settlement."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m5_api_07.sqlite3")
    context = _setup_three_players_and_start_game(app_main, username_prefix="m5a07")
    old_game_id = int(context["game_id"])
    app_main.room_registry.mark_game_settlement(old_game_id)

    for seat in (0, 1):
        app_main.set_room_ready(
            room_id=0,
            payload=app_main.ReadyRequest(ready=True),
            authorization=_auth_header(context["token_by_seat"][seat]),
        )

    room_payload = app_main.get_room_detail(
        room_id=0,
        authorization=_auth_header(context["token_by_seat"][0]),
    )
    assert room_payload["status"] == "settlement"
    assert int(room_payload["current_game_id"]) == old_game_id
    assert sum(1 for member in room_payload["members"] if member["ready"]) == 2


def test_m5_be_08_non_member_ready_in_settlement_is_forbidden(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M5-BE-08: non-member cannot update ready when room is in settlement."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m5_api_08.sqlite3")
    context = _setup_three_players_and_start_game(app_main, username_prefix="m5a08")
    app_main.room_registry.mark_game_settlement(context["game_id"])
    outsider_id, outsider_token = _register_and_get_access_token(app_main, username="m5a08x")

    with pytest.raises(HTTPException) as exc_info:
        app_main.set_room_ready(
            room_id=0,
            payload=app_main.ReadyRequest(ready=True),
            authorization=_auth_header(outsider_token),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == {
        "code": "ROOM_NOT_MEMBER",
        "message": "user is not a room member",
        "detail": {"room_id": 0, "user_id": outsider_id},
    }


def test_m5_be_09_concurrent_ready_in_settlement_starts_exactly_one_game(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M5-BE-09: concurrent ready updates should only start one new game."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m5_api_09.sqlite3")
    context = _setup_three_players_and_start_game(app_main, username_prefix="m5a09")
    old_game_id = int(context["game_id"])
    app_main.room_registry.mark_game_settlement(old_game_id)

    tokens = [context["token_by_seat"][seat] for seat in (0, 1, 2)]
    start_barrier = threading.Barrier(len(tokens))

    def _ready_worker(token: str) -> tuple[str, int | None]:
        start_barrier.wait()
        room_payload = app_main.set_room_ready(
            room_id=0,
            payload=app_main.ReadyRequest(ready=True),
            authorization=_auth_header(token),
        )
        game_id = room_payload["current_game_id"]
        return str(room_payload["status"]), int(game_id) if game_id is not None else None

    with ThreadPoolExecutor(max_workers=len(tokens)) as executor:
        results = list(executor.map(_ready_worker, tokens))

    room_payload = app_main.get_room_detail(
        room_id=0,
        authorization=_auth_header(context["token_by_seat"][0]),
    )
    assert room_payload["status"] == "playing"
    assert int(room_payload["current_game_id"]) == old_game_id + 1
    assert sorted(app_main.room_registry._games_by_id.keys()) == [old_game_id, old_game_id + 1]


def test_m5_be_10_after_reopen_ws_pushes_room_update_and_new_game_first_frames(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M5-BE-10: re-ready reopen should push ROOM_UPDATE + new GAME_PUBLIC/PRIVATE_STATE."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m5_api_10.sqlite3")
    context = _setup_three_players_and_start_game(app_main, username_prefix="m5a10")
    old_game_id = int(context["game_id"])
    app_main.room_registry.mark_game_settlement(old_game_id)

    async def _run() -> tuple[_FakeWebSocket, int]:
        listener_token = context["token_by_seat"][0]
        ws = _FakeWebSocket(token=listener_token)
        ws_task = asyncio.create_task(app_main.ws_room(ws, room_id=0))
        await ws.wait_accepted()

        third_payload: dict[str, Any] | None = None
        for seat in (0, 1, 2):
            third_payload = app_main.set_room_ready(
                room_id=0,
                payload=app_main.ReadyRequest(ready=True),
                authorization=_auth_header(context["token_by_seat"][seat]),
            )
            await asyncio.sleep(0)

        assert third_payload is not None
        new_game_id = int(third_payload["current_game_id"])
        await asyncio.sleep(0)

        ws.disconnect()
        await asyncio.wait_for(ws_task, timeout=1.0)
        return ws, new_game_id

    ws, new_game_id = asyncio.run(_run())

    room_updates = _find_json_messages_by_type(ws, "ROOM_UPDATE")
    assert any(
        event["payload"]["room"]["status"] == "playing"
        and int(event["payload"]["room"]["current_game_id"]) == new_game_id
        for event in room_updates
    ), "expected ROOM_UPDATE for the reopened game"

    public_events = _find_json_messages_by_type(ws, "GAME_PUBLIC_STATE")
    private_events = _find_json_messages_by_type(ws, "GAME_PRIVATE_STATE")
    assert any(
        int(event["payload"]["game_id"]) == new_game_id for event in public_events
    ), "expected GAME_PUBLIC_STATE for reopened game"
    assert any(
        int(event["payload"]["game_id"]) == new_game_id for event in private_events
    ), "expected GAME_PRIVATE_STATE for reopened game"
