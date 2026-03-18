"""FastAPI app factory для backend-слоя панели управления."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from cryptotechnolog.config import get_logger
from cryptotechnolog.core import get_event_bus

from .api.router import create_dashboard_router
from .runtime import DashboardRuntime, create_dashboard_runtime

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)


def create_dashboard_app(runtime: DashboardRuntime | None = None) -> FastAPI:
    """Создать отдельное FastAPI-приложение для read-only dashboard foundation."""
    dashboard_runtime = runtime or create_dashboard_runtime(event_bus=get_event_bus())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await dashboard_runtime.start()
        try:
            yield
        finally:
            await dashboard_runtime.stop()

    app = FastAPI(
        title="CRYPTOTEHNOLOG Dashboard API",
        version="1.4.0",
        lifespan=lifespan,
    )
    app.state.dashboard_runtime = dashboard_runtime
    app.include_router(create_dashboard_router(dashboard_runtime.overview_facade))

    logger.info("Создано dashboard FastAPI приложение")
    return app
