"""M1-API-05 contract test skeleton."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("app_not_ready")


def test_m1_api_05_login_success_returns_new_token_pair() -> None:
    """Contract: POST /api/auth/login returns a fresh token pair."""
