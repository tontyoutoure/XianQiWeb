"""Application settings for backend runtime and tests."""

from __future__ import annotations

from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Typed settings loaded from environment variables or explicit kwargs."""

    xqweb_app_env: str = "dev"
    xqweb_app_host: str = "127.0.0.1"
    xqweb_app_port: int = Field(default=8000, ge=1)

    xqweb_jwt_secret: str = Field(min_length=1)
    xqweb_access_token_expire_seconds: int = Field(default=3600, ge=1)
    xqweb_access_token_refresh_interval_seconds: int = Field(default=1800, ge=1)
    xqweb_refresh_token_expire_seconds: int = Field(default=7776000, ge=1)

    xqweb_sqlite_path: str = "xqweb.db"
    xqweb_cors_allow_origins: str = "*"
    xqweb_room_count: int = Field(default=8, ge=1)

    @model_validator(mode="after")
    def validate_refresh_interval(self) -> "Settings":
        """Ensure proactive refresh interval is smaller than access expiry."""
        if (
            self.xqweb_access_token_refresh_interval_seconds
            >= self.xqweb_access_token_expire_seconds
        ):
            raise ValueError(
                "XQWEB_ACCESS_TOKEN_REFRESH_INTERVAL_SECONDS must be less than "
                "XQWEB_ACCESS_TOKEN_EXPIRE_SECONDS"
            )
        return self


def load_settings() -> Settings:
    """Load settings from process environment."""
    return Settings()
