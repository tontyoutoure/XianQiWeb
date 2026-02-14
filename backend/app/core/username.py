"""Username normalization and validation helpers for auth."""

from __future__ import annotations

import unicodedata

import regex

MIN_USERNAME_GRAPHEMES = 1
MAX_USERNAME_GRAPHEMES = 10
_GRAPHEME_PATTERN = regex.compile(r"\X")


class UsernameValidationError(ValueError):
    """Raised when a username violates auth validation rules."""


def normalize_username(raw_username: str) -> str:
    """Trim and normalize username to NFC form."""
    return unicodedata.normalize("NFC", raw_username.strip())


def count_graphemes(value: str) -> int:
    """Count user-visible characters using grapheme clusters."""
    return len(_GRAPHEME_PATTERN.findall(value))


def validate_username_length(username: str) -> None:
    """Validate username grapheme length in [1, 10]."""
    grapheme_count = count_graphemes(username)
    if grapheme_count < MIN_USERNAME_GRAPHEMES or grapheme_count > MAX_USERNAME_GRAPHEMES:
        raise UsernameValidationError(
            f"username length must be {MIN_USERNAME_GRAPHEMES}-{MAX_USERNAME_GRAPHEMES} graphemes"
        )


def normalize_and_validate_username(raw_username: str) -> str:
    """Apply trim + NFC and validate length constraints."""
    normalized = normalize_username(raw_username)
    validate_username_length(normalized)
    return normalized
