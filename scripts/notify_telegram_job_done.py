#!/usr/bin/env python3
"""Send a Telegram message when a job is done.

Required environment variables:
- CODEX_JOB_DONE_BOT_TOKEN
- CODEX_JOB_DONE_CHAT_ID
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BOT_TOKEN_ENV = "CODEX_JOB_DONE_BOT_TOKEN"
CHAT_ID_ENV = "CODEX_JOB_DONE_CHAT_ID"
PROXY_URL = "http://127.0.0.1:17890"
DEFAULT_MESSAGE = "Job done"
REQUEST_TIMEOUT_SECONDS = 10


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _build_request(bot_token: str, chat_id: str, message: str) -> urllib.request.Request:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": message,
        }
    ).encode("utf-8")
    return urllib.request.Request(
        url=url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )


def send_message(bot_token: str, chat_id: str, message: str) -> None:
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY_URL, "https": PROXY_URL})
    )
    request = _build_request(bot_token=bot_token, chat_id=chat_id, message=message)

    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(f"Telegram HTTP error {exc.code}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Telegram request failed via proxy {PROXY_URL}: {exc.reason}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Telegram returned non-JSON response: {body}") from exc

    if not parsed.get("ok"):
        description = parsed.get("description", "Unknown Telegram API error")
        raise RuntimeError(f"Telegram API rejected request: {description}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a Telegram notification for job completion")
    parser.add_argument(
        "--message",
        default=DEFAULT_MESSAGE,
        help=f"Message text to send (default: {DEFAULT_MESSAGE!r})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        bot_token = _get_required_env(BOT_TOKEN_ENV)
        chat_id = _get_required_env(CHAT_ID_ENV)
        send_message(bot_token=bot_token, chat_id=chat_id, message=args.message)
    except RuntimeError as exc:
        print(f"[notify_telegram_job_done] {exc}", file=sys.stderr)
        return 1

    print("[notify_telegram_job_done] message sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
