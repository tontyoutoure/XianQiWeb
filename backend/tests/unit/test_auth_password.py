"""M1-UT-01 password hashing contract tests."""

from __future__ import annotations


def test_m1_ut_01_password_hash_and_verify(app_not_ready: None) -> None:
    """Contract: bcrypt hash/verify works and empty password is allowed in MVP.

    Expected input:
    - plaintext password examples: "abc", ""

    Expected output:
    - hashed value is not plaintext
    - verify succeeds for original plaintext
    - verify fails for wrong plaintext
    """
