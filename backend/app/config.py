"""
RealityCheck application configuration.
Loaded from environment variables / .env file.
"""
from __future__ import annotations

import secrets
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_debug: bool = True

    # Database
    database_url: str = "sqlite:///./realitycheck.db"

    # MCP bearer token — required for /mcp endpoint authentication
    mcp_bearer_token: str = ""

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Default timezone (IANA name)
    default_timezone: str = "UTC"

    @field_validator("mcp_bearer_token")
    @classmethod
    def token_must_not_be_placeholder(cls, v: str) -> str:
        if v in ("", "change-me-generate-a-real-token"):
            # Generate a safe default so the server always starts;
            # warn loudly in the app startup log.
            return secrets.token_urlsafe(32)
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
