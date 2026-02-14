"""FastAPI application entrypoint for M1 auth contracts."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import JSONResponse

from app.auth.errors import raise_token_invalid
from app.auth.http import handle_http_exception
from app.auth.models import LoginRequest
from app.auth.models import RegisterRequest
from app.auth.service import login_user
from app.auth.service import me_user
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


@app.get("/api/auth/me")
def me_route(authorization: str | None = Header(default=None, alias="Authorization")) -> dict[str, object]:
    """HTTP wrapper for /api/auth/me Bearer auth."""
    if authorization is None:
        raise_token_invalid()

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise_token_invalid()

    return me(token)


__all__ = [
    "Settings",
    "RegisterRequest",
    "LoginRequest",
    "app",
    "handle_http_exception",
    "login",
    "me",
    "register",
    "settings",
    "startup",
]
