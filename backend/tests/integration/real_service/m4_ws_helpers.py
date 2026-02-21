"""Scaffold helpers for M4 real-service websocket tests.

This module intentionally contains signatures only.
Implement helpers after specific M4 test IDs are assigned.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


async def open_lobby_ws(*, ws_base_url: str, access_token: str) -> Any:
    """Open lobby websocket for one authenticated user."""
    raise NotImplementedError("M4 scaffold only; helper body pending")


async def open_room_ws(*, ws_base_url: str, access_token: str, room_id: int) -> Any:
    """Open room websocket for one authenticated user."""
    raise NotImplementedError("M4 scaffold only; helper body pending")


async def recv_until(
    ws: Any,
    *,
    event_type: str,
    timeout_seconds: float = 5.0,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    """Receive websocket events until event_type/predicate match."""
    raise NotImplementedError("M4 scaffold only; helper body pending")


def assert_event_order(*, events: list[dict[str, Any]], expected_types: list[str]) -> None:
    """Assert websocket events are ordered by expected_types."""
    raise NotImplementedError("M4 scaffold only; helper body pending")
