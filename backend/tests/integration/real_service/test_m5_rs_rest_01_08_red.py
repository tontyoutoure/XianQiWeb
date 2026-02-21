"""Red-phase REST tests against a live M5 backend service (RS-REST-01~08)."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import httpx
import pytest

from tests.integration.real_service.live_server import run_live_server

JWT_SECRET = "m5-rs-red-test-secret-key-32-bytes-minimum"
ROOM_COUNT = 3


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[str, None, None]:
    """Start one real uvicorn server for each test case."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m5_rs_rest_01_08_red.sqlite3",
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


def _advance_game_until_settlement(
    *,
    client: httpx.Client,
    game_id: int,
    token_by_seat: dict[int, str],
    max_steps: int = 80,
) -> dict[str, Any]:
    """Drive one game by actions until /settlement becomes available."""
    observer_token = token_by_seat[0]
    for _ in range(max_steps):
        settlement_response = client.get(
            f"/api/games/{game_id}/settlement",
            headers=_auth_headers(observer_token),
        )
        if settlement_response.status_code == 200:
            settlement_payload = settlement_response.json()
            assert {"final_state", "chip_delta_by_seat"} <= set(settlement_payload)
            return settlement_payload

        conflict_payload = _assert_error_payload(response=settlement_response, expected_status=409)
        assert conflict_payload["code"] == "GAME_STATE_CONFLICT"

        probe_state = client.get(
            f"/api/games/{game_id}/state",
            headers=_auth_headers(observer_token),
        )
        assert probe_state.status_code == 200
        probe_payload = probe_state.json()
        current_seat = int(probe_payload["public_state"]["turn"]["current_seat"])
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


def test_m5_rs_rest_01_get_settlement_success(live_server: str) -> None:
    """M5-RS-REST-01: /settlement success in settlement phase."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m5rs01")
        payload = _advance_game_until_settlement(
            client=client,
            game_id=context["game_id"],
            token_by_seat=context["token_by_seat"],
        )

    final_state = payload["final_state"]
    assert isinstance(final_state, dict)
    assert str(final_state["phase"]) == "settlement"
    assert isinstance(payload["chip_delta_by_seat"], list)
    assert {int(item["seat"]) for item in payload["chip_delta_by_seat"]} == {0, 1, 2}


def test_m5_rs_rest_02_get_settlement_phase_gate(live_server: str) -> None:
    """M5-RS-REST-02: /settlement rejects when phase is not settlement."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m5rs02")
        response = client.get(
            f"/api/games/{context['game_id']}/settlement",
            headers=_auth_headers(context["token_by_seat"][0]),
        )

    payload = _assert_error_payload(response=response, expected_status=409)
    assert payload["code"] == "GAME_STATE_CONFLICT"


def test_m5_rs_rest_03_get_settlement_forbidden_non_member(live_server: str) -> None:
    """M5-RS-REST-03: /settlement rejects non-member access."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m5rs03")
        _advance_game_until_settlement(
            client=client,
            game_id=context["game_id"],
            token_by_seat=context["token_by_seat"],
        )
        _, outsider_token = _register_user(client=client, username="m5rs03x")
        response = client.get(
            f"/api/games/{context['game_id']}/settlement",
            headers=_auth_headers(outsider_token),
        )

    payload = _assert_error_payload(response=response, expected_status=403)
    assert payload["code"] == "GAME_FORBIDDEN"


def test_m5_rs_rest_04_get_settlement_game_not_found(live_server: str) -> None:
    """M5-RS-REST-04: /settlement returns GAME_NOT_FOUND for unknown game."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        _, access_token = _register_user(client=client, username="m5rs04u")
        response = client.get(
            "/api/games/999999/settlement",
            headers=_auth_headers(access_token),
        )

    payload = _assert_error_payload(response=response, expected_status=404)
    assert payload["code"] == "GAME_NOT_FOUND"
    assert payload["detail"] == {"game_id": 999999}


def test_m5_rs_rest_05_ready_reset_after_settlement(live_server: str) -> None:
    """M5-RS-REST-05: room member ready flags are reset after settlement."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m5rs05")
        game_id = context["game_id"]

        _advance_game_until_settlement(
            client=client,
            game_id=game_id,
            token_by_seat=context["token_by_seat"],
        )
        room_response = client.get(
            "/api/rooms/0",
            headers=_auth_headers(context["token_by_seat"][0]),
        )

    assert room_response.status_code == 200
    room_payload = room_response.json()
    assert room_payload["status"] == "settlement"
    assert room_payload["current_game_id"] == game_id
    assert all(member["ready"] is False for member in room_payload["members"])


def test_m5_rs_rest_06_all_ready_in_settlement_starts_new_game(live_server: str) -> None:
    """M5-RS-REST-06: all ready in settlement should create a new game."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m5rs06")
        old_game_id = context["game_id"]
        token_by_seat = context["token_by_seat"]

        _advance_game_until_settlement(
            client=client,
            game_id=old_game_id,
            token_by_seat=token_by_seat,
        )

        for seat in (0, 1, 2):
            ready_response = client.post(
                "/api/rooms/0/ready",
                headers=_auth_headers(token_by_seat[seat]),
                json={"ready": True},
            )
            assert ready_response.status_code == 200

        room_response = client.get("/api/rooms/0", headers=_auth_headers(token_by_seat[0]))

    assert room_response.status_code == 200
    room_payload = room_response.json()
    assert room_payload["status"] == "playing"
    assert isinstance(room_payload["current_game_id"], int)
    assert room_payload["current_game_id"] != old_game_id


def test_m5_rs_rest_07_partial_ready_in_settlement_not_start(live_server: str) -> None:
    """M5-RS-REST-07: partial ready in settlement should not start a new game."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m5rs07")
        old_game_id = context["game_id"]
        token_by_seat = context["token_by_seat"]

        _advance_game_until_settlement(
            client=client,
            game_id=old_game_id,
            token_by_seat=token_by_seat,
        )

        for seat in (0, 1):
            ready_response = client.post(
                "/api/rooms/0/ready",
                headers=_auth_headers(token_by_seat[seat]),
                json={"ready": True},
            )
            assert ready_response.status_code == 200

        room_response = client.get("/api/rooms/0", headers=_auth_headers(token_by_seat[0]))

    assert room_response.status_code == 200
    room_payload = room_response.json()
    assert room_payload["status"] == "settlement"
    assert room_payload["current_game_id"] == old_game_id
    assert sum(1 for member in room_payload["members"] if member["ready"]) == 2


def test_m5_rs_rest_08_ready_forbidden_non_member(live_server: str) -> None:
    """M5-RS-REST-08: non-member ready in settlement should be forbidden."""
    with httpx.Client(base_url=live_server, timeout=3, trust_env=False) as client:
        context = _setup_three_players_and_start_game(client=client, username_prefix="m5rs08")
        game_id = context["game_id"]
        token_by_seat = context["token_by_seat"]

        _advance_game_until_settlement(
            client=client,
            game_id=game_id,
            token_by_seat=token_by_seat,
        )
        outsider_id, outsider_token = _register_user(client=client, username="m5rs08x")
        response = client.post(
            "/api/rooms/0/ready",
            headers=_auth_headers(outsider_token),
            json={"ready": True},
        )

    payload = _assert_error_payload(response=response, expected_status=403)
    assert payload["code"] == "ROOM_NOT_MEMBER"
    assert payload["detail"] == {"room_id": 0, "user_id": outsider_id}
