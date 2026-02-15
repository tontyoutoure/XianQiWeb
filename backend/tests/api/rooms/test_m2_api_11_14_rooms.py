"""M2-API-11~14 rooms contract tests (RED phase)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _new_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_name: str) -> TestClient:
    db_path = tmp_path / db_name
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "m2-api-test-secret-key-32-bytes-minimum")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    return TestClient(app_main.app)


def _register_and_get_access_token(
    client: TestClient,
    username: str,
    password: str = "123",
) -> tuple[int, str]:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    payload = response.json()
    return payload["user"]["id"], payload["access_token"]


def test_m2_api_11_ready_rejects_non_member(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: non-member ready returns 403 + ROOM_NOT_MEMBER."""
    with _new_client(tmp_path, monkeypatch, "m2_api_11.sqlite3") as client:
        user_id, access_token = _register_and_get_access_token(client, username="m2a11u")
        headers = {"Authorization": f"Bearer {access_token}"}

        response = client.post("/api/rooms/0/ready", headers=headers, json={"ready": True})

        assert response.status_code == 403
        assert response.json() == {
            "code": "ROOM_NOT_MEMBER",
            "message": "user is not a room member",
            "detail": {"room_id": 0, "user_id": user_id},
        }


def test_m2_api_12_ready_rejects_when_room_not_waiting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: ready change in non-waiting room returns 409 + ROOM_NOT_WAITING."""
    with _new_client(tmp_path, monkeypatch, "m2_api_12.sqlite3") as client:
        _, access_token = _register_and_get_access_token(client, username="m2a12u")
        headers = {"Authorization": f"Bearer {access_token}"}

        assert client.post("/api/rooms/0/join", headers=headers).status_code == 200

        import app.main as app_main

        app_main.room_registry.get_room(0).status = "playing"

        response = client.post("/api/rooms/0/ready", headers=headers, json={"ready": True})

        assert response.status_code == 409
        assert response.json() == {
            "code": "ROOM_NOT_WAITING",
            "message": "room is not in waiting status",
            "detail": {"room_id": 0},
        }


def test_m2_api_13_start_game_hook_called_once_when_third_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: start_game hook is triggered exactly once when all 3 members become ready."""
    with _new_client(tmp_path, monkeypatch, "m2_api_13.sqlite3") as client:
        users: list[tuple[int, str]] = []
        for idx in range(3):
            user_id, token = _register_and_get_access_token(client, username=f"m2a13u{idx}")
            users.append((user_id, token))

        import app.main as app_main

        trigger_calls: list[int] = []

        def _spy_start_game_hook(room) -> None:
            trigger_calls.append(room.room_id)

        monkeypatch.setattr(app_main, "_start_game_hook_if_all_ready", _spy_start_game_hook)

        for _, token in users:
            headers = {"Authorization": f"Bearer {token}"}
            assert client.post("/api/rooms/0/join", headers=headers).status_code == 200

        for _, token in users:
            headers = {"Authorization": f"Bearer {token}"}
            assert client.post("/api/rooms/0/ready", headers=headers, json={"ready": True}).status_code == 200

        assert trigger_calls == [0]


def test_m2_api_14_leave_from_playing_triggers_cold_end_reset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: leave during playing resets waiting/current_game_id/ready while keeping chips."""
    with _new_client(tmp_path, monkeypatch, "m2_api_14.sqlite3") as client:
        users: list[tuple[int, str]] = []
        for idx in range(3):
            user_id, token = _register_and_get_access_token(client, username=f"m2a14u{idx}")
            users.append((user_id, token))

        for _, token in users:
            headers = {"Authorization": f"Bearer {token}"}
            assert client.post("/api/rooms/0/join", headers=headers).status_code == 200

        import app.main as app_main

        room = app_main.room_registry.get_room(0)
        room.status = "playing"
        room.current_game_id = 114
        for member in room.members:
            member.ready = True
        before_chips = {member.user_id: member.chips for member in room.members}

        leave_headers = {"Authorization": f"Bearer {users[0][1]}"}
        keep_headers = {"Authorization": f"Bearer {users[1][1]}"}

        leave_response = client.post("/api/rooms/0/leave", headers=leave_headers)
        assert leave_response.status_code == 200
        assert leave_response.json() == {"ok": True}

        detail_response = client.get("/api/rooms/0", headers=keep_headers)
        assert detail_response.status_code == 200
        payload = detail_response.json()
        assert payload["status"] == "waiting"
        assert payload["current_game_id"] is None
        assert all(member["ready"] is False for member in payload["members"])

        current_chips = {member["user_id"]: member["chips"] for member in payload["members"]}
        expected_chips = {
            user_id: chips for user_id, chips in before_chips.items() if user_id != users[0][0]
        }
        assert current_chips == expected_chips
