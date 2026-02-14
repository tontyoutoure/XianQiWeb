"""FastAPI application entrypoint for M1 auth contracts."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.auth.errors import raise_token_invalid
from app.auth.models import LogoutRequest
from app.auth.http import handle_http_exception
from app.auth.models import LoginRequest
from app.auth.models import RefreshRequest
from app.auth.models import RegisterRequest
from app.auth.service import login_user
from app.auth.service import logout_user
from app.auth.service import me_user
from app.auth.service import refresh_user
from app.auth.service import register_user
from app.auth.service import startup_auth_schema
from app.core.config import Settings
from app.core.config import load_settings

settings = load_settings()


def startup() -> None:
    """Ensure M1 auth tables exist before handling traffic."""
    startup_auth_schema(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    startup()
    yield


app = FastAPI(lifespan=lifespan)


@app.exception_handler(HTTPException)
async def handle_http_exception_route(request: Request, exc: HTTPException) -> JSONResponse:
    """Adapter used by FastAPI exception handling."""
    return await handle_http_exception(request, exc)


@app.post("/api/auth/register")
def register(payload: RegisterRequest) -> dict[str, object]:
    """Create user + auth session for MVP register flow."""
    return register_user(settings=settings, payload=payload)


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, object]:
    """Authenticate user and issue a fresh auth session."""
    return login_user(settings=settings, payload=payload)


def me(access_token: str) -> dict[str, object]:
    """Return current user profile for a valid access token."""
    return me_user(settings=settings, access_token=access_token)


async def _close_ws_unauthorized(websocket: WebSocket) -> None:
    """Close websocket with unified unauthorized semantics."""
    await websocket.accept()
    await websocket.close(code=4401, reason="UNAUTHORIZED")


@app.post("/api/auth/refresh")
def refresh(payload: RefreshRequest) -> dict[str, object]:
    """Rotate refresh token and issue a new access/refresh pair."""
    return refresh_user(settings=settings, payload=payload)


@app.post("/api/auth/logout")
def logout(payload: LogoutRequest) -> dict[str, bool]:
    """Revoke the provided refresh token idempotently."""
    return logout_user(settings=settings, payload=payload)


@app.get("/api/auth/me")
def me_route(authorization: str | None = Header(default=None, alias="Authorization")) -> dict[str, object]:
    """HTTP wrapper for /api/auth/me Bearer auth."""
    if authorization is None:
        raise_token_invalid()

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise_token_invalid()

    return me(token)


@app.websocket("/ws/lobby")
async def ws_lobby(websocket: WebSocket) -> None:
    """Minimal M1 lobby websocket with access-token auth."""
    token = websocket.query_params.get("token")
    if token is None or token == "":
        await _close_ws_unauthorized(websocket)
        return

    try:
        me(token)
    except HTTPException:
        await _close_ws_unauthorized(websocket)
        return

    await websocket.accept()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return


@app.websocket("/ws/rooms/{room_id}")
async def ws_room(websocket: WebSocket, room_id: int) -> None:
    """Room websocket auth stub for M1."""
    _ = room_id
    token = websocket.query_params.get("token")
    if token is None or token == "":
        await _close_ws_unauthorized(websocket)
        return

    try:
        me(token)
    except HTTPException:
        await _close_ws_unauthorized(websocket)
        return

    await websocket.accept()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return


__all__ = [
    "Settings",
    "RegisterRequest",
    "LoginRequest",
    "LogoutRequest",
    "RefreshRequest",
    "app",
    "handle_http_exception",
    "login",
    "logout",
    "me",
    "refresh",
    "register",
    "settings",
    "startup",
    "ws_lobby",
    "ws_room",
]
