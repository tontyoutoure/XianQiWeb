"""Standalone WS probe used by M1 WS contract tests."""

from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.tokens import create_access_token


def _pick_token(*, mode: str, access_token: str, user_id: int) -> str:
    if mode == "valid":
        return access_token
    if mode == "invalid":
        return "invalid-token"
    if mode == "expired":
        return create_access_token(
            user_id=user_id,
            now=datetime(2026, 2, 14, tzinfo=timezone.utc) - timedelta(hours=2),
            expires_in_seconds=3600,
        )
    raise ValueError(f"unknown mode: {mode}")


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"result": "error", "message": "usage: ws_probe.py <valid|invalid|expired>"}))
        return 2

    mode = sys.argv[1]

    import app.main as app_main

    app_main = importlib.reload(app_main)
    app_main.startup()
    register_result = app_main.register(app_main.RegisterRequest(username="Alice", password="123"))
    access_token = str(register_result["access_token"])
    user_id = int(register_result["user"]["id"])
    token = _pick_token(mode=mode, access_token=access_token, user_id=user_id)

    client = TestClient(app_main.app)
    try:
        with client.websocket_connect(f"/ws/lobby?token={token}"):
            print(json.dumps({"result": "connected"}))
            return 0
    except WebSocketDisconnect as exc:
        print(json.dumps({"result": "disconnect", "code": exc.code, "reason": exc.reason}))
        return 0
    except Exception as exc:  # pragma: no cover - exercised in RED phase.
        print(
            json.dumps(
                {
                    "result": "error",
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
            )
        )
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
