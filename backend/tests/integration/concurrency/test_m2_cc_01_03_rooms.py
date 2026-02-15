"""M2-CC-01~03 room concurrency contract tests (RED phase)."""

from __future__ import annotations

import importlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import HTTPException


def _setup_app(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_name: str,
):
    db_path = tmp_path / db_name
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "m2-cc-test-secret-key-32-bytes-minimum")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    return app_main


def _register_user(app_main, username: str) -> tuple[int, str]:
    payload = app_main.register(app_main.RegisterRequest(username=username, password="123"))
    return int(payload["user"]["id"]), str(payload["access_token"])


def test_m2_cc_01_concurrent_join_does_not_overfill_or_duplicate_seats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: concurrent join keeps player_count<=3 and seat assignments unique."""
    app_main = _setup_app(tmp_path=tmp_path, monkeypatch=monkeypatch, db_name="m2_cc_01.sqlite3")
    users = [_register_user(app_main, username=f"c1u{idx}") for idx in range(6)]
    tokens = [token for _, token in users]

    def _slow_pick_min_available_seat(room):
        used = {member.seat for member in room.members}
        # Expand race window so concurrent callers read the same seat set.
        time.sleep(0.02)
        for seat in range(app_main.MAX_ROOM_MEMBERS):
            if seat not in used:
                return seat
        raise app_main.RoomFullError(f"room_id={room.room_id} is full")

    monkeypatch.setattr(
        app_main.RoomRegistry,
        "_pick_min_available_seat",
        staticmethod(_slow_pick_min_available_seat),
    )

    start_barrier = threading.Barrier(len(tokens))

    def _join_worker(token: str) -> str:
        start_barrier.wait()
        try:
            app_main.join_room(room_id=0, authorization=f"Bearer {token}")
            return "ok"
        except HTTPException as exc:
            return str(exc.status_code)

    with ThreadPoolExecutor(max_workers=len(tokens)) as executor:
        list(executor.map(_join_worker, tokens))

    room = app_main.room_registry.get_room(0)
    seats = [member.seat for member in room.members]
    assert len(room.members) <= app_main.MAX_ROOM_MEMBERS
    assert len(seats) == len(set(seats))


def test_m2_cc_02_concurrent_ready_updates_are_serialized_per_room(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: concurrent ready updates should not overlap on same room."""
    app_main = _setup_app(tmp_path=tmp_path, monkeypatch=monkeypatch, db_name="m2_cc_02.sqlite3")
    users = [_register_user(app_main, username=f"c2u{idx}") for idx in range(3)]

    for _, token in users:
        app_main.join_room(room_id=0, authorization=f"Bearer {token}")

    active = 0
    max_active = 0
    active_lock = threading.Lock()
    original_set_ready = app_main.room_registry.set_ready

    def _instrumented_set_ready(room_id: int, user_id: int, ready: bool):
        nonlocal active, max_active
        with active_lock:
            active += 1
            max_active = max(max_active, active)
        try:
            time.sleep(0.02)
            return original_set_ready(room_id=room_id, user_id=user_id, ready=ready)
        finally:
            with active_lock:
                active -= 1

    monkeypatch.setattr(app_main.room_registry, "set_ready", _instrumented_set_ready)

    start_barrier = threading.Barrier(len(users))

    def _ready_worker(token: str) -> str:
        start_barrier.wait()
        app_main.set_room_ready(
            room_id=0,
            payload=app_main.ReadyRequest(ready=True),
            authorization=f"Bearer {token}",
        )
        return "ok"

    with ThreadPoolExecutor(max_workers=len(users)) as executor:
        list(executor.map(lambda item: _ready_worker(item[1]), users))

    room = app_main.room_registry.get_room(0)
    ready_count = sum(1 for member in room.members if member.ready)
    assert ready_count == 3
    assert max_active == 1


def test_m2_cc_03_cross_room_swap_completes_without_deadlock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: concurrent cross-room swap should complete without deadlock."""
    app_main = _setup_app(tmp_path=tmp_path, monkeypatch=monkeypatch, db_name="m2_cc_03.sqlite3")
    user_a_id, token_a = _register_user(app_main, username="c3ua")
    user_b_id, token_b = _register_user(app_main, username="c3ub")

    app_main.join_room(room_id=0, authorization=f"Bearer {token_a}")
    app_main.join_room(room_id=1, authorization=f"Bearer {token_b}")

    room_locks = {0: threading.Lock(), 1: threading.Lock()}
    original_join = app_main.room_registry.join

    def _join_with_unordered_dual_locks(room_id: int, user_id: int, username: str):
        source_room_id = app_main.room_registry.find_room_id_by_user(user_id)
        if source_room_id is None or source_room_id == room_id:
            return original_join(room_id=room_id, user_id=user_id, username=username)

        first_lock = room_locks[source_room_id]
        second_lock = room_locks[room_id]
        if not first_lock.acquire(timeout=0.3):
            raise TimeoutError("failed to acquire source room lock")
        try:
            time.sleep(0.05)
            if not second_lock.acquire(timeout=0.3):
                raise TimeoutError("potential deadlock while acquiring target room lock")
            try:
                return original_join(room_id=room_id, user_id=user_id, username=username)
            finally:
                second_lock.release()
        finally:
            first_lock.release()

    monkeypatch.setattr(app_main.room_registry, "join", _join_with_unordered_dual_locks)

    start_barrier = threading.Barrier(2)

    def _swap_worker(token: str, target_room_id: int) -> str:
        start_barrier.wait()
        try:
            app_main.join_room(room_id=target_room_id, authorization=f"Bearer {token}")
            return "ok"
        except Exception as exc:  # noqa: BLE001
            return type(exc).__name__

    with ThreadPoolExecutor(max_workers=2) as executor:
        result_a, result_b = executor.map(
            lambda item: _swap_worker(*item),
            ((token_a, 1), (token_b, 0)),
        )

    assert result_a == "ok"
    assert result_b == "ok"
    assert app_main.room_registry.find_room_id_by_user(user_a_id) == 1
    assert app_main.room_registry.find_room_id_by_user(user_b_id) == 0
