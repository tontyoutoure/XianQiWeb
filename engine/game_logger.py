"""Lightweight file logger for local engine state/action traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GameLogger:
    """Persist per-version state snapshots and action traces to disk."""

    def __init__(self, log_path: str | Path) -> None:
        self._log_dir = Path(log_path)

    def reset(self) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)

        for state_file in self._log_dir.glob("state_v*.json"):
            if state_file.is_file():
                state_file.unlink()

        for filename in ("action.json", "settle.json"):
            target = self._log_dir / filename
            if target.is_file():
                target.unlink()

    def write_state(self, version: int, state: dict[str, Any]) -> None:
        self._write_json(self._log_dir / f"state_v{int(version)}.json", state)

    def append_action(self, record: dict[str, Any]) -> None:
        target = self._log_dir / "action.json"
        current = self._read_json(target)
        if not isinstance(current, list):
            current = []
        current.append(record)
        self._write_json(target, current)

    def write_settlement(self, settlement_payload: dict[str, Any]) -> None:
        self._write_json(self._log_dir / "settle.json", settlement_payload)

    @staticmethod
    def _read_json(path: Path) -> Any:
        if not path.is_file():
            return []
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.tmp")
        with temp_path.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temp_path.replace(path)
