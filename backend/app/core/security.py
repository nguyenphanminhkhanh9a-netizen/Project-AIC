"""Authentication and security dependencies for local API endpoints."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def verify_session_token(
    x_aic_session_token: Annotated[str | None, Header(alias="X-AIC-Session-Token")] = None,
) -> str:
    """Verify ephemeral session token provided in request headers.

    Uses constant-time comparison to prevent timing attacks.
    """
    if not x_aic_session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "missing_session_token",
                "message": "Header 'X-AIC-Session-Token' is required for internal API calls.",
            },
        )

    # Constant time comparison
    if not secrets.compare_digest(x_aic_session_token, settings.session_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_session_token",
                "message": "Invalid session token provided.",
            },
        )

    return x_aic_session_token
