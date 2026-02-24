"""Process-wide runtime state shared by REST and WebSocket handlers."""

from __future__ import annotations

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


def startup() -> None:
    """Ensure auth schema exists and reset in-memory room/game runtime state."""
    global settings, room_registry, lobby_connections, room_connections, room_connection_users
    settings = load_settings()
    startup_auth_schema(settings)
    room_registry = RoomRegistry(room_count=settings.xqweb_room_count)
    lobby_connections = set()
    room_connections = {}
    room_connection_users = {}


__all__ = [
    "Settings",
    "lobby_connections",
    "room_connections",
    "room_connection_users",
    "room_registry",
    "settings",
    "startup",
]
