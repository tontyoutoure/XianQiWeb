"""Auth module for M1 endpoints."""

from app.auth.http import handle_http_exception
from app.auth.models import LoginRequest
from app.auth.models import RegisterRequest
from app.auth.service import login_user
from app.auth.service import register_user
from app.auth.service import startup_auth_schema

__all__ = [
    "LoginRequest",
    "RegisterRequest",
    "handle_http_exception",
    "login_user",
    "register_user",
    "startup_auth_schema",
]
