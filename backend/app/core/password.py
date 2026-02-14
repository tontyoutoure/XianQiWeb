"""Password hashing helpers for auth services."""

from __future__ import annotations

from passlib.context import CryptContext
from passlib.exc import UnknownHashError

# Keep algorithms centralized so auth code only depends on these helpers.
_PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash plaintext password using bcrypt."""
    return _PASSWORD_CONTEXT.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    try:
        return _PASSWORD_CONTEXT.verify(plain_password, password_hash)
    except UnknownHashError:
        return False
