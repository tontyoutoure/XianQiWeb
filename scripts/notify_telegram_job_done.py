#!/usr/bin/env python3
"""Send a Telegram message for manual calls or Codex notify hooks.

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
DEFAULT_PROMPT_PLACEHOLDER = "(from codex notify)"
DEFAULT_SUMMARY_PLACEHOLDER = "(no assistant summary)"


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
    parser = argparse.ArgumentParser(
        description="Send a Telegram notification for job completion or Codex notify events"
    )
    parser.add_argument(
        "--message",
        default=None,
        help="Message text to send directly. If omitted, tries Codex notify JSON payload.",
    )
    parser.add_argument(
        "payload",
        nargs="?",
        default=None,
        help="Codex notify JSON payload (usually passed automatically by Codex as argv[1]).",
    )
    return parser.parse_args()


def _coerce_to_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _truncate_text(text: str, max_len: int = 80) -> str:
    clean = " ".join(text.strip().split())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 3] + "..."


def _build_message_from_payload(payload_text: str) -> str:
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid Codex notify JSON payload") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Codex notify payload must be a JSON object")

    event_type = _coerce_to_str(payload.get("type"))
    if event_type and event_type != "agent-turn-complete":
        return ""

    input_messages = payload.get("input-messages")
    if input_messages is None:
        input_messages = payload.get("input_messages")
    prompt_text = ""
    if isinstance(input_messages, list):
        prompt_text = _coerce_to_str(input_messages[-1]) if input_messages else ""
    if not prompt_text:
        prompt_text = _coerce_to_str(payload.get("prompt"))
    if not prompt_text:
        prompt_text = DEFAULT_PROMPT_PLACEHOLDER

    summary_text = _coerce_to_str(payload.get("last-assistant-message"))
    if not summary_text:
        summary_text = _coerce_to_str(payload.get("last_assistant_message"))
    if not summary_text:
        summary_text = DEFAULT_SUMMARY_PLACEHOLDER

    return (
        f"prompt: {_truncate_text(prompt_text, max_len=120)}\n"
        f"response summary: {_truncate_text(summary_text, max_len=45)}"
    )


def main() -> int:
    with open("telegram.log", "w+") as f:
        f.write(sys.argv[1])

    # try:
    #     bot_token = _get_required_env(BOT_TOKEN_ENV)
    #     chat_id = _get_required_env(CHAT_ID_ENV)
    #     if args.message:
    #         message = args.message
    #     elif args.payload:
    #         message = _build_message_from_payload(args.payload)
    #     elif not sys.stdin.isatty():
    #         stdin_text = sys.stdin.read().strip()
    #         message = _build_message_from_payload(stdin_text) if stdin_text else DEFAULT_MESSAGE
    #     else:
    #         message = DEFAULT_MESSAGE

    #     if not message:
    #         print("[notify_telegram_job_done] skipped: unsupported notify event type")
    #         return 0

    #     send_message(bot_token=bot_token, chat_id=chat_id, message=message)
    # except RuntimeError as exc:
    #     print(f"[notify_telegram_job_done] {exc}", file=sys.stderr)
    #     return 1

    # print("[notify_telegram_job_done] message sent")
    # return 0


if __name__ == "__main__":
    raise SystemExit(main())
