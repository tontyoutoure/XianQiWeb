"""M1-UT-05 username normalization/length contract tests."""

from __future__ import annotations

import pytest

from app.core.username import UsernameValidationError
from app.core.username import normalize_and_validate_username


def test_m1_ut_05_username_trim_and_nfc_equivalence() -> None:
    """Input: " e\u0301 " and "\u00e9" -> Output: same canonical username."""
    assert normalize_and_validate_username(" e\u0301 ") == "\u00e9"
    assert normalize_and_validate_username("\u00e9") == "\u00e9"


def test_m1_ut_05_username_over_10_graphemes_is_rejected() -> None:
    """Input: username with 11 graphemes -> Output: validation error."""
    with pytest.raises(UsernameValidationError):
        normalize_and_validate_username("abcdefghijk")


def test_m1_ut_05_username_within_10_graphemes_is_accepted() -> None:
    """Input: username with 10 graphemes -> Output: normalized username."""
    assert normalize_and_validate_username("abcdefghij") == "abcdefghij"


def test_m1_ut_05_blank_after_trim_is_rejected() -> None:
    """Input: blank username -> Output: validation error."""
    with pytest.raises(UsernameValidationError):
        normalize_and_validate_username("   ")
