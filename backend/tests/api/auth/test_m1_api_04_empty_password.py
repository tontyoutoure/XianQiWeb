"""M1-API-04 contract test skeleton."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("app_not_ready")


def test_m1_api_04_empty_password_is_allowed_in_mvp() -> None:
    """Contract: register/login accepts empty password in MVP."""
