"""In-memory refresh token store used by M1 unit tests."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta


class RefreshTokenInvalidError(ValueError):
    """Raised when a refresh token is missing, revoked, or expired."""


@dataclass
class RefreshTokenRecord:
    """Stored refresh token metadata."""

    user_id: int
    token_hash: str
    expires_at: datetime
    created_at: datetime
    revoked_at: datetime | None = None


class RefreshTokenStore:
    """Simple in-memory store that supports issue/validate/rotate semantics."""

    def __init__(self) -> None:
        self._records: dict[str, RefreshTokenRecord] = {}

    def issue(self, *, user_id: int, now: datetime, expires_in_seconds: int) -> str:
        """Issue a new refresh token and persist only its hash."""
        plain = secrets.token_urlsafe(32)
        token_hash = self._hash_token(plain)
        self._records[token_hash] = RefreshTokenRecord(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=now + timedelta(seconds=expires_in_seconds),
            created_at=now,
        )
        return plain

    def validate(self, plain_token: str, *, now: datetime) -> RefreshTokenRecord:
        """Validate token and return its record."""
        token_hash = self._hash_token(plain_token)
        record = self._records.get(token_hash)
        if record is None:
            raise RefreshTokenInvalidError("refresh token not found")
        if record.revoked_at is not None:
            raise RefreshTokenInvalidError("refresh token revoked")
        if now >= record.expires_at:
            raise RefreshTokenInvalidError("refresh token expired")
        return record

    def rotate(self, plain_token: str, *, now: datetime, expires_in_seconds: int) -> str:
        """Revoke old token and issue a new token for the same user."""
        old_record = self.validate(plain_token, now=now)
        old_record.revoked_at = now
        return self.issue(user_id=old_record.user_id, now=now, expires_in_seconds=expires_in_seconds)

    @staticmethod
    def _hash_token(plain_token: str) -> str:
        return hashlib.sha256(plain_token.encode("utf-8")).hexdigest()
