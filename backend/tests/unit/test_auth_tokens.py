"""M1-UT-02/03 token contract tests."""

from __future__ import annotations


def test_m1_ut_02_access_jwt_contains_sub_and_exp(app_not_ready: None) -> None:
    """Contract: access token is JWT with sub/exp.

    Expected input:
    - create access token for user_id=1
    - validate in valid window and after expiry

    Expected output:
    - valid token resolves sub=1
    - expired token returns token-expired error
    """


def test_m1_ut_03_refresh_rotate_revokes_old_token(app_not_ready: None) -> None:
    """Contract: refresh rotation revokes old token immediately.

    Expected input:
    - create refresh token
    - perform one rotation

    Expected output:
    - old token is revoked and unusable
    - new token is returned and usable
    """
