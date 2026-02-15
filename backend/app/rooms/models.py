"""Pydantic models for room APIs."""

from __future__ import annotations

from pydantic import BaseModel


class ReadyRequest(BaseModel):
    """POST /api/rooms/{room_id}/ready request body."""

    ready: bool

