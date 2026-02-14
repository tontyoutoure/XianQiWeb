"""M1 API auth contract tests (API-01 in RED phase)."""

from __future__ import annotations

import pytest

from fastapi.testclient import TestClient


def test_m1_api_01_register_returns_auth_session(register_payload: dict[str, str]) -> None:
    """Contract: POST /api/auth/register returns access+refresh+user."""
    from app.main import app

    client = TestClient(app)
    response = client.post("/api/auth/register", json=register_payload)

    assert response.status_code == 200
    payload = response.json()
    assert {"access_token", "refresh_token", "expires_in", "refresh_expires_in", "user"} <= set(
        payload
    )
    assert payload["user"]["username"] == "Alice"


@pytest.mark.usefixtures("app_not_ready")
def test_m1_api_02_register_rejects_duplicate_username_with_nfc_equivalence() -> None:
    """Contract: equivalent normalized usernames conflict with 409."""


@pytest.mark.usefixtures("app_not_ready")
def test_m1_api_03_username_is_case_sensitive() -> None:
    """Contract: Tom and tom can both register as different users."""


@pytest.mark.usefixtures("app_not_ready")
def test_m1_api_04_empty_password_is_allowed_in_mvp() -> None:
    """Contract: register/login accepts empty password in MVP."""


@pytest.mark.usefixtures("app_not_ready")
def test_m1_api_05_login_success_returns_new_token_pair() -> None:
    """Contract: POST /api/auth/login returns a fresh token pair."""


@pytest.mark.usefixtures("app_not_ready")
def test_m1_api_06_login_failure_returns_401_with_unified_error_shape() -> None:
    """Contract: invalid credentials return 401 + {code,message,detail}."""


@pytest.mark.usefixtures("app_not_ready")
def test_m1_api_07_me_requires_valid_bearer_token() -> None:
    """Contract: GET /api/auth/me returns current user for valid access token."""


@pytest.mark.usefixtures("app_not_ready")
def test_m1_api_08_me_rejects_missing_or_invalid_token() -> None:
    """Contract: GET /api/auth/me returns 401 without valid access token."""


@pytest.mark.usefixtures("app_not_ready")
def test_m1_api_09_refresh_rotates_refresh_token() -> None:
    """Contract: POST /api/auth/refresh returns new pair and revokes old refresh."""


@pytest.mark.usefixtures("app_not_ready")
def test_m1_api_10_refresh_rejects_revoked_expired_or_random_token() -> None:
    """Contract: invalid refresh token returns 401."""


@pytest.mark.usefixtures("app_not_ready")
def test_m1_api_11_logout_revokes_specified_refresh_token_idempotently() -> None:
    """Contract: POST /api/auth/logout is idempotent and revokes target refresh token."""


@pytest.mark.usefixtures("app_not_ready")
def test_m1_api_12_login_kicks_old_session_refresh_but_old_access_still_works_until_expiry() -> None:
    """Contract: new login revokes previous refresh; old access valid until exp."""
