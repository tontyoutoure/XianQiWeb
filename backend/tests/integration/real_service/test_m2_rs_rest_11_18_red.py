"""Red-phase REST tests against a live M2 backend service (Rooms 11~18)."""

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
        db_filename="m2_rs_rest_11_18_red.sqlite3",
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


def _to_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _setup_three_members_in_room_0(
    *,
    client: httpx.Client,
    username_prefix: str,
) -> list[tuple[int, str]]:
    users: list[tuple[int, str]] = []
    for idx in range(3):
        user_id, token = _register_user(client=client, username=f"{username_prefix}{idx}")
        users.append((user_id, token))

    for _, token in users:
        response = client.post("/api/rooms/0/join", headers=_to_headers(token))
        assert response.status_code == 200

    return users


def _make_room_non_waiting_or_skip(*, client: httpx.Client, users: list[tuple[int, str]]) -> dict[str, object]:
    """Try to move room out of waiting via all-ready; skip when M3 hook is not integrated yet."""
    for _, token in users:
        response = client.post(
            "/api/rooms/0/ready",
            headers=_to_headers(token),
            json={"ready": True},
        )
        assert response.status_code == 200

    detail = client.get("/api/rooms/0", headers=_to_headers(users[0][1]))
    assert detail.status_code == 200
    room = detail.json()

    if room["status"] == "waiting":
        pytest.skip("M2 real-service cannot enter non-waiting room yet (M3 game hook not integrated)")

    return room


def test_m2_rs_rest_11_leave_success_and_owner_transfer(live_server: str) -> None:
    """M2-RS-REST-11: owner leave succeeds and owner transfers to earliest remaining member."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        users = _setup_three_members_in_room_0(client=client, username_prefix="r211")
        first_id, first_token = users[0]
        second_id, second_token = users[1]

        leave = client.post("/api/rooms/0/leave", headers=_to_headers(first_token))
        detail = client.get("/api/rooms/0", headers=_to_headers(second_token))

    assert leave.status_code == 200
    assert leave.json() == {"ok": True}
    assert detail.status_code == 200

    room = detail.json()
    assert room["owner_id"] == second_id
    assert all(member["user_id"] != first_id for member in room["members"])


def test_m2_rs_rest_12_leave_rejects_non_member(live_server: str) -> None:
    """M2-RS-REST-12: leave by non-member returns 403 + ROOM_NOT_MEMBER."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        user_id, token = _register_user(client=client, username="r212u")
        response = client.post("/api/rooms/0/leave", headers=_to_headers(token))

    payload = _assert_error_payload(response=response, expected_status=403)
    assert payload["code"] == "ROOM_NOT_MEMBER"
    assert payload["message"] == "user is not a room member"
    assert payload["detail"] == {"room_id": 0, "user_id": user_id}


def test_m2_rs_rest_13_ready_toggle_success_for_waiting_member(live_server: str) -> None:
    """M2-RS-REST-13: waiting member can toggle ready true/false successfully."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        user_id, token = _register_user(client=client, username="r213u")
        headers = _to_headers(token)

        assert client.post("/api/rooms/0/join", headers=headers).status_code == 200

        ready_true = client.post("/api/rooms/0/ready", headers=headers, json={"ready": True})
        ready_false = client.post("/api/rooms/0/ready", headers=headers, json={"ready": False})
        rooms = client.get("/api/rooms", headers=headers)

    assert ready_true.status_code == 200
    member_true = next(item for item in ready_true.json()["members"] if item["user_id"] == user_id)
    assert member_true["ready"] is True

    assert ready_false.status_code == 200
    member_false = next(item for item in ready_false.json()["members"] if item["user_id"] == user_id)
    assert member_false["ready"] is False

    assert rooms.status_code == 200
    room0 = next(item for item in rooms.json() if item["room_id"] == 0)
    assert room0["ready_count"] == 0


def test_m2_rs_rest_14_ready_rejects_non_member(live_server: str) -> None:
    """M2-RS-REST-14: ready by non-member returns 403 + ROOM_NOT_MEMBER."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        user_id, token = _register_user(client=client, username="r214u")
        response = client.post(
            "/api/rooms/0/ready",
            headers=_to_headers(token),
            json={"ready": True},
        )

    payload = _assert_error_payload(response=response, expected_status=403)
    assert payload["code"] == "ROOM_NOT_MEMBER"
    assert payload["message"] == "user is not a room member"
    assert payload["detail"] == {"room_id": 0, "user_id": user_id}


def test_m2_rs_rest_15_all_ready_behavior_matches_current_stage_contract(live_server: str) -> None:
    """M2-RS-REST-15: three members ready=true should match M2 placeholder or M3 playing behavior."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        users = _setup_three_members_in_room_0(client=client, username_prefix="r215")
        for _, token in users:
            response = client.post(
                "/api/rooms/0/ready",
                headers=_to_headers(token),
                json={"ready": True},
            )
            assert response.status_code == 200

        detail_before = client.get("/api/rooms/0", headers=_to_headers(users[0][1]))
        assert detail_before.status_code == 200
        room_before = detail_before.json()

        # Repeat one ready update to ensure no duplicate start side-effect happens.
        repeat_ready = client.post(
            "/api/rooms/0/ready",
            headers=_to_headers(users[0][1]),
            json={"ready": True},
        )
        assert repeat_ready.status_code == 200

        detail_after = client.get("/api/rooms/0", headers=_to_headers(users[0][1]))
        assert detail_after.status_code == 200
        room_after = detail_after.json()

    assert all(member["ready"] is True for member in room_after["members"])
    assert room_after["status"] in {"waiting", "playing"}

    if room_after["status"] == "waiting":
        assert room_after["current_game_id"] is None
    else:
        assert room_after["current_game_id"] is not None
        assert room_before["current_game_id"] == room_after["current_game_id"]


def test_m2_rs_rest_16_leave_from_non_waiting_triggers_cold_end_reset(live_server: str) -> None:
    """M2-RS-REST-16: leave in non-waiting room should reset waiting/current_game_id/ready and keep chips."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        users = _setup_three_members_in_room_0(client=client, username_prefix="r216")
        _ = _make_room_non_waiting_or_skip(client=client, users=users)

        keep_id, keep_token = users[1]
        leave_id, leave_token = users[0]

        before = client.get("/api/rooms/0", headers=_to_headers(keep_token))
        assert before.status_code == 200
        before_room = before.json()
        before_chips = {member["user_id"]: member["chips"] for member in before_room["members"]}

        leave = client.post("/api/rooms/0/leave", headers=_to_headers(leave_token))
        after = client.get("/api/rooms/0", headers=_to_headers(keep_token))

    assert leave.status_code == 200
    assert leave.json() == {"ok": True}
    assert after.status_code == 200

    room = after.json()
    assert room["status"] == "waiting"
    assert room["current_game_id"] is None
    assert all(member["ready"] is False for member in room["members"])

    current_chips = {member["user_id"]: member["chips"] for member in room["members"]}
    expected_chips = {uid: chips for uid, chips in before_chips.items() if uid != leave_id}
    assert keep_id in current_chips
    assert current_chips == expected_chips


def test_m2_rs_rest_17_ready_rejects_when_room_not_waiting(live_server: str) -> None:
    """M2-RS-REST-17: ready change in non-waiting room returns 409 + ROOM_NOT_WAITING."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        users = _setup_three_members_in_room_0(client=client, username_prefix="r217")
        _ = _make_room_non_waiting_or_skip(client=client, users=users)

        response = client.post(
            "/api/rooms/0/ready",
            headers=_to_headers(users[0][1]),
            json={"ready": False},
        )

    payload = _assert_error_payload(response=response, expected_status=409)
    assert payload["code"] == "ROOM_NOT_WAITING"
    assert payload["message"] == "room is not in waiting status"
    assert payload["detail"] == {"room_id": 0}


def test_m2_rs_rest_18_join_leave_ready_reject_missing_token(live_server: str) -> None:
    """M2-RS-REST-18: join/leave/ready reject missing token with 401."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        join_no_auth = client.post("/api/rooms/0/join")
        leave_no_auth = client.post("/api/rooms/0/leave")
        ready_no_auth = client.post("/api/rooms/0/ready", json={"ready": True})

    _assert_error_payload(response=join_no_auth, expected_status=401)
    _assert_error_payload(response=leave_no_auth, expected_status=401)
    _assert_error_payload(response=ready_no_auth, expected_status=401)
