"""WebSocket wire protocol helpers."""

from __future__ import annotations

import json
from typing import Any

WS_PROTOCOL_VERSION = 1


def ws_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"v": WS_PROTOCOL_VERSION, "type": event_type, "payload": payload}


async def ws_send_event(websocket: Any, event_type: str, payload: dict[str, Any]) -> None:
    message = ws_event(event_type, payload)
    if hasattr(websocket, "send_json"):
        await websocket.send_json(message)
        return
    if hasattr(websocket, "send_text"):
        await websocket.send_text(json.dumps(message))
