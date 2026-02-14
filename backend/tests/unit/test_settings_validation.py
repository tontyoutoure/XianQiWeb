"""M1-UT-06 configuration guard contract test (RED phase)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


from app.core.config import Settings


@pytest.mark.parametrize(
    ("refresh_interval", "access_expire"),
    [
        (3600, 3600),
        (3601, 3600),
    ],
)
def test_m1_ut_06_refresh_interval_less_than_access_expire(
    refresh_interval: int,
    access_expire: int,
) -> None:
    """Input: refresh interval >= access expiry -> Output: settings validation fails."""
    with pytest.raises(ValidationError):
        Settings(
            xqweb_jwt_secret="unit-test-secret",
            xqweb_access_token_refresh_interval_seconds=refresh_interval,
            xqweb_access_token_expire_seconds=access_expire,
        )
