"""Red-phase concurrency consistency tests against a live M6 backend service (CC 01~05)."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
from typing import Any

import httpx
import pytest
import websockets

from tests.integration.real_service.live_server import run_live_server

JWT_SECRET = "m6-rs-cc-red-test-secret-key-32-bytes-minimum"
ROOM_COUNT = 3


@pytest.fixture
def live_server(tmp_path: Path) -> Generator[tuple[str, str], None, None]:
    """Start one real uvicorn backend per test case."""
    with run_live_server(
        tmp_path=tmp_path,
        db_filename="m6_rs_cc_01_05_red.sqlite3",
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


def _post_game_action_response(
    *,
    base_url: str,
    access_token: str,
    game_id: int,
    payload: dict[str, Any],
) -> tuple[int, str | None]:
    with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
        response = client.post(
            f"/api/games/{game_id}/actions",
            headers=_auth_headers(access_token),
            json=payload,
        )
    if response.status_code == 204:
        return 204, None
    error_payload = _assert_error_payload(response=response, expected_status=409)
    return 409, str(error_payload["code"])


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
    return {"room_id": room_id, "game_id": game_id, "token_by_seat": token_by_seat}


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


def _apply_one_legal_action(*, base_url: str, game_id: int, token_by_seat: dict[int, str], observer_seat: int = 0) -> None:
    observer_token = token_by_seat[observer_seat]
    probe_state = _get_game_state(base_url=base_url, access_token=observer_token, game_id=game_id)
    current_seat = int(probe_state["public_state"]["turn"]["current_seat"])
    actor_token = token_by_seat[current_seat]
    actor_state = _get_game_state(base_url=base_url, access_token=actor_token, game_id=game_id)
    action_payload = _build_action_payload_from_state(state_payload=actor_state)
    status_code, error_code = _post_game_action_response(
        base_url=base_url,
        access_token=actor_token,
        game_id=game_id,
        payload=action_payload,
    )
    assert (status_code, error_code) == (204, None)


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


def _run_concurrent_action_requests(
    *,
    base_url: str,
    game_id: int,
    access_token: str,
    action_payload: dict[str, Any],
    worker_count: int = 2,
) -> list[tuple[int, str | None]]:
    barrier = threading.Barrier(worker_count)

    def _worker() -> tuple[int, str | None]:
        barrier.wait()
        return _post_game_action_response(
            base_url=base_url,
            access_token=access_token,
            game_id=game_id,
            payload=action_payload,
        )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        return list(executor.map(lambda _: _worker(), range(worker_count)))


def _run_concurrent_ready_requests(
    *,
    base_url: str,
    room_id: int,
    access_tokens: list[str],
) -> list[tuple[int, int | None, str | None]]:
    barrier = threading.Barrier(len(access_tokens))

    def _worker(access_token: str) -> tuple[int, int | None, str | None]:
        barrier.wait()
        with httpx.Client(base_url=base_url, timeout=3, trust_env=False) as client:
            response = client.post(
                f"/api/rooms/{room_id}/ready",
                headers=_auth_headers(access_token),
                json={"ready": True},
            )
        if response.status_code == 200:
            payload = response.json()
            game_id = payload.get("current_game_id")
            game_id_value = int(game_id) if isinstance(game_id, int) else None
            return 200, game_id_value, None
        error_payload = _assert_error_payload(response=response, expected_status=409)
        return 409, None, str(error_payload["code"])

    with ThreadPoolExecutor(max_workers=len(access_tokens)) as executor:
        return list(executor.map(_worker, access_tokens))


def _collect_public_snapshot_by_seat(
    *,
    base_url: str,
    game_id: int,
    token_by_seat: dict[int, str],
) -> dict[int, dict[str, Any]]:
    snapshot_by_seat: dict[int, dict[str, Any]] = {}
    for seat, token in token_by_seat.items():
        state = _get_game_state(base_url=base_url, access_token=token, game_id=game_id)
        snapshot_by_seat[seat] = {
            "version": int(state["public_state"]["version"]),
            "phase": str(state["public_state"]["phase"]),
        }
    return snapshot_by_seat


async def _connect_room_ws(*, ws_base_url: str, room_id: int, token: str) -> Any:
    return await websockets.connect(
        f"{ws_base_url}/ws/rooms/{room_id}?token={token}",
        open_timeout=3,
        close_timeout=3,
        ping_interval=None,
        proxy=None,
    )


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


async def _recv_optional_public_state(
    ws: Any,
    *,
    game_id: int,
    timeout_seconds: float = 1.0,
) -> dict[str, Any] | None:
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
        if event.get("type") != "GAME_PUBLIC_STATE":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        if int(payload.get("game_id", -1)) != game_id:
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
        predicate=lambda event: int(event["payload"].get("game_id", -1)) == game_id,
    )
    private_event = await _recv_until(
        ws,
        event_type="GAME_PRIVATE_STATE",
        predicate=lambda event: int(event["payload"].get("game_id", -1)) == game_id,
    )
    return room_event, public_event, private_event


def test_m6_rs_cc_01_concurrent_actions_single_winner_consistent_stream(live_server: tuple[str, str]) -> None:
    """M6-RS-CC-01: concurrent same-version actions keep a single winner and same final version on all clients."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rscc01")
    game_id = context["game_id"]

    probe_state = _get_game_state(base_url=base_url, access_token=context["token_by_seat"][0], game_id=game_id)
    before_version = int(probe_state["public_state"]["version"])
    current_seat = int(probe_state["public_state"]["turn"]["current_seat"])
    actor_token = context["token_by_seat"][current_seat]
    actor_state = _get_game_state(base_url=base_url, access_token=actor_token, game_id=game_id)
    action_payload = _build_action_payload_from_state(state_payload=actor_state)

    async def _run() -> tuple[list[tuple[int, str | None]], dict[int, int]]:
        ws_by_seat: dict[int, Any] = {}
        try:
            for seat in sorted(context["token_by_seat"]):
                ws = await _connect_room_ws(ws_base_url=ws_base_url, room_id=0, token=context["token_by_seat"][seat])
                ws_by_seat[seat] = ws
                await _recv_room_snapshot_with_game(ws=ws, game_id=game_id)

            race_results = await asyncio.to_thread(
                _run_concurrent_action_requests,
                base_url=base_url,
                game_id=game_id,
                access_token=actor_token,
                action_payload=action_payload,
            )

            target_version = before_version + 1
            converged_versions: dict[int, int] = {}
            for seat, ws in ws_by_seat.items():
                public_event = await _recv_until(
                    ws,
                    event_type="GAME_PUBLIC_STATE",
                    predicate=lambda event: int(event["payload"].get("game_id", -1)) == game_id
                    and int(event["payload"]["public_state"]["version"]) >= target_version,
                )
                converged_versions[seat] = int(public_event["payload"]["public_state"]["version"])
            return race_results, converged_versions
        finally:
            for ws in ws_by_seat.values():
                await ws.close()

    race_results, converged_versions = asyncio.run(_run())

    statuses = [status for status, _ in race_results]
    assert statuses.count(204) == 1
    assert statuses.count(409) == 1
    loser_codes = {code for status, code in race_results if status == 409}
    assert loser_codes <= {"GAME_VERSION_CONFLICT", "GAME_INVALID_ACTION"}

    assert set(converged_versions.values()) == {before_version + 1}
    final_state = _get_game_state(base_url=base_url, access_token=context["token_by_seat"][0], game_id=game_id)
    assert int(final_state["public_state"]["version"]) == before_version + 1


def test_m6_rs_cc_02_reconnect_action_race_no_duplicate_apply(live_server: tuple[str, str]) -> None:
    """M6-RS-CC-02: reconnect race with one action should not duplicate apply or roll back version."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rscc02")
    game_id = context["game_id"]

    probe_state = _get_game_state(base_url=base_url, access_token=context["token_by_seat"][0], game_id=game_id)
    before_version = int(probe_state["public_state"]["version"])
    current_seat = int(probe_state["public_state"]["turn"]["current_seat"])
    actor_token = context["token_by_seat"][current_seat]
    reconnect_seat = (current_seat + 1) % 3
    reconnect_token = context["token_by_seat"][reconnect_seat]
    actor_state = _get_game_state(base_url=base_url, access_token=actor_token, game_id=game_id)
    action_payload = _build_action_payload_from_state(state_payload=actor_state)

    async def _run() -> tuple[tuple[int, str | None], list[int]]:
        seen_versions: list[int] = []

        async def _reconnect_worker() -> None:
            ws = await _connect_room_ws(ws_base_url=ws_base_url, room_id=0, token=reconnect_token)
            try:
                _, public_event, _ = await _recv_room_snapshot_with_game(ws=ws, game_id=game_id)
                seen_versions.append(int(public_event["payload"]["public_state"]["version"]))
                next_public_event = await _recv_optional_public_state(ws, game_id=game_id, timeout_seconds=1.2)
                if next_public_event is not None:
                    seen_versions.append(int(next_public_event["payload"]["public_state"]["version"]))
            finally:
                await ws.close()

        reconnect_task = asyncio.create_task(_reconnect_worker())
        action_result = await asyncio.to_thread(
            _post_game_action_response,
            base_url=base_url,
            access_token=actor_token,
            game_id=game_id,
            payload=action_payload,
        )
        await reconnect_task
        return action_result, seen_versions

    action_result, seen_versions = asyncio.run(_run())
    assert action_result == (204, None)

    final_state = _get_game_state(base_url=base_url, access_token=reconnect_token, game_id=game_id)
    final_version = int(final_state["public_state"]["version"])
    assert final_version == before_version + 1

    assert seen_versions
    assert min(seen_versions) >= before_version
    assert seen_versions == sorted(seen_versions)
    assert max(seen_versions) == final_version


def test_m6_rs_cc_03_multi_socket_same_user_private_consistent(live_server: tuple[str, str]) -> None:
    """M6-RS-CC-03: multiple sockets of the same account should receive consistent own private snapshots."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rscc03")
    game_id = context["game_id"]

    self_seat = 0
    self_token = context["token_by_seat"][self_seat]
    probe_state = _get_game_state(base_url=base_url, access_token=self_token, game_id=game_id)
    before_version = int(probe_state["public_state"]["version"])

    async def _run() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        ws_a = await _connect_room_ws(ws_base_url=ws_base_url, room_id=0, token=self_token)
        ws_b = await _connect_room_ws(ws_base_url=ws_base_url, room_id=0, token=self_token)

        try:
            _, public_a_0, private_a_0 = await _recv_room_snapshot_with_game(ws=ws_a, game_id=game_id)
            _, public_b_0, private_b_0 = await _recv_room_snapshot_with_game(ws=ws_b, game_id=game_id)

            await asyncio.to_thread(
                _apply_one_legal_action,
                base_url=base_url,
                game_id=game_id,
                token_by_seat=context["token_by_seat"],
            )

            target_version = before_version + 1
            await _recv_until(
                ws_a,
                event_type="GAME_PUBLIC_STATE",
                predicate=lambda event: int(event["payload"].get("game_id", -1)) == game_id
                and int(event["payload"]["public_state"]["version"]) >= target_version,
            )
            await _recv_until(
                ws_b,
                event_type="GAME_PUBLIC_STATE",
                predicate=lambda event: int(event["payload"].get("game_id", -1)) == game_id
                and int(event["payload"]["public_state"]["version"]) >= target_version,
            )
            private_a_1 = await _recv_until(
                ws_a,
                event_type="GAME_PRIVATE_STATE",
                predicate=lambda event: int(event["payload"].get("game_id", -1)) == game_id,
            )
            private_b_1 = await _recv_until(
                ws_b,
                event_type="GAME_PRIVATE_STATE",
                predicate=lambda event: int(event["payload"].get("game_id", -1)) == game_id,
            )
            return private_a_0, private_b_0, private_a_1, private_b_1
        finally:
            await ws_a.close()
            await ws_b.close()

    private_a_0, private_b_0, private_a_1, private_b_1 = asyncio.run(_run())

    assert int(private_a_0["payload"]["self_seat"]) == self_seat
    assert int(private_b_0["payload"]["self_seat"]) == self_seat
    assert private_a_0["payload"]["private_state"] == private_b_0["payload"]["private_state"]

    assert int(private_a_1["payload"]["self_seat"]) == self_seat
    assert int(private_b_1["payload"]["self_seat"]) == self_seat
    assert private_a_1["payload"]["private_state"] == private_b_1["payload"]["private_state"]
    assert private_a_1["payload"].get("legal_actions") == private_b_1["payload"].get("legal_actions")


def test_m6_rs_cc_04_concurrent_ready_with_reconnect_single_new_game(live_server: tuple[str, str]) -> None:
    """M6-RS-CC-04: concurrent ready in settlement starts only one game and reconnect gets that new snapshot."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rscc04")
    room_id = int(context["room_id"])
    old_game_id = int(context["game_id"])

    _advance_game_until_settlement(base_url=base_url, game_id=old_game_id, token_by_seat=context["token_by_seat"])

    room_before = _get_room_detail(base_url=base_url, access_token=context["token_by_seat"][0], room_id=room_id)
    assert room_before["status"] == "settlement"
    assert room_before["current_game_id"] == old_game_id

    reconnect_token = context["token_by_seat"][2]
    ready_tokens = [context["token_by_seat"][seat] for seat in sorted(context["token_by_seat"])]

    async def _run() -> tuple[list[tuple[int, int | None, str | None]], int]:
        async def _reconnect_worker() -> int:
            ws = await _connect_room_ws(ws_base_url=ws_base_url, room_id=room_id, token=reconnect_token)
            try:
                room_event = await _recv_until(
                    ws,
                    event_type="ROOM_UPDATE",
                    timeout_seconds=8.0,
                    predicate=lambda event: isinstance(event["payload"]["room"].get("current_game_id"), int)
                    and int(event["payload"]["room"]["current_game_id"]) != old_game_id
                    and event["payload"]["room"].get("status") == "playing",
                )
                new_game_id = int(room_event["payload"]["room"]["current_game_id"])
                await _recv_until(
                    ws,
                    event_type="GAME_PUBLIC_STATE",
                    predicate=lambda event: int(event["payload"].get("game_id", -1)) == new_game_id,
                )
                await _recv_until(
                    ws,
                    event_type="GAME_PRIVATE_STATE",
                    predicate=lambda event: int(event["payload"].get("game_id", -1)) == new_game_id,
                )
                return new_game_id
            finally:
                await ws.close()

        reconnect_task = asyncio.create_task(_reconnect_worker())
        ready_results = await asyncio.to_thread(
            _run_concurrent_ready_requests,
            base_url=base_url,
            room_id=room_id,
            access_tokens=ready_tokens,
        )
        reconnect_game_id = await reconnect_task
        return ready_results, reconnect_game_id

    ready_results, reconnect_game_id = asyncio.run(_run())

    statuses = [status for status, _, _ in ready_results]
    assert statuses == [200, 200, 200]

    new_game_ids = {
        game_id
        for _, game_id, _ in ready_results
        if game_id is not None and game_id != old_game_id
    }
    assert len(new_game_ids) == 1
    assert reconnect_game_id in new_game_ids

    final_room = _get_room_detail(base_url=base_url, access_token=context["token_by_seat"][0], room_id=room_id)
    assert final_room["status"] == "playing"
    assert int(final_room["current_game_id"]) == reconnect_game_id


def test_m6_rs_cc_05_long_session_eventual_consistency(live_server: tuple[str, str]) -> None:
    """M6-RS-CC-05: long session with mid-game reconnect eventually converges on same phase/version."""
    base_url, ws_base_url = live_server
    context = _setup_three_players_and_start_game(base_url=base_url, username_prefix="m6rscc05")
    game_id = context["game_id"]

    async def _run() -> dict[int, dict[str, Any]]:
        ws_by_seat: dict[int, Any] = {}
        latest_version_by_seat: dict[int, int] = {}

        try:
            for seat in sorted(context["token_by_seat"]):
                ws = await _connect_room_ws(ws_base_url=ws_base_url, room_id=0, token=context["token_by_seat"][seat])
                ws_by_seat[seat] = ws
                _, public_event, _ = await _recv_room_snapshot_with_game(ws=ws, game_id=game_id)
                latest_version_by_seat[seat] = int(public_event["payload"]["public_state"]["version"])

            for step in range(6):
                if step == 2:
                    await ws_by_seat[2].close()
                    ws_by_seat.pop(2)
                await asyncio.to_thread(
                    _apply_one_legal_action,
                    base_url=base_url,
                    game_id=game_id,
                    token_by_seat=context["token_by_seat"],
                )
                if step == 3:
                    ws_reconnect = await _connect_room_ws(
                        ws_base_url=ws_base_url,
                        room_id=0,
                        token=context["token_by_seat"][2],
                    )
                    ws_by_seat[2] = ws_reconnect
                    _, public_event, _ = await _recv_room_snapshot_with_game(ws=ws_reconnect, game_id=game_id)
                    latest_version_by_seat[2] = int(public_event["payload"]["public_state"]["version"])

            snapshot_by_seat = await asyncio.to_thread(
                _collect_public_snapshot_by_seat,
                base_url=base_url,
                game_id=game_id,
                token_by_seat=context["token_by_seat"],
            )
            final_version = int(next(iter(snapshot_by_seat.values()))["version"])

            for seat, ws in ws_by_seat.items():
                if latest_version_by_seat.get(seat, 0) >= final_version:
                    continue
                public_event = await _recv_until(
                    ws,
                    event_type="GAME_PUBLIC_STATE",
                    timeout_seconds=8.0,
                    predicate=lambda event: int(event["payload"].get("game_id", -1)) == game_id
                    and int(event["payload"]["public_state"]["version"]) >= final_version,
                )
                latest_version_by_seat[seat] = int(public_event["payload"]["public_state"]["version"])

            return snapshot_by_seat
        finally:
            for ws in ws_by_seat.values():
                await ws.close()

    snapshot_by_seat = asyncio.run(_run())

    versions = {seat: int(snapshot["version"]) for seat, snapshot in snapshot_by_seat.items()}
    phases = {seat: str(snapshot["phase"]) for seat, snapshot in snapshot_by_seat.items()}
    assert len(set(versions.values())) == 1
    assert len(set(phases.values())) == 1
