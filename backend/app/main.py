"""Main FastAPI application entrypoint for Project AIC Sidecar.

Implements ADR-007: Managed sidecar lifecycle, loopback networking, and REST routing.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1_router
from app.core.config import settings

logger = logging.getLogger("project_aic.backend")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan context manager for startup and graceful shutdown."""
    # Startup lifecycle
    logger.info("Project AIC Sidecar starting on %s:%d", settings.host, settings.port)
    logger.info("Session token initialized: %s***", settings.session_token[:6])
    yield
    # Shutdown lifecycle
    logger.info("Project AIC Sidecar shutting down gracefully...")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    application = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="Local FastAPI managed sidecar backend for Project AIC",
        lifespan=lifespan,
    )

    # CORS configuration: Restricted strictly to local Tauri origins
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Register API v1 router
    application.include_router(api_v1_router)

    return application


app = create_app()
