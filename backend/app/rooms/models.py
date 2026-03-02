"""Pydantic models for room APIs."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field


class ReadyRequest(BaseModel):
    """POST /api/rooms/{room_id}/ready request body."""

    ready: bool


class GameActionRequest(BaseModel):
    """POST /api/games/{game_id}/actions request body."""

    action_idx: int
    client_version: int | None = None
    cover_list: dict[str, int] | None = None


class SeedInjectionRequest(BaseModel):
    """POST /api/games/seed-injection request body."""

    seed: int = Field(ge=0)
