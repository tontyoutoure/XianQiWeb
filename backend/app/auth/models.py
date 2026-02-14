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


class RefreshRequest(BaseModel):
    """POST /api/auth/refresh request body."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """POST /api/auth/logout request body."""

    refresh_token: str
