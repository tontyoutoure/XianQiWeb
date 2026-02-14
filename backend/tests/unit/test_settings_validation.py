"""M1-UT-06 configuration guard contract test."""

from __future__ import annotations


def test_m1_ut_06_refresh_interval_less_than_access_expire(app_not_ready: None) -> None:
    """Contract: refresh interval must be smaller than access token expiry.

    Expected input:
    - settings where refresh interval >= access expiry

    Expected output:
    - settings validation fails and app startup is blocked
    """
