"""M1-API-02 contract test (RED phase)."""

from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.exception_handlers import http_exception_handler
from starlette.requests import Request


def _build_http_request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [],
            "query_string": b"",
        }
    )


def test_m1_api_02_register_rejects_duplicate_username_with_nfc_equivalence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract: equivalent normalized usernames conflict with 409 + unified error shape."""
    db_path = tmp_path / "m1_api_02.sqlite3"
    monkeypatch.setenv("XQWEB_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("XQWEB_JWT_SECRET", "api-02-test-secret")

    import app.main as app_main

    app_main = importlib.reload(app_main)

    app_main.startup()
    app_main.register(app_main.RegisterRequest(username="é", password="123"))

    with pytest.raises(HTTPException) as exc_info:
        app_main.register(app_main.RegisterRequest(username="é", password="123"))

    response = asyncio.run(
        http_exception_handler(_build_http_request("/api/auth/register"), exc_info.value)
    )
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 409
    assert payload == {
        "code": "AUTH_USERNAME_CONFLICT",
        "message": "username already exists",
        "detail": {},
    }
