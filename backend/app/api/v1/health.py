"""Health check endpoint and backend status reporting."""

from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.security import verify_session_token

router = APIRouter()

_START_TIME = time.time()


class HealthResponse(BaseModel):
    """Schema for GET /api/v1/health endpoint."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        default="healthy",
        description="Overall health status of backend sidecar",
    )
    version: str = Field(
        description="Application version string",
    )
    environment: str = Field(
        description="Runtime environment ('development', 'production')",
    )
    uptime_seconds: float = Field(
        ge=0.0,
        description="Uptime duration in seconds since process startup",
    )
    active_sessions: int = Field(
        default=1,
        ge=0,
        description="Number of active Tauri frontend windows connected",
    )


@router.get(
    "",
    response_model=HealthResponse,
    summary="Health check probe",
    description="Accessible on loopback without session token to allow Tauri launcher handshake.",
)
async def get_health() -> HealthResponse:
    """Return current sidecar health status."""
    uptime = time.time() - _START_TIME
    return HealthResponse(
        status="healthy",
        version=settings.version,
        environment=settings.environment,
        uptime_seconds=round(uptime, 2),
        active_sessions=1,
    )


@router.get(
    "/authenticated",
    response_model=HealthResponse,
    summary="Authenticated health probe",
    description="Requires valid X-AIC-Session-Token header to verify authentication subsystem.",
)
async def get_authenticated_health(
    _token: str = Depends(verify_session_token),
) -> HealthResponse:
    """Return health status verifying that session token validation succeeds."""
    uptime = time.time() - _START_TIME
    return HealthResponse(
        status="healthy",
        version=settings.version,
        environment=settings.environment,
        uptime_seconds=round(uptime, 2),
        active_sessions=1,
    )
