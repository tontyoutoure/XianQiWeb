"""M1-UT-01 password hashing contract tests (RED phase)."""

from __future__ import annotations

from app.core.password import hash_password
from app.core.password import verify_password


def test_m1_ut_01_hash_is_not_plaintext() -> None:
    """Input: plaintext abc -> Output: hash value differs from plaintext."""
    hashed = hash_password("abc")
    assert hashed != "abc"


def test_m1_ut_01_verify_matches_original_password() -> None:
    """Input: correct plaintext with its hash -> Output: verify True."""
    plaintext = "abc"
    hashed = hash_password(plaintext)
    assert verify_password(plaintext, hashed) is True


def test_m1_ut_01_verify_rejects_wrong_password() -> None:
    """Input: wrong plaintext with hash -> Output: verify False."""
    hashed = hash_password("abc")
    assert verify_password("wrong", hashed) is False


def test_m1_ut_01_empty_password_is_supported_in_mvp() -> None:
    """Input: empty password -> Output: can hash and verify as True."""
    hashed = hash_password("")
    assert verify_password("", hashed) is True
