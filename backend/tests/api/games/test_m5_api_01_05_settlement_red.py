"""M5-BE-01~05 API contract tests for settlement and ready-reset (RED phase)."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException


def _bootstrap_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_name: str):
    db_path = tmp_path / db_name
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "m5-api-test-secret-key-32-bytes-minimum")
    monkeypatch.setenv("XQWEB_ROOM_COUNT", "3")

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    return app_main


def _register_and_get_access_token(app_main: Any, username: str) -> tuple[int, str]:
    payload = app_main.register(
        app_main.RegisterRequest(username=username, password="123"),
    )
    return int(payload["user"]["id"]), str(payload["access_token"])


def _auth_header(token: str) -> str:
    return f"Bearer {token}"


def _setup_three_players_and_start_game(app_main: Any, username_prefix: str) -> dict[str, Any]:
    users: list[tuple[int, str]] = []
    for idx in range(3):
        users.append(_register_and_get_access_token(app_main, username=f"{username_prefix}{idx}"))

    user_token_by_id = {user_id: token for user_id, token in users}

    for _, token in users:
        app_main.join_room(room_id=0, authorization=_auth_header(token))

    for _, token in users:
        app_main.set_room_ready(
            room_id=0,
            payload=app_main.ReadyRequest(ready=True),
            authorization=_auth_header(token),
        )

    room_payload = app_main.get_room_detail(room_id=0, authorization=_auth_header(users[0][1]))
    assert room_payload["status"] == "playing"

    game_id = int(room_payload["current_game_id"])
    token_by_seat: dict[int, str] = {}
    for member in room_payload["members"]:
        token_by_seat[int(member["seat"])] = user_token_by_id[int(member["user_id"])]
    assert set(token_by_seat.keys()) == {0, 1, 2}

    return {"game_id": game_id, "token_by_seat": token_by_seat}


def test_m5_be_01_get_settlement_success_returns_settlement_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M5-BE-01: /settlement should return settlement output when phase is settlement."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m5_api_01.sqlite3")
    context = _setup_three_players_and_start_game(app_main, username_prefix="m5a01")

    game = app_main.room_registry.get_game(context["game_id"])
    app_main.room_registry.mark_game_settlement(context["game_id"])

    payload = app_main.get_game_settlement(
        game_id=context["game_id"],
        authorization=_auth_header(context["token_by_seat"][0]),
    )

    assert {"chip_delta_by_seat", "final_state"} <= set(payload)
    assert payload["final_state"]["phase"] == "settlement"
    assert int(payload["final_state"]["version"]) == int(game.version)


def test_m5_be_02_settlement_phase_gate_depends_on_phase_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M5-BE-02: when public_state.phase is not settlement, /settlement must return 409."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m5_api_02.sqlite3")
    context = _setup_three_players_and_start_game(app_main, username_prefix="m5a02")

    game = app_main.room_registry.get_game(context["game_id"])
    game.status = "settlement"
    game.phase = "in_round"

    with pytest.raises(HTTPException) as exc_info:
        app_main.get_game_settlement(
            game_id=context["game_id"],
            authorization=_auth_header(context["token_by_seat"][0]),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "GAME_STATE_CONFLICT"


def test_m5_be_03_settlement_rejects_non_room_member(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M5-BE-03: non-member access to /settlement returns 403."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m5_api_03.sqlite3")
    context = _setup_three_players_and_start_game(app_main, username_prefix="m5a03")

    app_main.room_registry.mark_game_settlement(context["game_id"])
    outsider_id, outsider_token = _register_and_get_access_token(app_main, username="m5a03x")

    with pytest.raises(HTTPException) as exc_info:
        app_main.get_game_settlement(
            game_id=context["game_id"],
            authorization=_auth_header(outsider_token),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == {
        "code": "GAME_FORBIDDEN",
        "message": "user is not a game member",
        "detail": {"game_id": context["game_id"], "user_id": outsider_id},
    }


def test_m5_be_04_settlement_game_not_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M5-BE-04: unknown game id returns 404 + GAME_NOT_FOUND."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m5_api_04.sqlite3")
    _, access_token = _register_and_get_access_token(app_main, username="m5a04u")

    with pytest.raises(HTTPException) as exc_info:
        app_main.get_game_settlement(
            game_id=999999,
            authorization=_auth_header(access_token),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {
        "code": "GAME_NOT_FOUND",
        "message": "game not found",
        "detail": {"game_id": 999999},
    }


def test_m5_be_05_ready_flags_reset_when_room_enters_settlement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M5-BE-05: entering settlement resets all room members ready flags to false."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m5_api_05.sqlite3")
    context = _setup_three_players_and_start_game(app_main, username_prefix="m5a05")

    app_main.room_registry.mark_game_settlement(context["game_id"])
    room_payload = app_main.get_room_detail(
        room_id=0,
        authorization=_auth_header(context["token_by_seat"][0]),
    )

    assert room_payload["status"] == "settlement"
    assert room_payload["current_game_id"] == context["game_id"]
    assert all(member["ready"] is False for member in room_payload["members"])
