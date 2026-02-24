"""Red-phase reconnect/recovery tests against a live M6 backend service (RC 01~08)."""

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

JWT_SECRET = "m6-rs-rc-red-test-secret-key-32-bytes-minimum"
ROOM_COUNT = 3


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[tuple[str, str], None, None]:
    """Start one real uvicorn backend per test case."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m6_rs_rc_01_08_red.sqlite3",
        jwt_secret=JWT_SECRET,
        env_overrides={"XQWEB_ROOM_COUNT": str(ROOM_COUNT)},
    ) as server:
        yield server.base_url, server.ws_base_url


@pytest.fixture
def live_server_short_access(tmp_path: Path) -> Generator[tuple[str, str], None, None]:
    """Server fixture with tiny access-token TTL for reconnect/token-expiry checks."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m6_rs_rc_07_short_access.sqlite3",
        jwt_secret=JWT_SECRET,
        env_overrides={
            "XQWEB_ROOM_COUNT": str(ROOM_COUNT),
            "XQWEB_ACCESS_TOKEN_EXPIRE_SECONDS": "2",
            "XQWEB_ACCESS_TOKEN_REFRESH_INTERVAL_SECONDS": "1",
        },
    ) as server:
        yield server.base_url, server.ws_base_url


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _assert_error_payload(*, response: httpx.Response, expected_status: int) -> dict[str, object]:
    assert response.status_code == expected_status
    payload = response.json()
    assert {"code", "message", "detail"} <= set(payload)
    return payload


def _register_user(*, base_url: str, username: str) -> dict[str, Any]:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(
            "/api/auth/register",
            json={"username": username, "password": "123"},
        )
    assert response.status_code == 200
    payload = response.json()
    user_payload = payload["user"]
    return {
        "user_id": int(user_payload["id"]),
        "access_token": str(payload["access_token"]),
        "refresh_token": str(payload["refresh_token"]),
    }


def _refresh_access_token(*, base_url: str, refresh_token: str) -> dict[str, Any]:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
    assert response.status_code == 200
    return dict(response.json())


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
    users = [_register_user(base_url=base_url, username=f"{username_prefix}{idx}") for idx in range(3)]

    user_access_by_id = {int(user["user_id"]): str(user["access_token"]) for user in users}
    user_refresh_by_id = {int(user["user_id"]): str(user["refresh_token"]) for user in users}

    for user in users:
        _join_room(base_url=base_url, access_token=str(user["access_token"]), room_id=room_id)
    for user in users:
        _set_room_ready(base_url=base_url, access_token=str(user["access_token"]), room_id=room_id, ready=True)

    room_payload = _get_room_detail(base_url=base_url, access_token=str(users[0]["access_token"]), room_id=room_id)
    assert room_payload["status"] == "playing"
    game_id = room_payload["current_game_id"]
    assert isinstance(game_id, int)

    token_by_seat: dict[int, str] = {}
    refresh_by_seat: dict[int, str] = {}
    for member in room_payload["members"]:
        seat = int(member["seat"])
        user_id = int(member["user_id"])
        token_by_seat[seat] = user_access_by_id[user_id]
        refresh_by_seat[seat] = user_refresh_by_id[user_id]

    assert set(token_by_seat) == {0, 1, 2}
    return {
        "game_id": game_id,
        "token_by_seat": token_by_seat,
        "refresh_by_seat": refresh_by_seat,
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


def _build_action_payload_from_state(*, state_payload: dict[str, Any]) -> dict[str, Any]:
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
        "client_version": int(public_state["version"]),
    }

    if action.get("type") == "COVER":
        private_state = state_payload.get("private_state")
        assert isinstance(private_state, dict)
        hand = private_state.get("hand")
        assert isinstance(hand, dict)
        required_count = int(action["required_count"])
        payload["cover_list"] = _pick_cover_from_hand(hand=hand, required_count=required_count)
    return payload


def _apply_one_legal_action(*, base_url: str, game_id: int, token_by_seat: dict[int, str], observer_seat: int = 0) -> None:
    observer_token = token_by_seat[observer_seat]
    probe_state = _get_game_state(base_url=base_url, access_token=observer_token, game_id=game_id)
    current_seat = int(probe_state["public_state"]["turn"]["current_seat"])
    actor_token = token_by_seat[current_seat]
    actor_state = _get_game_state(base_url=base_url, access_token=actor_token, game_id=game_id)
    action_payload = _build_action_payload_from_state(state_payload=actor_state)
    _post_game_action(base_url=base_url, access_token=actor_token, game_id=game_id, payload=action_payload)


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
            return dict(settlement_payload)

        conflict_payload = _assert_error_payload(response=settlement_response, expected_status=409)
        assert conflict_payload["code"] == "GAME_STATE_CONFLICT"
        _apply_one_legal_action(base_url=base_url, game_id=game_id, token_by_seat=token_by_seat)

    pytest.fail(f"game_id={game_id} did not enter settlement within {max_steps} actions")


def _assert_legal_actions_hidden(payload: dict[str, Any]) -> None:
    assert ("legal_actions" not in payload) or (payload["legal_actions"] is None)


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


async def _recv_room_snapshot_with_game(*, ws: Any, game_id: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    room_event = await _recv_until(
        ws,
        event_type="ROOM_UPDATE",
        predicate=lambda event: event["payload"]["room"].get("current_game_id") == game_id,
    )
    public_event = await _recv_until(
        ws,
        event_type="GAME_PUBLIC_STATE",
        predicate=lambda event: event["payload"].get("game_id") == game_id,
    )
    private_event = await _recv_until(
        ws,
        event_type="GAME_PRIVATE_STATE",
        predicate=lambda event: event["payload"].get("game_id") == game_id,
    )
    return room_event, public_event, private_event


def _ensure_seat_not_current(
    *,
    base_url: str,
    game_id: int,
    token_by_seat: dict[int, str],
    seat: int,
) -> dict[str, Any]:
    state = _get_game_state(base_url=base_url, access_token=token_by_seat[seat], game_id=game_id)
    if int(state["public_state"]["turn"]["current_seat"]) == seat:
        _apply_one_legal_action(base_url=base_url, game_id=game_id, token_by_seat=token_by_seat)
        state = _get_game_state(base_url=base_url, access_token=token_by_seat[seat], game_id=game_id)
    assert int(state["public_state"]["turn"]["current_seat"]) != seat
    return state


def test_m6_rs_rc_01_http_state_recover_after_disconnect(live_server: tuple[str, str]) -> None:
    """M6-RS-RC-01: disconnected player recovers latest HTTP snapshot after others act."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rsrc01")
    game_id = context["game_id"]
    token0 = context["token_by_seat"][0]

    before_state = _ensure_seat_not_current(
        base_url=base_url,
        game_id=game_id,
        token_by_seat=context["token_by_seat"],
        seat=0,
    )
    version_before = int(before_state["public_state"]["version"])

    async def _disconnect_once() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={token0}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            await _recv_until(ws, event_type="ROOM_UPDATE")

    asyncio.run(_disconnect_once())

    _apply_one_legal_action(base_url=base_url, game_id=game_id, token_by_seat=context["token_by_seat"])
    recovered_state = _get_game_state(base_url=base_url, access_token=token0, game_id=game_id)

    assert int(recovered_state["public_state"]["version"]) > version_before
    assert recovered_state["self_seat"] == 0
    _assert_legal_actions_hidden(recovered_state)


def test_m6_rs_rc_02_room_ws_snapshot_after_reconnect(live_server: tuple[str, str]) -> None:
    """M6-RS-RC-02: reconnect receives ordered room/public/private snapshot with non-decreasing version."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rsrc02")
    game_id = context["game_id"]
    token0 = context["token_by_seat"][0]

    async def _run() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={token0}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            _, public_event, _ = await _recv_room_snapshot_with_game(ws=ws, game_id=game_id)
            first_version = int(public_event["payload"]["public_state"]["version"])

        await asyncio.to_thread(
            _apply_one_legal_action,
            base_url=base_url,
            game_id=game_id,
            token_by_seat=context["token_by_seat"],
        )

        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={token0}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            _, public_event_2, private_event_2 = await _recv_room_snapshot_with_game(ws=ws, game_id=game_id)
            version_after = int(public_event_2["payload"]["public_state"]["version"])
            assert version_after >= first_version
            if int(public_event_2["payload"]["public_state"]["turn"]["current_seat"]) != 0:
                _assert_legal_actions_hidden(private_event_2["payload"])

    asyncio.run(_run())


def test_m6_rs_rc_03_multi_step_catchup_consistency(live_server: tuple[str, str]) -> None:
    """M6-RS-RC-03: after missing multiple steps, reconnecting player catches up to same public snapshot."""
    base_url, _ = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rsrc03")
    game_id = context["game_id"]

    for _ in range(2):
        _apply_one_legal_action(base_url=base_url, game_id=game_id, token_by_seat=context["token_by_seat"])

    online_state = _get_game_state(base_url=base_url, access_token=context["token_by_seat"][1], game_id=game_id)
    recovered_state = _get_game_state(base_url=base_url, access_token=context["token_by_seat"][0], game_id=game_id)

    assert recovered_state["public_state"]["phase"] == online_state["public_state"]["phase"]
    assert recovered_state["public_state"]["turn"] == online_state["public_state"]["turn"]
    assert int(recovered_state["public_state"]["version"]) == int(online_state["public_state"]["version"])
    if int(recovered_state["public_state"]["turn"]["current_seat"]) != 0:
        _assert_legal_actions_hidden(recovered_state)


def test_m6_rs_rc_04_buckle_flow_recover_legal_actions(live_server: tuple[str, str]) -> None:
    """M6-RS-RC-04: reconnect in buckle_flow should recover BUCKLE/PASS or REVEAL/PASS choices."""
    base_url, _ = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rsrc04")
    game_id = context["game_id"]
    token0 = context["token_by_seat"][0]

    recovered_state = _get_game_state(base_url=base_url, access_token=token0, game_id=game_id)
    assert recovered_state["public_state"]["phase"] == "buckle_flow"

    current_seat = int(recovered_state["public_state"]["turn"]["current_seat"])
    if current_seat == 0:
        legal_actions = recovered_state["legal_actions"]
        assert isinstance(legal_actions, dict)
        action_types = {action["type"] for action in legal_actions["actions"]}
        assert action_types in ({"BUCKLE", "PASS_BUCKLE"}, {"REVEAL", "PASS_REVEAL"})
    else:
        _assert_legal_actions_hidden(recovered_state)


def test_m6_rs_rc_05_in_round_recover_action_index_stable(live_server: tuple[str, str]) -> None:
    """M6-RS-RC-05: reconnect in in_round keeps stable action order; non-current seat has no legal actions."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rsrc05")
    game_id = context["game_id"]

    probe = _get_game_state(base_url=base_url, access_token=context["token_by_seat"][0], game_id=game_id)
    current_seat = int(probe["public_state"]["turn"]["current_seat"])
    actor_token = context["token_by_seat"][current_seat]

    async def _run() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={actor_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            _, _, private_event = await _recv_room_snapshot_with_game(ws=ws, game_id=game_id)
            legal_actions_1 = private_event["payload"].get("legal_actions")

        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={actor_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            _, _, private_event_2 = await _recv_room_snapshot_with_game(ws=ws, game_id=game_id)
            legal_actions_2 = private_event_2["payload"].get("legal_actions")

        assert legal_actions_1 == legal_actions_2

    asyncio.run(_run())

    non_actor_seat = (current_seat + 1) % 3
    non_actor_state = _get_game_state(base_url=base_url, access_token=context["token_by_seat"][non_actor_seat], game_id=game_id)
    _assert_legal_actions_hidden(non_actor_state)


def test_m6_rs_rc_06_settlement_recover_and_query(live_server: tuple[str, str]) -> None:
    """M6-RS-RC-06: reconnect in settlement recovers phase and /settlement stays consistent."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rsrc06")
    game_id = context["game_id"]
    token0 = context["token_by_seat"][0]

    _advance_game_until_settlement(base_url=base_url, game_id=game_id, token_by_seat=context["token_by_seat"])

    async def _run() -> int:
        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={token0}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            _, public_event, private_event = await _recv_room_snapshot_with_game(ws=ws, game_id=game_id)
            assert public_event["payload"]["public_state"]["phase"] == "settlement"
            _assert_legal_actions_hidden(private_event["payload"])
            return int(public_event["payload"]["public_state"]["version"])

    reconnect_version = asyncio.run(_run())

    settlement_response = _get_game_settlement_response(base_url=base_url, access_token=token0, game_id=game_id)
    assert settlement_response.status_code == 200
    settlement_payload = settlement_response.json()
    assert settlement_payload["final_state"]["phase"] == "settlement"
    assert int(settlement_payload["final_state"]["version"]) == reconnect_version


def test_m6_rs_rc_07_expired_token_refresh_then_reconnect(live_server_short_access: tuple[str, str]) -> None:
    """M6-RS-RC-07: ws closes with 4401 after token expiry, then refresh token can reconnect."""
    base_url, ws_base_url = live_server_short_access
    user = _register_user(base_url=base_url, username="m6rsrc07")
    access_token = str(user["access_token"])
    refresh_token = str(user["refresh_token"])
    _join_room(base_url=base_url, access_token=access_token, room_id=0)

    async def _connect_wait_expire_close() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={access_token}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            await _recv_until(ws, event_type="ROOM_UPDATE")
            await asyncio.sleep(3.0)
            await asyncio.wait_for(ws.wait_closed(), timeout=4.0)
            assert ws.close_code == 4401
            assert ws.close_reason == "UNAUTHORIZED"

    asyncio.run(_connect_wait_expire_close())

    refreshed = _refresh_access_token(base_url=base_url, refresh_token=refresh_token)
    new_access = str(refreshed["access_token"])

    async def _reconnect() -> None:
        async with websockets.connect(
            f"{ws_base_url}/ws/rooms/0?token={new_access}",
            open_timeout=3,
            close_timeout=3,
            ping_interval=None,
            proxy=None,
        ) as ws:
            await _recv_until(ws, event_type="ROOM_UPDATE")

    asyncio.run(_reconnect())


def test_m6_rs_rc_08_restart_boundary_no_cross_restart_recover(tmp_path: Path) -> None:
    """M6-RS-RC-08: restart clears in-memory game state and old game_id cannot be recovered."""
    db_filename = "m6_rs_rc_08_restart.sqlite3"

    with run_live_server(
        tmp_path=tmp_path,
        db_filename=db_filename,
        jwt_secret=JWT_SECRET,
        env_overrides={"XQWEB_ROOM_COUNT": str(ROOM_COUNT)},
    ) as server:
        base_url = server.base_url
        user = _register_user(base_url=base_url, username="m6rsrc08")
        access_token = str(user["access_token"])

        setup = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rsrc08g")
        game_id = int(setup["game_id"])

        state_before = _get_game_state(base_url=base_url, access_token=setup["token_by_seat"][0], game_id=game_id)
        assert int(state_before["game_id"]) == game_id

    with run_live_server(
        tmp_path=tmp_path,
        db_filename=db_filename,
        jwt_secret=JWT_SECRET,
        env_overrides={"XQWEB_ROOM_COUNT": str(ROOM_COUNT)},
    ) as server_after:
        base_url_after = server_after.base_url

        with httpx.Client(base_url=base_url_after, timeout=3, trust_env=False) as client:
            state_response = client.get(
                f"/api/games/{game_id}/state",
                headers=_auth_headers(access_token),
            )
        assert state_response.status_code in {404, 409}

        room_payload = _get_room_detail(base_url=base_url_after, access_token=access_token, room_id=0)
        assert room_payload["status"] == "waiting"
        assert room_payload["current_game_id"] is None
