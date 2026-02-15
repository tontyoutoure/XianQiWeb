"""Red-phase REST tests against a live M2 backend service (Rooms 01~10)."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
from tests.integration.real_service.live_server import run_live_server

JWT_SECRET = "m2-rs-red-test-secret-key-32-bytes-minimum"
ROOM_COUNT = 3


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[str, None, None]:
    """Start a real uvicorn process for one test case."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m2_rs_rest_01_10_red.sqlite3",
        jwt_secret=JWT_SECRET,
        env_overrides={"XQWEB_ROOM_COUNT": str(ROOM_COUNT)},
    ) as server:
        yield server.base_url


def _assert_error_payload(*, response: httpx.Response, expected_status: int) -> dict[str, object]:
    """Assert unified REST error contract and return parsed payload."""
    assert response.status_code == expected_status
    payload = response.json()
    assert {"code", "message", "detail"} <= set(payload)
    return payload


def _register_user(*, client: httpx.Client, username: str) -> tuple[int, str]:
    """Register one user and return (user_id, access_token)."""
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "123"},
    )
    assert response.status_code == 200
    payload = response.json()
    return int(payload["user"]["id"]), str(payload["access_token"])


def test_m2_rs_rest_01_rooms_initialized_as_preset_waiting_rooms(live_server: str) -> None:
    """M2-RS-REST-01: /api/rooms reflects preset room initialization."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        _, access_token = _register_user(client=client, username="r201u")
        response = client.get(
            "/api/rooms",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == ROOM_COUNT
    assert [room["room_id"] for room in payload] == list(range(ROOM_COUNT))

    for room in payload:
        assert {"room_id", "status", "player_count", "ready_count"} <= set(room)
        assert room["status"] == "waiting"
        assert room["player_count"] == 0
        assert room["ready_count"] == 0


def test_m2_rs_rest_02_rooms_list_rejects_missing_token(live_server: str) -> None:
    """M2-RS-REST-02: /api/rooms rejects missing token with 401."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        response = client.get("/api/rooms")

    _assert_error_payload(response=response, expected_status=401)


def test_m2_rs_rest_03_room_detail_success(live_server: str) -> None:
    """M2-RS-REST-03: /api/rooms/{room_id} returns room_detail for valid room."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        _, access_token = _register_user(client=client, username="r203u")
        response = client.get(
            "/api/rooms/0",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["room_id"] == 0
    assert payload["status"] == "waiting"
    assert payload["owner_id"] is None
    assert payload["members"] == []
    assert payload["current_game_id"] is None


def test_m2_rs_rest_04_room_detail_404_for_invalid_room_id(live_server: str) -> None:
    """M2-RS-REST-04: /api/rooms/{room_id} returns ROOM_NOT_FOUND for invalid room."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        _, access_token = _register_user(client=client, username="r204u")
        response = client.get(
            "/api/rooms/9999",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    payload = _assert_error_payload(response=response, expected_status=404)
    assert payload["code"] == "ROOM_NOT_FOUND"
    assert payload["message"] == "room not found"
    assert payload["detail"] == {"room_id": 9999}


def test_m2_rs_rest_05_first_join_sets_owner_seat_and_initial_chips(live_server: str) -> None:
    """M2-RS-REST-05: first join sets owner, seat=0, and chips=20."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        user_id, access_token = _register_user(client=client, username="r205u")
        response = client.post(
            "/api/rooms/0/join",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["room_id"] == 0
    assert payload["status"] == "waiting"
    assert payload["owner_id"] == user_id
    assert payload["current_game_id"] is None

    assert len(payload["members"]) == 1
    member = payload["members"][0]
    assert member["user_id"] == user_id
    assert member["username"] == "r205u"
    assert member["seat"] == 0
    assert member["ready"] is False
    assert member["chips"] == 20


def test_m2_rs_rest_06_sequential_join_assigns_min_available_seats(live_server: str) -> None:
    """M2-RS-REST-06: sequential joins assign seats 0/1/2 in order."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        user_a_id, token_a = _register_user(client=client, username="r206a")
        user_b_id, token_b = _register_user(client=client, username="r206b")
        user_c_id, token_c = _register_user(client=client, username="r206c")

        assert client.post("/api/rooms/0/join", headers={"Authorization": f"Bearer {token_a}"}).status_code == 200
        assert client.post("/api/rooms/0/join", headers={"Authorization": f"Bearer {token_b}"}).status_code == 200
        assert client.post("/api/rooms/0/join", headers={"Authorization": f"Bearer {token_c}"}).status_code == 200

        detail = client.get("/api/rooms/0", headers={"Authorization": f"Bearer {token_a}"})

    assert detail.status_code == 200
    members = detail.json()["members"]
    seat_map = {member["user_id"]: member["seat"] for member in members}
    assert seat_map[user_a_id] == 0
    assert seat_map[user_b_id] == 1
    assert seat_map[user_c_id] == 2


def test_m2_rs_rest_07_join_rejects_when_room_is_full(live_server: str) -> None:
    """M2-RS-REST-07: 4th user join returns 409 + ROOM_FULL."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        tokens: list[str] = []
        for username in ("r207a", "r207b", "r207c", "r207d"):
            _, token = _register_user(client=client, username=username)
            tokens.append(token)

        for token in tokens[:3]:
            response = client.post("/api/rooms/0/join", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200

        overflow = client.post("/api/rooms/0/join", headers={"Authorization": f"Bearer {tokens[3]}"})

    payload = _assert_error_payload(response=overflow, expected_status=409)
    assert payload["code"] == "ROOM_FULL"
    assert payload["message"] == "room is full"
    assert payload["detail"] == {"room_id": 0}


def test_m2_rs_rest_08_same_room_join_is_idempotent(live_server: str) -> None:
    """M2-RS-REST-08: joining same room twice keeps one member record and same seat."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        user_id, access_token = _register_user(client=client, username="r208u")
        headers = {"Authorization": f"Bearer {access_token}"}

        first_join = client.post("/api/rooms/0/join", headers=headers)
        second_join = client.post("/api/rooms/0/join", headers=headers)
        detail = client.get("/api/rooms/0", headers=headers)

    assert first_join.status_code == 200
    assert second_join.status_code == 200
    assert detail.status_code == 200

    members = detail.json()["members"]
    own_members = [member for member in members if member["user_id"] == user_id]
    assert len(own_members) == 1
    assert own_members[0]["seat"] == 0
    assert len(members) == 1


def test_m2_rs_rest_09_cross_room_join_migrates_membership(live_server: str) -> None:
    """M2-RS-REST-09: join room B after room A migrates membership atomically."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        user_id, access_token = _register_user(client=client, username="r209u")
        headers = {"Authorization": f"Bearer {access_token}"}

        assert client.post("/api/rooms/0/join", headers=headers).status_code == 200
        migrate = client.post("/api/rooms/1/join", headers=headers)
        room0 = client.get("/api/rooms/0", headers=headers)
        room1 = client.get("/api/rooms/1", headers=headers)

    assert migrate.status_code == 200
    assert room0.status_code == 200
    assert room1.status_code == 200
    assert all(member["user_id"] != user_id for member in room0.json()["members"])
    assert sum(1 for member in room1.json()["members"] if member["user_id"] == user_id) == 1


def test_m2_rs_rest_10_cross_room_join_rollback_when_target_full(live_server: str) -> None:
    """M2-RS-REST-10: failed migration to full room keeps source membership unchanged."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        src_user_id, src_token = _register_user(client=client, username="r210s")
        src_headers = {"Authorization": f"Bearer {src_token}"}

        first_join = client.post("/api/rooms/0/join", headers=src_headers)
        assert first_join.status_code == 200
        source_seat = first_join.json()["members"][0]["seat"]

        for username in ("r210a", "r210b", "r210c"):
            _, token = _register_user(client=client, username=username)
            fill_resp = client.post("/api/rooms/1/join", headers={"Authorization": f"Bearer {token}"})
            assert fill_resp.status_code == 200

        overflow = client.post("/api/rooms/1/join", headers=src_headers)
        room0 = client.get("/api/rooms/0", headers=src_headers)
        room1 = client.get("/api/rooms/1", headers=src_headers)

    payload = _assert_error_payload(response=overflow, expected_status=409)
    assert payload["code"] == "ROOM_FULL"
    assert payload["message"] == "room is full"
    assert payload["detail"] == {"room_id": 1}

    assert room0.status_code == 200
    assert room1.status_code == 200

    room0_members = room0.json()["members"]
    room1_members = room1.json()["members"]
    source_member = [member for member in room0_members if member["user_id"] == src_user_id]
    assert len(source_member) == 1
    assert source_member[0]["seat"] == source_seat
    assert all(member["user_id"] != src_user_id for member in room1_members)
