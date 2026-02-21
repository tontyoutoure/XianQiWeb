"""Red-phase REST tests against a live M4 backend service (API 01~14)."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import httpx
import pytest
from tests.integration.real_service.live_server import run_live_server

JWT_SECRET = "m4-rs-red-test-secret-key-32-bytes-minimum"
ROOM_COUNT = 3


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[str, None, None]:
    """Start a real uvicorn process for one test case."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m4_rs_rest_01_14_red.sqlite3",
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

    assert set(token_by_seat.keys()) == {0, 1, 2}
    return {"game_id": game_id, "token_by_seat": token_by_seat}


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
    assert len(actions) > 0

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


def test_m4_rs_rest_01_get_state_success(live_server: str) -> None:
    """M4-API-01: GET /api/games/{id}/state success."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m401")
        response = client.get(
            f"/api/games/{context['game_id']}/state",
            headers=_auth_headers(context["token_by_seat"][0]),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["game_id"] == context["game_id"]
    assert payload["self_seat"] == 0
    assert {"public_state", "private_state", "legal_actions"} <= set(payload)


def test_m4_rs_rest_02_get_state_forbidden_non_member(live_server: str) -> None:
    """M4-API-02: /state rejects non-member."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m402")
        _, outsider_token = _register_user(client=client, username="m402x")

        response = client.get(
            f"/api/games/{context['game_id']}/state",
            headers=_auth_headers(outsider_token),
        )

    payload = _assert_error_payload(response=response, expected_status=403)
    assert payload["code"] in {"GAME_FORBIDDEN", "ROOM_NOT_MEMBER"}


def test_m4_rs_rest_03_get_state_game_not_found(live_server: str) -> None:
    """M4-API-03: /state returns GAME_NOT_FOUND for unknown game."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        _, access_token = _register_user(client=client, username="m403u")
        response = client.get(
            "/api/games/999999/state",
            headers=_auth_headers(access_token),
        )

    payload = _assert_error_payload(response=response, expected_status=404)
    assert payload["code"] == "GAME_NOT_FOUND"
    assert payload["detail"] == {"game_id": 999999}


def test_m4_rs_rest_04_post_actions_success_version_increments(live_server: str) -> None:
    """M4-API-04: /actions success and version increments."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m404")
        game_id = context["game_id"]

        probe_state = client.get(
            f"/api/games/{game_id}/state",
            headers=_auth_headers(context["token_by_seat"][0]),
        )
        assert probe_state.status_code == 200
        probe_payload = probe_state.json()

        current_seat = int(probe_payload["public_state"]["turn"]["current_seat"])
        actor_token = context["token_by_seat"][current_seat]

        before_state = client.get(f"/api/games/{game_id}/state", headers=_auth_headers(actor_token))
        assert before_state.status_code == 200
        before_payload = before_state.json()
        before_version = int(before_payload["public_state"]["version"])

        action_payload = _build_action_payload_from_state(state_payload=before_payload)
        action_response = client.post(
            f"/api/games/{game_id}/actions",
            headers=_auth_headers(actor_token),
            json=action_payload,
        )

        after_state = client.get(f"/api/games/{game_id}/state", headers=_auth_headers(actor_token))

    assert action_response.status_code == 204
    assert after_state.status_code == 200
    assert int(after_state.json()["public_state"]["version"]) == before_version + 1


def test_m4_rs_rest_05_post_actions_version_conflict(live_server: str) -> None:
    """M4-API-05: /actions rejects stale client_version."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m405")
        game_id = context["game_id"]

        probe_state = client.get(
            f"/api/games/{game_id}/state",
            headers=_auth_headers(context["token_by_seat"][0]),
        )
        assert probe_state.status_code == 200
        probe_payload = probe_state.json()

        current_seat = int(probe_payload["public_state"]["turn"]["current_seat"])
        actor_token = context["token_by_seat"][current_seat]

        before_state = client.get(f"/api/games/{game_id}/state", headers=_auth_headers(actor_token))
        assert before_state.status_code == 200
        before_payload = before_state.json()
        stale_version = int(before_payload["public_state"]["version"])

        first_action_payload = _build_action_payload_from_state(
            state_payload=before_payload,
            client_version=stale_version,
        )
        first_action_response = client.post(
            f"/api/games/{game_id}/actions",
            headers=_auth_headers(actor_token),
            json=first_action_payload,
        )
        assert first_action_response.status_code == 204

        fresh_probe = client.get(
            f"/api/games/{game_id}/state",
            headers=_auth_headers(context["token_by_seat"][0]),
        )
        assert fresh_probe.status_code == 200
        fresh_payload = fresh_probe.json()
        next_seat = int(fresh_payload["public_state"]["turn"]["current_seat"])
        next_actor_token = context["token_by_seat"][next_seat]

        next_actor_state = client.get(f"/api/games/{game_id}/state", headers=_auth_headers(next_actor_token))
        assert next_actor_state.status_code == 200
        stale_payload = _build_action_payload_from_state(
            state_payload=next_actor_state.json(),
            client_version=stale_version,
        )
        conflict_response = client.post(
            f"/api/games/{game_id}/actions",
            headers=_auth_headers(next_actor_token),
            json=stale_payload,
        )

    payload = _assert_error_payload(response=conflict_response, expected_status=409)
    assert payload["code"] == "GAME_VERSION_CONFLICT"


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_06_post_actions_reject_non_turn_player() -> None:
    """M4-API-06: /actions rejects non-turn player."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_07_post_actions_reject_invalid_cover_list() -> None:
    """M4-API-07: /actions rejects invalid cover_list."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_08_post_actions_forbidden_non_member() -> None:
    """M4-API-08: /actions rejects non-member."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_09_post_actions_game_not_found() -> None:
    """M4-API-09: /actions returns GAME_NOT_FOUND for unknown game."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_10_get_settlement_phase_gate() -> None:
    """M4-API-10: /settlement phase gate."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_11_get_settlement_success() -> None:
    """M4-API-11: /settlement success in settlement/finished phase."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_12_ready_reset_after_settlement() -> None:
    """M4-API-12: ready flags are reset after settlement."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_13_all_ready_in_settlement_starts_new_game() -> None:
    """M4-API-13: all ready in settlement starts a new game."""
    pass


@pytest.mark.skip(reason="M4 scaffold only; test body pending")
def test_m4_rs_rest_14_partial_ready_in_settlement_not_start() -> None:
    """M4-API-14: partial ready in settlement does not start a new game."""
    pass
