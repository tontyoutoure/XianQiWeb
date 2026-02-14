"""Shared fixtures for M1 auth test skeletons."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def register_payload() -> dict[str, Any]:
    """Default register/login payload used by API tests."""
    return {"username": "Alice", "password": "123"}


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Placeholder auth headers; replace with a real access token fixture."""
    return {"Authorization": "Bearer <access_token>"}


@pytest.fixture
def ws_token() -> str:
    """Placeholder WS token; replace with a real access token fixture."""
    return "<access_token>"


@pytest.fixture
def app_not_ready() -> None:
    """Skip helper until FastAPI app and services are wired."""
    pytest.skip("M1 backend implementation is not wired yet")
