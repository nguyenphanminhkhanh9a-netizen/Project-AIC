"""Application settings and configuration management for Project AIC Sidecar.

Implements ADR-007 (Desktop-first with Tauri shell and Python sidecar).
Strictly binds to 127.0.0.1 (loopback) and issues an ephemeral session token.
"""

from __future__ import annotations

import secrets

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment or defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Project AIC Sidecar"
    version: str = "0.5.0"
    environment: str = "development"

    # Network Security: Strictly loopback only (ADR-007)
    host: str = Field(
        default="127.0.0.1",
        description="Loopback bind host. Never bind 0.0.0.0.",
    )
    port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="TCP port for loopback REST/WebSocket server",
    )

    # Session authentication: Ephemeral token per app lifecycle
    session_token: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Ephemeral session token passed from Tauri launcher or generated at startup",
    )

    # CORS Origins: Restricted strictly to Tauri local webview
    cors_origins: list[str] = [
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "https://tauri.localhost",
    ]

    @field_validator("host")
    @classmethod
    def validate_loopback_only(cls, value: str) -> str:
        """Enforce strict loopback binding rule per ADR-007."""
        allowed_loopbacks = {"127.0.0.1", "localhost", "::1"}
        if value not in allowed_loopbacks:
            raise ValueError(
                f"Security violation: Binding to '{value}' is prohibited. "
                "AIC Sidecar must bind strictly to loopback (127.0.0.1) to prevent LAN exposure."
            )
        return value


# Global singleton settings instance
settings = Settings()
