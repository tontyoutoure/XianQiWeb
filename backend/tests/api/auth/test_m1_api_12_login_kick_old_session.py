"""M1-API-12 contract test skeleton."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("app_not_ready")


def test_m1_api_12_login_kicks_old_session_refresh_but_old_access_still_works_until_expiry() -> None:
    """Contract: new login revokes previous refresh; old access valid until exp."""
