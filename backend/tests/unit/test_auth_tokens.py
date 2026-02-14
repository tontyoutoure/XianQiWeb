"""M1-UT-02/03 token contract tests (RED phase)."""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from app.core.refresh_tokens import RefreshTokenInvalidError
from app.core.refresh_tokens import RefreshTokenStore
from app.core.tokens import AccessTokenExpiredError
from app.core.tokens import create_access_token
from app.core.tokens import decode_access_token


def test_m1_ut_02_access_jwt_contains_sub_and_exp() -> None:
    """Input: user_id=1 token in valid window -> Output: payload includes sub/exp."""
    now = datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc)
    token = create_access_token(user_id=1, now=now, expires_in_seconds=60)

    payload = decode_access_token(token, now=now + timedelta(seconds=30))

    assert payload["sub"] == "1"
    assert isinstance(payload["exp"], int)


def test_m1_ut_02_access_jwt_expired_token_is_rejected() -> None:
    """Input: token after exp -> Output: raises AccessTokenExpiredError."""
    now = datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc)
    token = create_access_token(user_id=1, now=now, expires_in_seconds=1)

    with pytest.raises(AccessTokenExpiredError):
        decode_access_token(token, now=now + timedelta(seconds=2))


def test_m1_ut_03_refresh_rotate_revokes_old_token() -> None:
    """Input: issue + rotate -> Output: old revoked, new usable."""
    now = datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc)
    store = RefreshTokenStore()

    old_plain = store.issue(user_id=1, now=now, expires_in_seconds=3600)
    new_plain = store.rotate(old_plain, now=now + timedelta(seconds=10), expires_in_seconds=3600)

    assert new_plain != old_plain

    with pytest.raises(RefreshTokenInvalidError):
        store.validate(old_plain, now=now + timedelta(seconds=11))

    assert store.validate(new_plain, now=now + timedelta(seconds=11)).user_id == 1
