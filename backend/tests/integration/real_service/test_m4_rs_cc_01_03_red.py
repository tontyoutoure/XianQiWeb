"""Red-phase real-service concurrency tests for M4 contracts (CC 01~03)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
from collections.abc import Generator
from pathlib import Path
from typing import Any

import httpx
import pytest
from tests.integration.real_service.live_server import run_live_server

JWT_SECRET = "m4-rs-cc-red-test-secret-key-32-bytes-minimum"
ROOM_COUNT = 3


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[str, None, None]:
    """Start one live uvicorn backend per test case."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m4_rs_cc_01_03_red.sqlite3",
        jwt_secret=JWT_SECRET,
        env_overrides={"XQWEB_ROOM_COUNT": str(ROOM_COUNT)},
    ) as server:
        yield server.base_url


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _assert_error_payload(*, response: httpx.Response, expected_status: int) -> dict[str, object]:
    assert response.status_code == expected_status
    payload = response.json()
    assert {"code", "message", "detail"} <= set(payload)
    return payload


def _register_user(*, client: httpx.Client, username: str) -> tuple[int, str]:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "123"},
    )
    assert response.status_code == 200
    payload = response.json()
    return int(payload["user"]["id"]), str(payload["access_token"])


def _setup_three_players_and_start_game(
    *,
    client: httpx.Client,
    username_prefix: str,
    room_id: int = 0,
) -> dict[str, Any]:
    users: list[tuple[int, str]] = []
    for idx in range(3):
        users.append(_register_user(client=client, username=f"{username_prefix}{idx}"))

    user_token_by_id = {user_id: token for user_id, token in users}
    for _, token in users:
        join_response = client.post(f"/api/rooms/{room_id}/join", headers=_auth_headers(token))
        assert join_response.status_code == 200
    for _, token in users:
        ready_response = client.post(
            f"/api/rooms/{room_id}/ready",
            headers=_auth_headers(token),
            json={"ready": True},
        )
        assert ready_response.status_code == 200

    room_response = client.get(f"/api/rooms/{room_id}", headers=_auth_headers(users[0][1]))
    assert room_response.status_code == 200
    room_payload = room_response.json()
    assert room_payload["status"] == "playing"
    game_id = room_payload["current_game_id"]
    assert isinstance(game_id, int)

    token_by_seat: dict[int, str] = {}
    for member in room_payload["members"]:
        token_by_seat[int(member["seat"])] = user_token_by_id[int(member["user_id"])]
    assert set(token_by_seat) == {0, 1, 2}

    return {
        "room_id": room_id,
        "game_id": game_id,
        "token_by_seat": token_by_seat,
        "tokens": [token for _, token in users],
    }


def _pick_cover_from_hand(*, hand: dict[str, int], required_count: int) -> dict[str, int]:
    remaining = required_count
    cover_list: dict[str, int] = {}
    for card_type in sorted(hand):
        if remaining == 0:
            break
        take = min(int(hand[card_type]), remaining)
        if take > 0:
            cover_list[card_type] = take
            remaining -= take
    assert remaining == 0
    return cover_list


def _build_action_payload_from_state(*, state_payload: dict[str, Any], client_version: int | None = None) -> dict[str, Any]:
    legal_actions = state_payload.get("legal_actions")
    assert isinstance(legal_actions, dict)
    actions = legal_actions.get("actions")
    assert isinstance(actions, list)
    assert actions

    action_idx = 0
    action = actions[action_idx]
    public_state = state_payload.get("public_state")
    assert isinstance(public_state, dict)
    payload: dict[str, Any] = {
        "action_idx": action_idx,
        "client_version": int(public_state["version"]) if client_version is None else client_version,
    }

    if action.get("type") == "COVER":
        private_state = state_payload.get("private_state")
        assert isinstance(private_state, dict)
        hand = private_state.get("hand")
        assert isinstance(hand, dict)
        required_count = int(action["required_count"])
        payload["cover_list"] = _pick_cover_from_hand(hand=hand, required_count=required_count)

    return payload


def _advance_game_until_settlement(
    *,
    client: httpx.Client,
    game_id: int,
    token_by_seat: dict[int, str],
    max_steps: int = 80,
) -> dict[str, Any]:
    observer_token = token_by_seat[0]
    for _ in range(max_steps):
        settlement_response = client.get(
            f"/api/games/{game_id}/settlement",
            headers=_auth_headers(observer_token),
        )
        if settlement_response.status_code == 200:
            payload = settlement_response.json()
            assert {"final_state", "chip_delta_by_seat"} <= set(payload)
            return payload

        conflict_payload = _assert_error_payload(response=settlement_response, expected_status=409)
        assert conflict_payload["code"] == "GAME_STATE_CONFLICT"

        probe_state = client.get(
            f"/api/games/{game_id}/state",
            headers=_auth_headers(observer_token),
        )
        assert probe_state.status_code == 200
        current_seat = int(probe_state.json()["public_state"]["turn"]["current_seat"])
        actor_token = token_by_seat[current_seat]

        actor_state = client.get(f"/api/games/{game_id}/state", headers=_auth_headers(actor_token))
        assert actor_state.status_code == 200
        action_payload = _build_action_payload_from_state(state_payload=actor_state.json())
        action_response = client.post(
            f"/api/games/{game_id}/actions",
            headers=_auth_headers(actor_token),
            json=action_payload,
        )
        assert action_response.status_code == 204

    pytest.fail(f"game_id={game_id} did not enter settlement within {max_steps} actions")


def test_m4_rs_cc_01_concurrent_actions_single_winner(live_server: str) -> None:
    """M4-CC-01: concurrent same-version actions accept only one winner."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m4cc01")
        game_id = int(context["game_id"])

        observer_token = context["token_by_seat"][0]
        probe_state = client.get(f"/api/games/{game_id}/state", headers=_auth_headers(observer_token))
        assert probe_state.status_code == 200
        current_seat = int(probe_state.json()["public_state"]["turn"]["current_seat"])
        actor_token = context["token_by_seat"][current_seat]

        actor_state = client.get(f"/api/games/{game_id}/state", headers=_auth_headers(actor_token))
        assert actor_state.status_code == 200
        actor_state_payload = actor_state.json()
        before_version = int(actor_state_payload["public_state"]["version"])
        action_payload = _build_action_payload_from_state(state_payload=actor_state_payload)

    start_barrier = threading.Barrier(2)

    def _action_worker() -> tuple[int, str | None]:
        start_barrier.wait()
        with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
            response = client.post(
                f"/api/games/{game_id}/actions",
                headers=_auth_headers(actor_token),
                json=action_payload,
            )
            if response.status_code == 204:
                return response.status_code, None
            payload = _assert_error_payload(response=response, expected_status=409)
            return response.status_code, str(payload["code"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        race_results = list(executor.map(lambda _: _action_worker(), range(2)))

    statuses = [status for status, _ in race_results]
    assert statuses.count(204) == 1
    assert statuses.count(409) == 1
    loser_codes = {code for status, code in race_results if status == 409}
    assert loser_codes <= {"GAME_VERSION_CONFLICT", "GAME_INVALID_ACTION"}

    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        after_state = client.get(f"/api/games/{game_id}/state", headers=_auth_headers(observer_token))
    assert after_state.status_code == 200
    assert int(after_state.json()["public_state"]["version"]) == before_version + 1


def test_m4_rs_cc_02_concurrent_ready_after_settlement_single_new_game(live_server: str) -> None:
    """M4-CC-02: concurrent ready after settlement creates exactly one new game."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m4cc02")
        room_id = int(context["room_id"])
        old_game_id = int(context["game_id"])
        token_by_seat = dict(context["token_by_seat"])
        observer_token = token_by_seat[0]

        _advance_game_until_settlement(client=client, game_id=old_game_id, token_by_seat=token_by_seat)

        room_before = client.get(f"/api/rooms/{room_id}", headers=_auth_headers(observer_token))
        assert room_before.status_code == 200
        room_before_payload = room_before.json()
        assert room_before_payload["status"] == "settlement"
        assert room_before_payload["current_game_id"] == old_game_id
        assert all(member["ready"] is False for member in room_before_payload["members"])

    players = [token_by_seat[seat] for seat in sorted(token_by_seat)]
    start_barrier = threading.Barrier(len(players))

    def _ready_worker(access_token: str) -> tuple[int, int | None]:
        start_barrier.wait()
        with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
            response = client.post(
                f"/api/rooms/{room_id}/ready",
                headers=_auth_headers(access_token),
                json={"ready": True},
            )
            assert response.status_code == 200
            payload = response.json()
            current_game_id = payload.get("current_game_id")
            return response.status_code, int(current_game_id) if isinstance(current_game_id, int) else None

    with ThreadPoolExecutor(max_workers=len(players)) as executor:
        ready_results = list(executor.map(_ready_worker, players))

    assert [status for status, _ in ready_results] == [200, 200, 200]
    new_game_ids = {game_id for _, game_id in ready_results if game_id is not None and game_id != old_game_id}
    assert len(new_game_ids) == 1

    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        final_room = client.get(f"/api/rooms/{room_id}", headers=_auth_headers(observer_token))
    assert final_room.status_code == 200
    final_payload = final_room.json()
    assert final_payload["status"] == "playing"
    assert isinstance(final_payload["current_game_id"], int)
    assert final_payload["current_game_id"] != old_game_id
    assert final_payload["current_game_id"] in new_game_ids


def test_m4_rs_cc_03_concurrent_third_ready_only_one_game_created(live_server: str) -> None:
    """M4-CC-03: concurrent edge around third ready creates only one new game."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m4cc03")
        room_id = int(context["room_id"])
        old_game_id = int(context["game_id"])
        token_by_seat = dict(context["token_by_seat"])
        observer_token = token_by_seat[0]

        _advance_game_until_settlement(client=client, game_id=old_game_id, token_by_seat=token_by_seat)

        for seat in (0, 1):
            ready_response = client.post(
                f"/api/rooms/{room_id}/ready",
                headers=_auth_headers(token_by_seat[seat]),
                json={"ready": True},
            )
            assert ready_response.status_code == 200
            assert ready_response.json()["status"] == "settlement"

    third_token = token_by_seat[2]
    start_barrier = threading.Barrier(2)

    def _third_ready_worker() -> tuple[int, str | None, int | None]:
        start_barrier.wait()
        with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
            response = client.post(
                f"/api/rooms/{room_id}/ready",
                headers=_auth_headers(third_token),
                json={"ready": True},
            )
            if response.status_code == 200:
                payload = response.json()
                current_game_id = payload.get("current_game_id")
                return 200, None, int(current_game_id) if isinstance(current_game_id, int) else None
            payload = _assert_error_payload(response=response, expected_status=409)
            return 409, str(payload["code"]), None

    with ThreadPoolExecutor(max_workers=2) as executor:
        race_results = list(executor.map(lambda _: _third_ready_worker(), range(2)))

    statuses = [status for status, _, _ in race_results]
    assert statuses.count(200) == 1
    assert statuses.count(409) == 1
    loser_codes = {code for status, code, _ in race_results if status == 409}
    assert loser_codes == {"ROOM_NOT_WAITING"}

    successful_game_ids = {
        game_id for status, _, game_id in race_results if status == 200 and game_id is not None and game_id != old_game_id
    }
    assert len(successful_game_ids) == 1
    new_game_id = next(iter(successful_game_ids))

    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        final_room = client.get(f"/api/rooms/{room_id}", headers=_auth_headers(observer_token))
    assert final_room.status_code == 200
    final_payload = final_room.json()
    assert final_payload["status"] == "playing"
    assert final_payload["current_game_id"] == new_game_id
