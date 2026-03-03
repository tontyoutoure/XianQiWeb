"""Red-phase API tests for M8 seed injection semantics (API-01~05)."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.rooms.models import SeedInjectionRequest


def _bootstrap_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_name: str,
    *,
    seed_injection_enabled: str = "true",
):
    db_path = tmp_path / db_name
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "m8-api-red-test-secret-key-32-bytes-minimum")
    monkeypatch.setenv("XQWEB_ROOM_COUNT", "3")
    monkeypatch.setenv("XQWEB_SEED_ENABLE_SEED_INJECTION", seed_injection_enabled)
    monkeypatch.delenv("XQWEB_SEED_CATALOG_DIR", raising=False)

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    return app_main


def _auth_header(token: str) -> str:
    return f"Bearer {token}"


def _register_and_get_access_token(app_main: Any, username: str) -> tuple[int, str]:
    payload = app_main.register(
        app_main.RegisterRequest(username=username, password="123"),
    )
    return int(payload["user"]["id"]), str(payload["access_token"])


def _prepare_three_members(app_main: Any, username_prefix: str, *, room_id: int = 0) -> dict[int, str]:
    users: list[tuple[int, str]] = []
    for idx in range(3):
        users.append(_register_and_get_access_token(app_main, username=f"{username_prefix}{idx}"))
    for _, token in users:
        app_main.join_room(room_id=room_id, authorization=_auth_header(token))
    return {user_id: token for user_id, token in users}


def _start_game(app_main: Any, user_token_by_id: dict[int, str], *, room_id: int = 0) -> int:
    for token in user_token_by_id.values():
        app_main.set_room_ready(
            room_id=room_id,
            payload=app_main.ReadyRequest(ready=True),
            authorization=_auth_header(token),
        )
    room_payload = app_main.get_room_detail(
        room_id=room_id,
        authorization=_auth_header(next(iter(user_token_by_id.values()))),
    )
    assert room_payload["status"] == "playing"
    return int(room_payload["current_game_id"])


def _reopen_next_game(app_main: Any, user_token_by_id: dict[int, str], current_game_id: int, *, room_id: int = 0) -> int:
    app_main.room_registry.mark_game_settlement(current_game_id)
    return _start_game(app_main, user_token_by_id, room_id=room_id)


def test_m8_api_01_valid_seed_injection_returns_200_and_updates_runtime_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M8-API-01: valid seed injection should return success payload and write runtime seed."""
    _bootstrap_app(tmp_path, monkeypatch, "m8_api_01.sqlite3", seed_injection_enabled="true")
    import app.runtime as runtime
    from app.api.routers import games as game_routes

    payload = game_routes.seed_injection(SeedInjectionRequest(seed=123456))

    assert payload == {"ok": True, "injected_seed": 123456, "apply_scope": "next_game_once"}
    assert runtime.next_game_seed == 123456


@pytest.mark.parametrize(
    "invalid_body",
    [
        {},
        {"seed": "abc"},
        {"seed": -1},
    ],
)
def test_m8_api_02_invalid_request_body_returns_400(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_body: dict[str, object],
) -> None:
    """M8-API-02: missing/type/negative seed should return 400 (contract)."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m8_api_02.sqlite3", seed_injection_enabled="true")

    with TestClient(app_main.app) as client:
        response = client.post("/api/games/seed-injection", json=invalid_body)

    assert response.status_code == 400


def test_m8_api_03_latter_injection_should_override_previous_seed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M8-API-03: repeated injection should use last-write seed for the next game."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m8_api_03.sqlite3", seed_injection_enabled="true")
    from app.api.routers import games as game_routes

    user_token_by_id = _prepare_three_members(app_main, "m8api03")

    game_routes.seed_injection(SeedInjectionRequest(seed=111))
    game_routes.seed_injection(SeedInjectionRequest(seed=222))
    game_id = _start_game(app_main, user_token_by_id)
    game = app_main.room_registry.get_game(game_id)

    assert int(game.rng_seed) == 222


def test_m8_api_04_injected_seed_should_be_consumed_once_for_next_game(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M8-API-04: injected seed applies to first new game only, then should be cleared."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m8_api_04.sqlite3", seed_injection_enabled="true")
    from app.api.routers import games as game_routes

    user_token_by_id = _prepare_three_members(app_main, "m8api04")

    game_routes.seed_injection(SeedInjectionRequest(seed=333))
    first_game_id = _start_game(app_main, user_token_by_id)
    first_game = app_main.room_registry.get_game(first_game_id)
    second_game_id = _reopen_next_game(app_main, user_token_by_id, first_game_id)
    second_game = app_main.room_registry.get_game(second_game_id)

    assert int(first_game.rng_seed) == 333
    assert second_game.rng_seed is None


def test_m8_api_05_injection_should_not_retroactively_affect_existing_game(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M8-API-05: ongoing game seed stays unchanged; injection only affects future new game."""
    app_main = _bootstrap_app(tmp_path, monkeypatch, "m8_api_05.sqlite3", seed_injection_enabled="true")
    from app.api.routers import games as game_routes

    user_token_by_id = _prepare_three_members(app_main, "m8api05")

    first_game_id = _start_game(app_main, user_token_by_id)
    first_game = app_main.room_registry.get_game(first_game_id)
    assert first_game.rng_seed is None

    game_routes.seed_injection(SeedInjectionRequest(seed=444))
    assert app_main.room_registry.get_game(first_game_id).rng_seed is None

    second_game_id = _reopen_next_game(app_main, user_token_by_id, first_game_id)
    second_game = app_main.room_registry.get_game(second_game_id)
    assert int(second_game.rng_seed) == 444
