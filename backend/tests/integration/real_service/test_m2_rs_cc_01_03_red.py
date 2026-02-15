"""Red-phase real-service concurrency tests for M2 room contracts (CC 01~03)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest

from tests.integration.real_service.live_server import run_live_server

JWT_SECRET = "m2-rs-cc-red-test-secret-key-32-bytes-minimum"
ROOM_COUNT = 3


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[str, None, None]:
    """Start one live uvicorn backend per test case."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m2_rs_cc_01_03_red.sqlite3",
        jwt_secret=JWT_SECRET,
        env_overrides={"XQWEB_ROOM_COUNT": str(ROOM_COUNT)},
    ) as server:
        yield server.base_url


def _register_user(*, client: httpx.Client, username: str) -> tuple[int, str]:
    """Register one test user and return (user_id, access_token)."""
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "123"},
    )
    assert response.status_code == 200
    payload = response.json()
    return int(payload["user"]["id"]), str(payload["access_token"])


def test_m2_rs_cc_01_concurrent_join_does_not_overfill_or_duplicate_seat(live_server: str) -> None:
    """M2-RS-CC-01: concurrent joins keep room size <= 3 and seat unique."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        tokens: list[str] = []
        for idx in range(8):
            _, token = _register_user(client=client, username=f"rcc1u{idx}")
            tokens.append(token)

    start_barrier = threading.Barrier(len(tokens))

    def _join_worker(access_token: str) -> int:
        start_barrier.wait()
        with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
            response = client.post(
                "/api/rooms/0/join",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=len(tokens)) as executor:
        statuses = list(executor.map(_join_worker, tokens))

    assert all(status in {200, 409} for status in statuses)
    assert sum(1 for status in statuses if status == 200) <= 3

    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        detail = client.get(
            "/api/rooms/0",
            headers={"Authorization": f"Bearer {tokens[0]}"},
        )
    assert detail.status_code == 200
    members = detail.json()["members"]
    seats = [member["seat"] for member in members]
    assert len(members) <= 3
    assert len(seats) == len(set(seats))


def test_m2_rs_cc_02_concurrent_ready_updates_keep_ready_count_consistent(live_server: str) -> None:
    """M2-RS-CC-02: concurrent ready updates keep ready_count in sync."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        tokens: list[str] = []
        for idx in range(3):
            _, token = _register_user(client=client, username=f"rcc2u{idx}")
            tokens.append(token)

        for token in tokens:
            join = client.post("/api/rooms/0/join", headers={"Authorization": f"Bearer {token}"})
            assert join.status_code == 200

    start_barrier = threading.Barrier(len(tokens))

    def _ready_worker(access_token: str) -> int:
        start_barrier.wait()
        with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
            response = client.post(
                "/api/rooms/0/ready",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"ready": True},
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=len(tokens)) as executor:
        statuses = list(executor.map(_ready_worker, tokens))

    assert statuses == [200, 200, 200]

    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        detail = client.get(
            "/api/rooms/0",
            headers={"Authorization": f"Bearer {tokens[0]}"},
        )
        summary_list = client.get(
            "/api/rooms",
            headers={"Authorization": f"Bearer {tokens[0]}"},
        )
    assert detail.status_code == 200
    assert summary_list.status_code == 200
    payload = detail.json()
    ready_count = sum(1 for member in payload["members"] if member["ready"] is True)
    room0_summary = next(room for room in summary_list.json() if room["room_id"] == 0)
    assert ready_count == 3
    assert room0_summary["ready_count"] == ready_count


def test_m2_rs_cc_03_concurrent_cross_room_swap_completes_without_deadlock(live_server: str) -> None:
    """M2-RS-CC-03: concurrent A->B and B->A room swap should both complete."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        user_a_id, token_a = _register_user(client=client, username="rcc3ua")
        user_b_id, token_b = _register_user(client=client, username="rcc3ub")

        assert client.post("/api/rooms/0/join", headers={"Authorization": f"Bearer {token_a}"}).status_code == 200
        assert client.post("/api/rooms/1/join", headers={"Authorization": f"Bearer {token_b}"}).status_code == 200

    start_barrier = threading.Barrier(2)

    def _swap_worker(access_token: str, target_room_id: int) -> int:
        start_barrier.wait()
        with httpx.Client(base_url=live_server, timeout=1.5, trust_env=False) as client:
            response = client.post(
                f"/api/rooms/{target_room_id}/join",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        status_a, status_b = executor.map(
            lambda item: _swap_worker(*item),
            ((token_a, 1), (token_b, 0)),
        )

    assert status_a == 200
    assert status_b == 200

    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        room0 = client.get("/api/rooms/0", headers={"Authorization": f"Bearer {token_a}"})
        room1 = client.get("/api/rooms/1", headers={"Authorization": f"Bearer {token_a}"})

    assert room0.status_code == 200
    assert room1.status_code == 200
    room0_member_ids = {member["user_id"] for member in room0.json()["members"]}
    room1_member_ids = {member["user_id"] for member in room1.json()["members"]}
    assert user_b_id in room0_member_ids
    assert user_a_id in room1_member_ids
