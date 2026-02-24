"""WebSocket heartbeat and message-loop utilities."""

from __future__ import annotations

import asyncio
from datetime import datetime
from datetime import timezone
import json
from typing import Any

from fastapi import WebSocketDisconnect

from app.core.tokens import AccessTokenExpiredError
from app.core.tokens import AccessTokenInvalidError
from app.core.tokens import decode_access_token

from .protocol import ws_send_event


class HeartbeatState:
    """Track one websocket heartbeat ping/pong lifecycle."""

    def __init__(self) -> None:
        self.last_ping_at: float | None = None
        self.last_pong_at: float | None = None
        self.missed_pong_count = 0
        self._awaiting_pong = False
        self._pong_event = asyncio.Event()

    def mark_ping_sent(self) -> None:
        self.last_ping_at = datetime.now(timezone.utc).timestamp()
        self._awaiting_pong = True
        self._pong_event.clear()

    def mark_pong_received(self) -> None:
        self.last_pong_at = datetime.now(timezone.utc).timestamp()
        if not self._awaiting_pong:
            return
        self._awaiting_pong = False
        self.missed_pong_count = 0
        self._pong_event.set()

    async def wait_for_pong(self, *, timeout_seconds: float) -> bool:
        if not self._awaiting_pong:
            return True
        try:
            await asyncio.wait_for(self._pong_event.wait(), timeout=timeout_seconds)
        except TimeoutError:
            self._awaiting_pong = False
            self.missed_pong_count += 1
            return False
        return True


def is_pong_message(message: str) -> bool:
    if message == "PONG":
        return True
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return payload.get("type") == "PONG"


def token_expiry_epoch(access_token: str) -> int | None:
    now = datetime.now(timezone.utc)
    try:
        payload = decode_access_token(access_token, now=now)
    except (AccessTokenInvalidError, AccessTokenExpiredError):
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int):
        return None
    return exp


async def send_heartbeat_ping(websocket: Any) -> None:
    await ws_send_event(websocket, "PING", {})


async def reply_with_pong(websocket: Any) -> None:
    await ws_send_event(websocket, "PONG", {})


async def handle_ws_message(*, websocket: Any, heartbeat_state: HeartbeatState, message: str) -> None:
    if message == "PING":
        await reply_with_pong(websocket)
        return
    if is_pong_message(message):
        heartbeat_state.mark_pong_received()


async def heartbeat_loop(
    websocket: Any,
    *,
    heartbeat_state: HeartbeatState,
    interval_seconds: float = 30.0,
    pong_timeout_seconds: float = 10.0,
    max_missed_pongs: int = 2,
) -> None:
    sleep_after_probe = max(interval_seconds - pong_timeout_seconds, 0.0)
    while True:
        await send_heartbeat_ping(websocket)
        heartbeat_state.mark_ping_sent()
        pong_received = await heartbeat_state.wait_for_pong(timeout_seconds=pong_timeout_seconds)
        if (not pong_received) and heartbeat_state.missed_pong_count >= max_missed_pongs:
            await websocket.close(code=4408, reason="HEARTBEAT_TIMEOUT")
            return
        if sleep_after_probe > 0:
            await asyncio.sleep(sleep_after_probe)


async def close_ws_on_token_expire(websocket: Any, *, expire_epoch: int) -> None:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    delay_seconds = max(float(expire_epoch - now_ts), 0.0)
    await asyncio.sleep(delay_seconds)
    try:
        await websocket.close(code=4401, reason="UNAUTHORIZED")
    except Exception:
        return


async def ws_message_loop(websocket: Any, *, token_expire_epoch_value: int | None = None) -> None:
    heartbeat_state = HeartbeatState()
    heartbeat_task = asyncio.create_task(heartbeat_loop(websocket, heartbeat_state=heartbeat_state))
    token_expiry_task: asyncio.Task[Any] | None = None
    if token_expire_epoch_value is not None:
        token_expiry_task = asyncio.create_task(
            close_ws_on_token_expire(websocket, expire_epoch=token_expire_epoch_value)
        )
    try:
        while True:
            message = await websocket.receive_text()
            await handle_ws_message(websocket=websocket, heartbeat_state=heartbeat_state, message=message)
    except WebSocketDisconnect:
        return
    finally:
        heartbeat_task.cancel()
        if token_expiry_task is not None:
            token_expiry_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        if token_expiry_task is not None:
            try:
                await token_expiry_task
            except asyncio.CancelledError:
                pass
