"""Process-wide runtime state shared by REST and WebSocket handlers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.auth.service import startup_auth_schema
from app.core.config import Settings
from app.core.config import load_settings
from app.rooms.registry import RoomRegistry

settings = load_settings()
room_registry = RoomRegistry(room_count=settings.xqweb_room_count)
lobby_connections: set[Any] = set()
room_connections: dict[int, set[Any]] = {}
room_connection_users: dict[Any, int] = {}
next_game_seed: int | None = None


def _run_seed_hunting_mode(settings: Settings) -> int:
    """Run lightweight catalog scan and return process exit code."""
    if not settings.xqweb_seed_catalog_dir:
        return 1

    catalog_dir = Path(settings.xqweb_seed_catalog_dir)
    seen_test_ids: set[str] = set()

    for json_file in sorted(catalog_dir.glob("*.json")):
        with json_file.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        cases = payload.get("cases", [])
        if not isinstance(cases, list):
            raise ValueError(f"seed catalog file must provide list cases: {json_file}")
        for case in cases:
            test_id = case.get("test_id")
            if isinstance(test_id, str):
                if test_id in seen_test_ids:
                    raise ValueError(f"duplicate test_id in seed catalog: {test_id}")
                seen_test_ids.add(test_id)

    return 0


def startup() -> None:
    """Ensure auth schema exists and reset in-memory room/game runtime state."""
    global settings, room_registry, lobby_connections, room_connections, room_connection_users, next_game_seed
    settings = load_settings()
    if settings.xqweb_seed_catalog_dir:
        raise SystemExit(_run_seed_hunting_mode(settings))

    startup_auth_schema(settings)
    room_registry = RoomRegistry(room_count=settings.xqweb_room_count)
    lobby_connections = set()
    room_connections = {}
    room_connection_users = {}
    next_game_seed = None


__all__ = [
    "Settings",
    "lobby_connections",
    "room_connections",
    "room_connection_users",
    "room_registry",
    "settings",
    "startup",
    "next_game_seed",
]
