"""M1-API-07 contract test skeleton."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("app_not_ready")


def test_m1_api_07_me_requires_valid_bearer_token() -> None:
    """Contract: GET /api/auth/me returns current user for valid access token."""
