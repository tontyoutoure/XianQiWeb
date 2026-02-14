"""M1 WebSocket auth contract test skeletons."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("app_not_ready")


def test_m1_ws_01_ws_connects_with_valid_access_token() -> None:
    """Contract: WS with valid access token should connect successfully."""


def test_m1_ws_02_ws_rejects_invalid_token_with_4401() -> None:
    """Contract: WS auth failure closes with code 4401 and UNAUTHORIZED reason."""


def test_m1_ws_03_ws_rejects_expired_token_with_4401() -> None:
    """Contract: expired access token cannot establish WS connection."""
