"""FastAPI app factory для backend-слоя панели управления."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cryptotechnolog.config import get_logger, get_settings
from cryptotechnolog.core import EnhancedEventBus
from cryptotechnolog.runtime_identity import get_runtime_version

from .api.router import create_dashboard_router
from .runtime import DashboardRuntime, create_dashboard_runtime

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)

_DASHBOARD_ALLOWED_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
)


def _create_dashboard_event_bus() -> EnhancedEventBus:
    """Собрать локальный event bus для standalone dashboard backend."""
    settings = get_settings()
    return EnhancedEventBus(
        enable_persistence=False,
        redis_url=None,
        rate_limit=settings.event_bus_rate_limit,
        backpressure_strategy=settings.event_bus_backpressure_strategy,
    )


def create_dashboard_app(runtime: DashboardRuntime | None = None) -> FastAPI:
    """Создать отдельное FastAPI-приложение для read-only dashboard foundation."""
    dashboard_runtime = runtime or create_dashboard_runtime(event_bus=_create_dashboard_event_bus())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await dashboard_runtime.start()
        try:
            yield
        finally:
            await dashboard_runtime.stop()

    app = FastAPI(
        title="CRYPTOTEHNOLOG Dashboard API",
        version=get_runtime_version(),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(_DASHBOARD_ALLOWED_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "PUT", "OPTIONS"],
        allow_headers=["*"],
    )
    app.state.dashboard_runtime = dashboard_runtime
    app.include_router(
        create_dashboard_router(
            dashboard_runtime.overview_facade,
            runtime_diagnostics_supplier=dashboard_runtime.get_runtime_diagnostics,
        )
    )

    logger.info("Создано dashboard FastAPI приложение")
    return app
