"""M2-API-01~05 rooms contract tests (RED phase)."""

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


def test_m2_api_01_get_rooms_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: GET /api/rooms returns room_summary list."""
    with _new_client(tmp_path, monkeypatch, "m2_api_01.sqlite3") as client:
        _, access_token = _register_and_get_access_token(client, username="m2a01u")

        response = client.get(
            "/api/rooms",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        rooms = response.json()
        assert isinstance(rooms, list)
        assert len(rooms) >= 1
        sample = rooms[0]
        assert {"room_id", "status", "player_count", "ready_count"} <= set(sample)


def test_m2_api_02_get_room_detail_and_404(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: room detail succeeds for valid id and returns ROOM_NOT_FOUND for invalid id."""
    with _new_client(tmp_path, monkeypatch, "m2_api_02.sqlite3") as client:
        _, access_token = _register_and_get_access_token(client, username="m2a02u")
        headers = {"Authorization": f"Bearer {access_token}"}

        ok_response = client.get("/api/rooms/0", headers=headers)
        assert ok_response.status_code == 200
        room = ok_response.json()
        assert room["room_id"] == 0
        assert {"room_id", "status", "owner_id", "members", "current_game_id"} <= set(room)

        not_found_response = client.get("/api/rooms/999", headers=headers)
        assert not_found_response.status_code == 404
        assert not_found_response.json() == {
            "code": "ROOM_NOT_FOUND",
            "message": "room not found",
            "detail": {"room_id": 999},
        }


def test_m2_api_03_join_first_member_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: first join returns room_detail with owner and seat assignment."""
    with _new_client(tmp_path, monkeypatch, "m2_api_03.sqlite3") as client:
        user_id, access_token = _register_and_get_access_token(client, username="m2a03u")

        response = client.post(
            "/api/rooms/0/join",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        room = response.json()
        assert room["room_id"] == 0
        assert room["status"] == "waiting"
        assert room["owner_id"] == user_id
        assert room["current_game_id"] is None
        assert len(room["members"]) == 1
        assert room["members"][0]["user_id"] == user_id
        assert room["members"][0]["seat"] == 0
        assert room["members"][0]["ready"] is False
        assert room["members"][0]["chips"] == 20


def test_m2_api_04_join_returns_room_full_when_4th_user_joins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: 4th join in same room is rejected with ROOM_FULL."""
    with _new_client(tmp_path, monkeypatch, "m2_api_04.sqlite3") as client:
        tokens: list[str] = []
        for idx in range(4):
            _, token = _register_and_get_access_token(client, username=f"m2a04u{idx}")
            tokens.append(token)

        for idx in range(3):
            join_response = client.post(
                "/api/rooms/0/join",
                headers={"Authorization": f"Bearer {tokens[idx]}"},
            )
            assert join_response.status_code == 200

        overflow_response = client.post(
            "/api/rooms/0/join",
            headers={"Authorization": f"Bearer {tokens[3]}"},
        )
        assert overflow_response.status_code == 409
        assert overflow_response.json() == {
            "code": "ROOM_FULL",
            "message": "room is full",
            "detail": {"room_id": 0},
        }


def test_m2_api_05_join_is_idempotent_for_same_room(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: joining the same room twice keeps one member and stable seat."""
    with _new_client(tmp_path, monkeypatch, "m2_api_05.sqlite3") as client:
        user_id, access_token = _register_and_get_access_token(client, username="m2a05u")
        headers = {"Authorization": f"Bearer {access_token}"}

        first_join = client.post("/api/rooms/0/join", headers=headers)
        assert first_join.status_code == 200

        second_join = client.post("/api/rooms/0/join", headers=headers)
        assert second_join.status_code == 200
        room = second_join.json()
        assert len(room["members"]) == 1
        assert room["members"][0]["user_id"] == user_id
        assert room["members"][0]["seat"] == 0
