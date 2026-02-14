"""Pydantic models for auth requests."""

from __future__ import annotations

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    """POST /api/auth/register request body."""

    username: str
    password: str


class LoginRequest(BaseModel):
    """POST /api/auth/login request body."""

    username: str
    password: str
