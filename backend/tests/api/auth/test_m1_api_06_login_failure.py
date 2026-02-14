"""M1-API-06 contract test skeleton."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("app_not_ready")


def test_m1_api_06_login_failure_returns_401_with_unified_error_shape() -> None:
    """Contract: invalid credentials return 401 + {code,message,detail}."""
