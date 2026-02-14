"""M1-API-03 contract test skeleton."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("app_not_ready")


def test_m1_api_03_username_is_case_sensitive() -> None:
    """Contract: Tom and tom can both register as different users."""
