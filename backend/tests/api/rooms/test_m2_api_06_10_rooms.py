"""M2-API-06~10 rooms contract tests (RED phase)."""

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


def test_m2_api_06_join_cross_room_migration_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: join B from A migrates user and keeps single-room membership."""
    with _new_client(tmp_path, monkeypatch, "m2_api_06.sqlite3") as client:
        user_id, access_token = _register_and_get_access_token(client, username="m2a06u1")
        headers = {"Authorization": f"Bearer {access_token}"}

        assert client.post("/api/rooms/0/join", headers=headers).status_code == 200
        assert client.post("/api/rooms/1/join", headers=headers).status_code == 200

        room0 = client.get("/api/rooms/0", headers=headers)
        room1 = client.get("/api/rooms/1", headers=headers)
        assert room0.status_code == 200
        assert room1.status_code == 200

        members_0 = room0.json()["members"]
        members_1 = room1.json()["members"]
        assert all(member["user_id"] != user_id for member in members_0)
        assert sum(1 for member in members_1 if member["user_id"] == user_id) == 1


def test_m2_api_07_join_cross_room_migration_rollback_when_target_full(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: failed migration to full room keeps user in source room."""
    with _new_client(tmp_path, monkeypatch, "m2_api_07.sqlite3") as client:
        src_user_id, src_token = _register_and_get_access_token(client, username="m2a07s")
        src_headers = {"Authorization": f"Bearer {src_token}"}
        assert client.post("/api/rooms/0/join", headers=src_headers).status_code == 200

        for idx in range(3):
            _, token = _register_and_get_access_token(client, username=f"m2a07t{idx}")
            full_headers = {"Authorization": f"Bearer {token}"}
            assert client.post("/api/rooms/1/join", headers=full_headers).status_code == 200

        overflow = client.post("/api/rooms/1/join", headers=src_headers)
        assert overflow.status_code == 409
        assert overflow.json() == {
            "code": "ROOM_FULL",
            "message": "room is full",
            "detail": {"room_id": 1},
        }

        room0 = client.get("/api/rooms/0", headers=src_headers)
        assert room0.status_code == 200
        members_0 = room0.json()["members"]
        assert sum(1 for member in members_0 if member["user_id"] == src_user_id) == 1


def test_m2_api_08_leave_success_and_owner_transfer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: owner leaves successfully and owner transfers to earliest remaining member."""
    with _new_client(tmp_path, monkeypatch, "m2_api_08.sqlite3") as client:
        first_id, first_token = _register_and_get_access_token(client, username="m2a08a")
        second_id, second_token = _register_and_get_access_token(client, username="m2a08b")
        _, third_token = _register_and_get_access_token(client, username="m2a08c")

        first_headers = {"Authorization": f"Bearer {first_token}"}
        second_headers = {"Authorization": f"Bearer {second_token}"}
        third_headers = {"Authorization": f"Bearer {third_token}"}

        assert client.post("/api/rooms/0/join", headers=first_headers).status_code == 200
        assert client.post("/api/rooms/0/join", headers=second_headers).status_code == 200
        assert client.post("/api/rooms/0/join", headers=third_headers).status_code == 200

        leave_response = client.post("/api/rooms/0/leave", headers=first_headers)
        assert leave_response.status_code == 200
        assert leave_response.json() == {"ok": True}

        detail_response = client.get("/api/rooms/0", headers=second_headers)
        assert detail_response.status_code == 200
        room = detail_response.json()
        assert room["owner_id"] == second_id
        assert all(member["user_id"] != first_id for member in room["members"])


def test_m2_api_09_leave_rejects_non_member(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: leave by non-member returns 403 + ROOM_NOT_MEMBER."""
    with _new_client(tmp_path, monkeypatch, "m2_api_09.sqlite3") as client:
        user_id, token = _register_and_get_access_token(client, username="m2a09u")
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post("/api/rooms/0/leave", headers=headers)

        assert response.status_code == 403
        assert response.json() == {
            "code": "ROOM_NOT_MEMBER",
            "message": "user is not a room member",
            "detail": {"room_id": 0, "user_id": user_id},
        }


def test_m2_api_10_ready_toggle_success_for_member_waiting_room(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: waiting-room member can toggle ready and receive updated room detail."""
    with _new_client(tmp_path, monkeypatch, "m2_api_10.sqlite3") as client:
        user_id, token = _register_and_get_access_token(client, username="m2a10u")
        headers = {"Authorization": f"Bearer {token}"}

        assert client.post("/api/rooms/0/join", headers=headers).status_code == 200
        response = client.post("/api/rooms/0/ready", headers=headers, json={"ready": True})

        assert response.status_code == 200
        room = response.json()
        assert room["status"] == "waiting"
        member = next(item for item in room["members"] if item["user_id"] == user_id)
        assert member["ready"] is True
