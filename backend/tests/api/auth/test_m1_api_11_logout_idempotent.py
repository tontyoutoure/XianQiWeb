"""M1-API-11 contract test skeleton."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("app_not_ready")


def test_m1_api_11_logout_revokes_specified_refresh_token_idempotently() -> None:
    """Contract: POST /api/auth/logout is idempotent and revokes target refresh token."""
