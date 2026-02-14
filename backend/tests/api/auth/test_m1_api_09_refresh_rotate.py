"""M1-API-09 contract test skeleton."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("app_not_ready")


def test_m1_api_09_refresh_rotates_refresh_token() -> None:
    """Contract: POST /api/auth/refresh returns new pair and revokes old refresh."""
