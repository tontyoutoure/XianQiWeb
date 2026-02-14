"""FastAPI application entrypoint for M1 auth contracts."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import Settings
from app.core.config import load_settings
from app.core.db import create_sqlite_connection
from app.core.password import hash_password
from app.core.tokens import create_access_token
from app.core.username import UsernameValidationError
from app.core.username import normalize_and_validate_username


CREATE_AUTH_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revoked_at TEXT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
"""


class RegisterRequest(BaseModel):
    """POST /api/auth/register request body."""

    username: str
    password: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash_refresh_token(plain_token: str) -> str:
    return hashlib.sha256(plain_token.encode("utf-8")).hexdigest()


def _init_schema(settings: Settings) -> None:
    conn = create_sqlite_connection(settings.xqweb_sqlite_path)
    try:
        conn.executescript(CREATE_AUTH_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def _build_auth_response(*, settings: Settings, user_id: int, username: str, created_at: str) -> dict[str, object]:
    now = _utc_now()
    access_token = create_access_token(
        user_id=user_id,
        now=now,
        expires_in_seconds=settings.xqweb_access_token_expire_seconds,
    )
    refresh_plain = secrets.token_urlsafe(32)

    conn = create_sqlite_connection(settings.xqweb_sqlite_path)
    try:
        refresh_expires_at = _to_utc_iso(
            now + timedelta(seconds=settings.xqweb_refresh_token_expire_seconds)
        )
        conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at, created_at, revoked_at)
            VALUES (?, ?, ?, ?, NULL)
            """,
            (user_id, _hash_refresh_token(refresh_plain), refresh_expires_at, _to_utc_iso(now)),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "access_token": access_token,
        "expires_in": settings.xqweb_access_token_expire_seconds,
        "refresh_token": refresh_plain,
        "refresh_expires_in": settings.xqweb_refresh_token_expire_seconds,
        "user": {"id": user_id, "username": username, "created_at": created_at},
    }


def _api_error(*, code: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "detail": detail or {}}


settings = load_settings()


def startup() -> None:
    """Ensure M1 auth tables exist before handling traffic."""
    _init_schema(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    startup()
    yield


app = FastAPI(lifespan=lifespan)


@app.exception_handler(HTTPException)
async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
    """Unify HTTP errors to {code,message,detail} payload."""
    if isinstance(exc.detail, dict) and {"code", "message", "detail"} <= set(exc.detail):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
            headers=exc.headers,
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=_api_error(
            code="HTTP_ERROR",
            message=str(exc.detail),
            detail={},
        ),
        headers=exc.headers,
    )


@app.post("/api/auth/register")
def register(payload: RegisterRequest) -> dict[str, object]:
    """Create user + auth session for MVP register flow."""
    try:
        normalized_username = normalize_and_validate_username(payload.username)
    except UsernameValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=_api_error(code="VALIDATION_ERROR", message=str(exc), detail={}),
        ) from exc

    created_at = _to_utc_iso(_utc_now())
    password_hash = hash_password(payload.password)

    conn = create_sqlite_connection(settings.xqweb_sqlite_path)
    try:
        conn.execute("BEGIN")
        cursor = conn.execute(
            """
            INSERT INTO users (username, password_hash, created_at)
            VALUES (?, ?, ?)
            """,
            (normalized_username, password_hash, created_at),
        )
        user_id = int(cursor.lastrowid)
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise HTTPException(
            status_code=409,
            detail=_api_error(
                code="AUTH_USERNAME_CONFLICT",
                message="username already exists",
                detail={},
            ),
        ) from exc
    finally:
        conn.close()

    return _build_auth_response(
        settings=settings,
        user_id=user_id,
        username=normalized_username,
        created_at=created_at,
    )
