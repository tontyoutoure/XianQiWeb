"""Process-wide runtime state shared by REST and WebSocket handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.auth.service import startup_auth_schema
from app.core.config import Settings
from app.core.config import load_settings
from app.rooms.registry import RoomRegistry
from app.seed_hunter import run_seed_hunting_mode

settings = load_settings()
lobby_connections: set[Any] = set()
room_connections: dict[int, set[Any]] = {}
room_connection_users: dict[Any, int] = {}
next_game_seed: int | None = None


def consume_next_game_seed() -> int | None:
    """Consume and clear the one-shot seed for the next new game."""
    global next_game_seed
    seed = next_game_seed
    next_game_seed = None
    return seed


room_registry = RoomRegistry(
    room_count=settings.xqweb_room_count,
    next_game_seed_provider=consume_next_game_seed,
)


def _run_seed_hunting_mode(settings: Settings) -> int:
    """Run catalog seed hunting and return process exit code."""
    if not settings.xqweb_seed_catalog_dir:
        return 1

    catalog_dir = Path(settings.xqweb_seed_catalog_dir)
    return run_seed_hunting_mode(catalog_dir)


def exit_if_seed_hunting_mode() -> None:
    """Exit current process after running seed hunting in catalog mode."""
    if settings.xqweb_seed_catalog_dir:
        raise SystemExit(_run_seed_hunting_mode(settings))


def startup() -> None:
    """Ensure auth schema exists and reset in-memory room/game runtime state."""
    global settings, room_registry, lobby_connections, room_connections, room_connection_users, next_game_seed
    settings = load_settings()
    exit_if_seed_hunting_mode()

    startup_auth_schema(settings)
    room_registry = RoomRegistry(
        room_count=settings.xqweb_room_count,
        next_game_seed_provider=consume_next_game_seed,
    )
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
    "consume_next_game_seed",
    "exit_if_seed_hunting_mode",
]
