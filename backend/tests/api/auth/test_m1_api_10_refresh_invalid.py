"""M1-API-10 contract test skeleton."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("app_not_ready")


def test_m1_api_10_refresh_rejects_revoked_expired_or_random_token() -> None:
    """Contract: invalid refresh token returns 401."""
