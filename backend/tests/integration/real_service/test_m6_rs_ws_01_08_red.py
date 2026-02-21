"""Red-phase websocket tests against a live M6 backend service (WS 01~08)."""

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

JWT_SECRET = "m6-rs-ws-red-test-secret-key-32-bytes-minimum"
ROOM_COUNT = 3


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[tuple[str, str], None, None]:
    """Start one real uvicorn backend per test case."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m6_rs_ws_01_08_red.sqlite3",
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


def _leave_room(*, base_url: str, access_token: str, room_id: int) -> None:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(
            f"/api/rooms/{room_id}/leave",
            headers=_auth_headers(access_token),
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


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


async def _recv_optional_business_event(ws: Any, *, timeout_seconds: float = 0.6) -> dict[str, Any] | None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        try:
            event = await _recv_json_event(ws, timeout_seconds=remaining)
        except TimeoutError:
            return None
        if event.get("type") in {"PING", "PONG"}:
            continue
        return event


def test_m6_rs_ws_01_room_snapshot_with_game_ordered(live_server: tuple[str, str]) -> None:
    """M6-RS-WS-01: room snapshot with game keeps ordered ROOM/PUBLIC/PRIVATE events."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rsws01")
    token = context["token_by_seat"][0]
    game_id = context["game_id"]
    expected_state = _get_game_state(base_url=base_url, access_token=token, game_id=game_id)
    expected_version = int(expected_state["public_state"]["version"])

    async def _run() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            room_event = await _recv_until(
                ws,
                event_type="ROOM_UPDATE",
                predicate=lambda event: event["payload"]["room"]["current_game_id"] == game_id,
            )
            public_event = await _recv_until(
                ws,
                event_type="GAME_PUBLIC_STATE",
                predicate=lambda event: event["payload"]["game_id"] == game_id,
            )
            private_event = await _recv_until(
                ws,
                event_type="GAME_PRIVATE_STATE",
                predicate=lambda event: event["payload"]["game_id"] == game_id,
            )
            assert room_event["type"] == "ROOM_UPDATE"
            assert public_event["type"] == "GAME_PUBLIC_STATE"
            assert private_event["type"] == "GAME_PRIVATE_STATE"
            assert int(public_event["payload"]["public_state"]["version"]) == expected_version
            assert int(private_event["payload"]["self_seat"]) == 0

    asyncio.run(_run())


def test_m6_rs_ws_02_room_snapshot_without_game_only_room_update(live_server: tuple[str, str]) -> None:
    """M6-RS-WS-02: room snapshot without game should contain ROOM_UPDATE only."""
    base_url, ws_base_url = live_server
    _, access_token = _register_user(base_url=base_url, username="m6rsws02")
    _join_room(base_url=base_url, access_token=access_token, room_id=0)

    async def _run() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={access_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            room_event = await _recv_until(ws, event_type="ROOM_UPDATE")
            payload_room = room_event["payload"]["room"]
            assert payload_room["room_id"] == 0
            assert payload_room["current_game_id"] is None

            unexpected = await _recv_optional_business_event(ws, timeout_seconds=0.6)
            assert unexpected is None

    asyncio.run(_run())


def test_m6_rs_ws_03_action_push_order_and_version_monotonic(live_server: tuple[str, str]) -> None:
    """M6-RS-WS-03: action push order is PUBLIC then PRIVATE and version increments."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rsws03")
    game_id = context["game_id"]
    listener_token = context["token_by_seat"][0]

    probe_state = _get_game_state(base_url=base_url, access_token=listener_token, game_id=game_id)
    version_before = int(probe_state["public_state"]["version"])
    actor_seat = int(probe_state["public_state"]["turn"]["current_seat"])
    actor_token = context["token_by_seat"][actor_seat]
    actor_state = _get_game_state(base_url=base_url, access_token=actor_token, game_id=game_id)
    action_payload = _build_action_payload_from_state(state_payload=actor_state)

    async def _run() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={listener_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            await _recv_until(ws, event_type="ROOM_UPDATE")
            await _recv_until(ws, event_type="GAME_PUBLIC_STATE", predicate=lambda event: event["payload"]["game_id"] == game_id)
            await _recv_until(ws, event_type="GAME_PRIVATE_STATE", predicate=lambda event: event["payload"]["game_id"] == game_id)

            await asyncio.to_thread(
                _post_game_action,
                base_url=base_url,
                access_token=actor_token,
                game_id=game_id,
                payload=action_payload,
            )

            public_event = await _recv_until(
                ws,
                event_type="GAME_PUBLIC_STATE",
                predicate=lambda event: event["payload"]["game_id"] == game_id,
            )
            private_event = await _recv_until(
                ws,
                event_type="GAME_PRIVATE_STATE",
                predicate=lambda event: event["payload"]["game_id"] == game_id,
            )

            version_after = int(public_event["payload"]["public_state"]["version"])
            assert version_after == version_before + 1
            assert int(private_event["payload"]["self_seat"]) == 0

    asyncio.run(_run())


def test_m6_rs_ws_04_private_state_unicast_without_leak(live_server: tuple[str, str]) -> None:
    """M6-RS-WS-04: GAME_PRIVATE_STATE should stay unicast per connection seat."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rsws04")
    game_id = context["game_id"]
    token0 = context["token_by_seat"][0]
    token1 = context["token_by_seat"][1]

    probe_state = _get_game_state(base_url=base_url, access_token=token0, game_id=game_id)
    actor_seat = int(probe_state["public_state"]["turn"]["current_seat"])
    actor_token = context["token_by_seat"][actor_seat]
    actor_state = _get_game_state(base_url=base_url, access_token=actor_token, game_id=game_id)
    action_payload = _build_action_payload_from_state(state_payload=actor_state)

    async def _run() -> None:
        async with (
            websockets.connect(
                f"{ws_base_url}/ws/rooms/0?token={token0}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as ws0,
            websockets.connect(
                f"{ws_base_url}/ws/rooms/0?token={token1}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as ws1,
        ):
            await _recv_until(ws0, event_type="ROOM_UPDATE")
            await _recv_until(ws0, event_type="GAME_PUBLIC_STATE", predicate=lambda event: event["payload"]["game_id"] == game_id)
            await _recv_until(ws0, event_type="GAME_PRIVATE_STATE", predicate=lambda event: event["payload"]["game_id"] == game_id)
            await _recv_until(ws1, event_type="ROOM_UPDATE")
            await _recv_until(ws1, event_type="GAME_PUBLIC_STATE", predicate=lambda event: event["payload"]["game_id"] == game_id)
            await _recv_until(ws1, event_type="GAME_PRIVATE_STATE", predicate=lambda event: event["payload"]["game_id"] == game_id)

            await asyncio.to_thread(
                _post_game_action,
                base_url=base_url,
                access_token=actor_token,
                game_id=game_id,
                payload=action_payload,
            )

            private0 = await _recv_until(
                ws0,
                event_type="GAME_PRIVATE_STATE",
                predicate=lambda event: event["payload"]["game_id"] == game_id,
            )
            private1 = await _recv_until(
                ws1,
                event_type="GAME_PRIVATE_STATE",
                predicate=lambda event: event["payload"]["game_id"] == game_id,
            )
            assert int(private0["payload"]["self_seat"]) == 0
            assert int(private1["payload"]["self_seat"]) == 1

            maybe_private0 = await _recv_optional_business_event(ws0, timeout_seconds=0.3)
            if maybe_private0 is not None and maybe_private0.get("type") == "GAME_PRIVATE_STATE":
                assert int(maybe_private0["payload"]["self_seat"]) == 0
            maybe_private1 = await _recv_optional_business_event(ws1, timeout_seconds=0.3)
            if maybe_private1 is not None and maybe_private1.get("type") == "GAME_PRIVATE_STATE":
                assert int(maybe_private1["payload"]["self_seat"]) == 1

    asyncio.run(_run())


def test_m6_rs_ws_05_settlement_push_with_room_transition(live_server: tuple[str, str]) -> None:
    """M6-RS-WS-05: entering settlement should push room transition + settlement event."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rsws05")
    game_id = context["game_id"]
    listener_token = context["token_by_seat"][0]

    async def _run() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={listener_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            await _recv_until(ws, event_type="ROOM_UPDATE")
            await asyncio.to_thread(
                _advance_game_until_settlement,
                base_url=base_url,
                game_id=game_id,
                token_by_seat=context["token_by_seat"],
            )

            room_event = await _recv_until(
                ws,
                event_type="ROOM_UPDATE",
                predicate=lambda event: (
                    event["payload"]["room"]["status"] == "settlement"
                    and event["payload"]["room"]["current_game_id"] == game_id
                ),
            )
            settlement_event = await _recv_until(
                ws,
                event_type="SETTLEMENT",
                predicate=lambda event: event["payload"]["game_id"] == game_id,
            )

            assert room_event["payload"]["room"]["status"] == "settlement"
            assert settlement_event["payload"]["final_state"]["phase"] == "settlement"

    asyncio.run(_run())


def test_m6_rs_ws_06_cold_abort_push_without_settlement(live_server: tuple[str, str]) -> None:
    """M6-RS-WS-06: leave during playing should push waiting room update without settlement."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rsws06")
    listener_token = context["token_by_seat"][0]
    leaver_token = context["token_by_seat"][1]

    async def _run() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={listener_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            await _recv_until(ws, event_type="ROOM_UPDATE")
            await asyncio.to_thread(_leave_room, base_url=base_url, access_token=leaver_token, room_id=0)

            room_event = await _recv_until(
                ws,
                event_type="ROOM_UPDATE",
                predicate=lambda event: (
                    event["payload"]["room"]["status"] == "waiting"
                    and event["payload"]["room"]["current_game_id"] is None
                ),
            )
            assert room_event["payload"]["room"]["status"] == "waiting"
            assert room_event["payload"]["room"]["current_game_id"] is None

            next_business_event = await _recv_optional_business_event(ws, timeout_seconds=0.8)
            assert next_business_event is None or next_business_event["type"] != "SETTLEMENT"

    asyncio.run(_run())


def test_m6_rs_ws_07_lobby_and_room_consistency(live_server: tuple[str, str]) -> None:
    """M6-RS-WS-07: lobby ROOM_LIST and room ROOM_UPDATE stay consistent on same change."""
    base_url, ws_base_url = live_server
    _, listener_token = _register_user(base_url=base_url, username="m6rsws07l")
    actor_id, actor_token = _register_user(base_url=base_url, username="m6rsws07a")
    _join_room(base_url=base_url, access_token=listener_token, room_id=0)

    async def _run() -> None:
        async with (
            websockets.connect(
                f"{ws_base_url}/ws/lobby?token={listener_token}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as lobby_ws,
            websockets.connect(
                f"{ws_base_url}/ws/rooms/0?token={listener_token}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as room_ws,
        ):
            await _recv_until(lobby_ws, event_type="ROOM_LIST")
            await _recv_until(room_ws, event_type="ROOM_UPDATE")

            await asyncio.to_thread(_join_room, base_url=base_url, access_token=actor_token, room_id=0)

            lobby_event = await _recv_until(
                lobby_ws,
                event_type="ROOM_LIST",
                predicate=lambda event: any(
                    room["room_id"] == 0 and room["player_count"] == 2 for room in event["payload"]["rooms"]
                ),
            )
            room_event = await _recv_until(
                room_ws,
                event_type="ROOM_UPDATE",
                predicate=lambda event: any(
                    member["user_id"] == actor_id for member in event["payload"]["room"]["members"]
                ),
            )

            room_summary = next(room for room in lobby_event["payload"]["rooms"] if room["room_id"] == 0)
            room_detail = room_event["payload"]["room"]
            assert room_summary["status"] == room_detail["status"]
            assert int(room_summary["player_count"]) == len(room_detail["members"])
            ready_count = sum(1 for member in room_detail["members"] if member["ready"])
            assert int(room_summary["ready_count"]) == ready_count

    asyncio.run(_run())


def test_m6_rs_ws_08_multi_client_public_stream_consistent(live_server: tuple[str, str]) -> None:
    """M6-RS-WS-08: all online room clients observe same public stream sequence."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rsws08")
    game_id = context["game_id"]
    token0 = context["token_by_seat"][0]
    token1 = context["token_by_seat"][1]
    token2 = context["token_by_seat"][2]

    async def _run() -> None:
        async with (
            websockets.connect(
                f"{ws_base_url}/ws/rooms/0?token={token0}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as ws0,
            websockets.connect(
                f"{ws_base_url}/ws/rooms/0?token={token1}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as ws1,
            websockets.connect(
                f"{ws_base_url}/ws/rooms/0?token={token2}",
                open_timeout=3,
                close_timeout=3,
                ping_interval=None,
                proxy=None,
            ) as ws2,
        ):
            streams = {0: ws0, 1: ws1, 2: ws2}
            initial_versions: dict[int, int] = {}

            for seat, ws in streams.items():
                await _recv_until(ws, event_type="ROOM_UPDATE")
                public_event = await _recv_until(
                    ws,
                    event_type="GAME_PUBLIC_STATE",
                    predicate=lambda event: event["payload"]["game_id"] == game_id,
                )
                await _recv_until(
                    ws,
                    event_type="GAME_PRIVATE_STATE",
                    predicate=lambda event: event["payload"]["game_id"] == game_id,
                )
                initial_versions[seat] = int(public_event["payload"]["public_state"]["version"])

            assert len(set(initial_versions.values())) == 1
            expected_version = next(iter(initial_versions.values()))

            for _ in range(2):
                probe_state = await asyncio.to_thread(
                    _get_game_state,
                    base_url=base_url,
                    access_token=token0,
                    game_id=game_id,
                )
                current_seat = int(probe_state["public_state"]["turn"]["current_seat"])
                actor_token = context["token_by_seat"][current_seat]
                actor_state = await asyncio.to_thread(
                    _get_game_state,
                    base_url=base_url,
                    access_token=actor_token,
                    game_id=game_id,
                )
                action_payload = _build_action_payload_from_state(state_payload=actor_state)
                await asyncio.to_thread(
                    _post_game_action,
                    base_url=base_url,
                    access_token=actor_token,
                    game_id=game_id,
                    payload=action_payload,
                )

                observed_versions: list[int] = []
                for ws in (ws0, ws1, ws2):
                    public_event = await _recv_until(
                        ws,
                        event_type="GAME_PUBLIC_STATE",
                        predicate=lambda event: event["payload"]["game_id"] == game_id,
                    )
                    observed_versions.append(int(public_event["payload"]["public_state"]["version"]))

                expected_version += 1
                assert observed_versions == [expected_version, expected_version, expected_version]

    asyncio.run(_run())
