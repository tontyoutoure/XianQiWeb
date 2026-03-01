#!/usr/bin/env python3
"""Send sys.argv[1] to Telegram."""

import json
import os
import sys
import urllib.error
import urllib.request

BOT_TOKEN_ENV = "CODEX_JOB_DONE_BOT_TOKEN"
CHAT_ID_ENV = "CODEX_JOB_DONE_CHAT_ID"
PROXY_URL = "http://127.0.0.1:17890"
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


def _format_input_messages(input_messages: object) -> str:
    if isinstance(input_messages, list):
        for item in reversed(input_messages):
            text = str(item).strip()
            if text:
                return text
        return "(empty)"
    if input_messages is None:
        return "(empty)"

    text = str(input_messages).strip()
    return text or "(empty)"


def _extract_input_output_message(raw_message: str) -> str:
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError:
        return raw_message

    if not isinstance(payload, dict):
        return raw_message

    input_messages = payload.get("input-messages")
    output_message = payload.get("last-assistant-message")

    if input_messages is None and output_message is None:
        return raw_message

    input_text = _format_input_messages(input_messages)
    output_text = str(output_message).strip() if output_message is not None else "(empty)"
    if not output_text:
        output_text = "(empty)"

    return f"输入:\n{input_text}\n\n输出:\n{output_text}"


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: notify_telegram_job_done.py <message>", file=sys.stderr)
        return 1

    raw_message = sys.argv[1]
    message = _extract_input_output_message(raw_message)

    try:
        bot_token = _get_required_env(BOT_TOKEN_ENV)
        chat_id = _get_required_env(CHAT_ID_ENV)
        send_message(bot_token=bot_token, chat_id=chat_id, message=message)
    except RuntimeError as exc:
        print(f"[notify_telegram_job_done] {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
