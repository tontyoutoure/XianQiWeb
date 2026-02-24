"""FastAPI application entrypoint and route assembly."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import JSONResponse

import app.runtime as runtime
from app.api.routers import auth as auth_routes
from app.api.routers import games as game_routes
from app.api.routers import rooms as room_routes
from app.auth.http import handle_http_exception
from app.auth.models import LoginRequest
from app.auth.models import LogoutRequest
from app.auth.models import RefreshRequest
from app.auth.models import RegisterRequest
from app.core.config import Settings
from app.rooms.models import GameActionRequest
from app.rooms.models import ReadyRequest
from app.rooms.registry import MAX_ROOM_MEMBERS
from app.rooms.registry import RoomFullError
from app.rooms.registry import RoomRegistry
from app.ws import routers as ws_routes

settings = runtime.settings
room_registry = runtime.room_registry
_lobby_connections = runtime.lobby_connections
_room_connections = runtime.room_connections
_room_connection_users = runtime.room_connection_users


def _sync_runtime_exports() -> None:
    global settings, room_registry, _lobby_connections, _room_connections, _room_connection_users
    settings = runtime.settings
    room_registry = runtime.room_registry
    _lobby_connections = runtime.lobby_connections
    _room_connections = runtime.room_connections
    _room_connection_users = runtime.room_connection_users


def startup() -> None:
    """Ensure auth schema exists and reset in-memory room/game runtime state."""
    runtime.startup()
    _sync_runtime_exports()


@asynccontextmanager
async def lifespan(_: FastAPI):
    startup()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(auth_routes.router)
app.include_router(room_routes.router)
app.include_router(game_routes.router)
app.include_router(ws_routes.router)


@app.exception_handler(HTTPException)
async def handle_http_exception_route(request: Request, exc: HTTPException) -> JSONResponse:
    """Adapter used by FastAPI exception handling."""
    return await handle_http_exception(request, exc)


# Keep old symbol exports for existing tests and call sites.
register = auth_routes.register
login = auth_routes.login
me = auth_routes.me
refresh = auth_routes.refresh
logout = auth_routes.logout
me_route = auth_routes.me_route

list_rooms = room_routes.list_rooms
get_room_detail = room_routes.get_room_detail
join_room = room_routes.join_room
leave_room = room_routes.leave_room
set_room_ready = room_routes.set_room_ready
_start_game_hook_if_all_ready = room_routes._start_game_hook_if_all_ready

get_game_state = game_routes.get_game_state
post_game_action = game_routes.post_game_action
get_game_settlement = game_routes.get_game_settlement

ws_lobby = ws_routes.ws_lobby
ws_room = ws_routes.ws_room


__all__ = [
    "Settings",
    "RegisterRequest",
    "LoginRequest",
    "LogoutRequest",
    "RefreshRequest",
    "ReadyRequest",
    "GameActionRequest",
    "MAX_ROOM_MEMBERS",
    "RoomRegistry",
    "RoomFullError",
    "app",
    "handle_http_exception",
    "handle_http_exception_route",
    "login",
    "logout",
    "me",
    "me_route",
    "refresh",
    "register",
    "_start_game_hook_if_all_ready",
    "settings",
    "startup",
    "ws_lobby",
    "ws_room",
]
