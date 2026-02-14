"""M1-API-08 contract test skeleton."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("app_not_ready")


def test_m1_api_08_me_rejects_missing_or_invalid_token() -> None:
    """Contract: GET /api/auth/me returns 401 without valid access token."""
