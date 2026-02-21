"""Red-phase websocket tests against a live M5 backend service (WS 01)."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from collections.abc import Generator
from pathlib import Path
from typing import Any

import httpx
import pytest
import websockets

from tests.integration.real_service.live_server import run_live_server

JWT_SECRET = "m5-rs-ws-red-test-secret-key-32-bytes-minimum"
ROOM_COUNT = 3


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[tuple[str, str], None, None]:
    """Start one real uvicorn backend per test case."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m5_rs_ws_01_red.sqlite3",
        jwt_secret=JWT_SECRET,
        env_overrides={"XQWEB_ROOM_COUNT": str(ROOM_COUNT)},
    ) as server:
        yield server.base_url, server.ws_base_url


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _assert_error_payload(*, response: httpx.Response, expected_status: int) -> dict[str, object]:
    assert response.status_code == expected_status
    payload = response.json()
    assert {"code", "message", "detail"} <= set(payload)
    return payload


def _register_user(*, base_url: str, username: str) -> tuple[int, str]:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(
            "/api/auth/register",
            json={"username": username, "password": "123"},
        )
    assert response.status_code == 200
    payload = response.json()
    return int(payload["user"]["id"]), str(payload["access_token"])


def _join_room(*, base_url: str, access_token: str, room_id: int) -> dict[str, Any]:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(
            f"/api/rooms/{room_id}/join",
            headers=_auth_headers(access_token),
        )
    assert response.status_code == 200
    return dict(response.json())


def _set_room_ready(*, base_url: str, access_token: str, room_id: int, ready: bool) -> dict[str, Any]:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(
            f"/api/rooms/{room_id}/ready",
            headers=_auth_headers(access_token),
            json={"ready": ready},
        )
    assert response.status_code == 200
    return dict(response.json())


def _get_room_detail(*, base_url: str, access_token: str, room_id: int) -> dict[str, Any]:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.get(
            f"/api/rooms/{room_id}",
            headers=_auth_headers(access_token),
        )
    assert response.status_code == 200
    return dict(response.json())


def _get_game_state(*, base_url: str, access_token: str, game_id: int) -> dict[str, Any]:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.get(
            f"/api/games/{game_id}/state",
            headers=_auth_headers(access_token),
        )
    assert response.status_code == 200
    return dict(response.json())


def _post_game_action(*, base_url: str, access_token: str, game_id: int, payload: dict[str, Any]) -> None:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(
            f"/api/games/{game_id}/actions",
            headers=_auth_headers(access_token),
            json=payload,
        )
    assert response.status_code == 204


def _get_game_settlement_response(*, base_url: str, access_token: str, game_id: int) -> httpx.Response:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        return client.get(
            f"/api/games/{game_id}/settlement",
            headers=_auth_headers(access_token),
        )


def _setup_three_players_and_start_game(
    *,
    base_url: str,
    username_prefix: str,
    room_id: int = 0,
) -> dict[str, Any]:
    users: list[tuple[int, str]] = []
    for idx in range(3):
        users.append(_register_user(base_url=base_url, username=f"{username_prefix}{idx}"))

    user_token_by_id = {user_id: token for user_id, token in users}

    for _, token in users:
        _join_room(base_url=base_url, access_token=token, room_id=room_id)
    for _, token in users:
        _set_room_ready(base_url=base_url, access_token=token, room_id=room_id, ready=True)

    room_payload = _get_room_detail(base_url=base_url, access_token=users[0][1], room_id=room_id)
    assert room_payload["status"] == "playing"
    game_id = room_payload["current_game_id"]
    assert isinstance(game_id, int)

    token_by_seat: dict[int, str] = {}
    for member in room_payload["members"]:
        token_by_seat[int(member["seat"])] = user_token_by_id[int(member["user_id"])]
    assert set(token_by_seat) == {0, 1, 2}
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
    base_url: str,
    game_id: int,
    token_by_seat: dict[int, str],
    max_steps: int = 80,
) -> dict[str, Any]:
    observer_token = token_by_seat[0]
    for _ in range(max_steps):
        settlement_response = _get_game_settlement_response(
            base_url=base_url,
            access_token=observer_token,
            game_id=game_id,
        )
        if settlement_response.status_code == 200:
            settlement_payload = settlement_response.json()
            assert {"final_state", "chip_delta_by_seat"} <= set(settlement_payload)
            return settlement_payload

        conflict_payload = _assert_error_payload(response=settlement_response, expected_status=409)
        assert conflict_payload["code"] == "GAME_STATE_CONFLICT"

        probe_state = _get_game_state(base_url=base_url, access_token=observer_token, game_id=game_id)
        current_seat = int(probe_state["public_state"]["turn"]["current_seat"])
        actor_token = token_by_seat[current_seat]
        actor_state = _get_game_state(base_url=base_url, access_token=actor_token, game_id=game_id)
        action_payload = _build_action_payload_from_state(state_payload=actor_state)
        _post_game_action(base_url=base_url, access_token=actor_token, game_id=game_id, payload=action_payload)

    pytest.fail(f"game_id={game_id} did not enter settlement within {max_steps} actions")


async def _recv_json_event(ws: Any, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return dict(json.loads(raw))


async def _recv_until(
    ws: Any,
    *,
    event_type: str,
    timeout_seconds: float = 5.0,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(f"timeout waiting for event_type={event_type}")
        event = await _recv_json_event(ws, timeout_seconds=remaining)
        if event.get("type") in {"PING", "PONG"}:
            continue
        if event.get("type") != event_type:
            continue
        if predicate is not None and not predicate(event):
            continue
        return event


def test_m5_rs_ws_01_reopen_pushes_room_update_and_new_game_frames(live_server: tuple[str, str]) -> None:
    """M5-RS-WS-01: settlement re-ready reopen should push room update + new game frames."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m5rsws01")
    old_game_id = context["game_id"]
    token_by_seat = context["token_by_seat"]
    listener_token = token_by_seat[0]

    _advance_game_until_settlement(base_url=base_url, game_id=old_game_id, token_by_seat=token_by_seat)

    async def _run() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={listener_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            await _recv_until(
                ws,
                event_type="ROOM_UPDATE",
                predicate=lambda event: event["payload"]["room"]["current_game_id"] == old_game_id,
            )
            await _recv_until(
                ws,
                event_type="GAME_PUBLIC_STATE",
                predicate=lambda event: event["payload"]["game_id"] == old_game_id,
            )
            await _recv_until(
                ws,
                event_type="GAME_PRIVATE_STATE",
                predicate=lambda event: event["payload"]["game_id"] == old_game_id,
            )

            third_payload: dict[str, Any] | None = None
            for seat in (0, 1, 2):
                third_payload = await asyncio.to_thread(
                    _set_room_ready,
                    base_url=base_url,
                    access_token=token_by_seat[seat],
                    room_id=0,
                    ready=True,
                )
            assert third_payload is not None
            new_game_id = int(third_payload["current_game_id"])
            assert new_game_id != old_game_id

            room_event = await _recv_until(
                ws,
                event_type="ROOM_UPDATE",
                predicate=lambda event: (
                    event["payload"]["room"]["status"] == "playing"
                    and event["payload"]["room"]["current_game_id"] == new_game_id
                ),
            )
            public_event = await _recv_until(
                ws,
                event_type="GAME_PUBLIC_STATE",
                predicate=lambda event: event["payload"]["game_id"] == new_game_id,
            )
            private_event = await _recv_until(
                ws,
                event_type="GAME_PRIVATE_STATE",
                predicate=lambda event: event["payload"]["game_id"] == new_game_id,
            )

            assert room_event["type"] == "ROOM_UPDATE"
            assert public_event["type"] == "GAME_PUBLIC_STATE"
            assert private_event["type"] == "GAME_PRIVATE_STATE"

    asyncio.run(_run())
