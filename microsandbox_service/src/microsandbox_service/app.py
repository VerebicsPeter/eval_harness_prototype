"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from microsandbox_service.config import Settings, get_settings
from microsandbox_service.registry import SandboxFactory, SandboxRegistry
from microsandbox_service.routes import router

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    sandbox_factory: SandboxFactory | None = None,
) -> FastAPI:
    """Build the FastAPI app.

    Args:
        settings: Overrides the env-derived settings (useful for tests).
        sandbox_factory: Overrides how sandboxes are created (inject a fake in tests).
    """
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        registry = SandboxRegistry(settings, sandbox_factory=sandbox_factory)
        app.state.settings = settings
        app.state.registry = registry

        if not settings.api_key:
            logger.warning(
                "MSB_SERVICE_API_KEY is not set; the service is UNAUTHENTICATED. "
                "Set it before exposing this service on a network."
            )

        registry.start_reaper()
        try:
            yield
        finally:
            await registry.stop_reaper()
            await registry.remove_all()

    app = FastAPI(
        title="microsandbox service",
        description="A light HTTP wrapper around the microsandbox SDK for networked training loops.",
        version="0.0.1",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app
