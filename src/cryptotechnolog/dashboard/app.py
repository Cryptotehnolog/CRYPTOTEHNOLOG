"""FastAPI app factory для backend-слоя панели управления."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cryptotechnolog.bootstrap import (
    ProductionRuntime,
    start_production_runtime,
)
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


@dataclass(slots=True)
class _CanonicalRuntimeHolder:
    """Mutable holder for canonical runtime diagnostics supplier wiring."""

    runtime: ProductionRuntime | None = None


def _create_dashboard_event_bus() -> EnhancedEventBus:
    """Собрать локальный event bus для standalone dashboard backend."""
    settings = get_settings()
    return EnhancedEventBus(
        enable_persistence=False,
        redis_url=None,
        rate_limit=settings.event_bus_rate_limit,
        backpressure_strategy=settings.event_bus_backpressure_strategy,
    )


def create_dashboard_app(
    runtime: DashboardRuntime | None = None,
    *,
    production_runtime: ProductionRuntime | None = None,
    enable_canonical_runtime: bool = False,
) -> FastAPI:
    """Создать отдельное FastAPI-приложение для read-only dashboard foundation."""
    dashboard_runtime = runtime or create_dashboard_runtime(event_bus=_create_dashboard_event_bus())
    canonical_runtime_holder = _CanonicalRuntimeHolder(runtime=production_runtime)

    def _get_runtime_diagnostics() -> dict[str, Any]:
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is not None:
            return canonical_runtime.get_runtime_diagnostics()
        return dashboard_runtime.get_runtime_diagnostics()

    async def _set_bybit_connector_enabled(enabled: bool) -> dict[str, Any]:
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is None:
            raise RuntimeError("Canonical backend runtime ещё не поднят")
        return await canonical_runtime.set_bybit_market_data_connector_enabled(enabled)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        owned_production_runtime: ProductionRuntime | None = None
        started_production_runtime = False
        if canonical_runtime_holder.runtime is None and enable_canonical_runtime:
            owned_production_runtime = await start_production_runtime()
            canonical_runtime_holder.runtime = owned_production_runtime
            _app.state.production_runtime = owned_production_runtime
        elif canonical_runtime_holder.runtime is not None and not getattr(
            canonical_runtime_holder.runtime,
            "is_started",
            True,
        ):
            await canonical_runtime_holder.runtime.startup()
            started_production_runtime = True
        await dashboard_runtime.start()
        try:
            yield
        finally:
            await dashboard_runtime.stop()
            if owned_production_runtime is not None:
                await owned_production_runtime.shutdown()
                canonical_runtime_holder.runtime = None
                _app.state.production_runtime = None
            elif started_production_runtime and canonical_runtime_holder.runtime is not None:
                await canonical_runtime_holder.runtime.shutdown()

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
    app.state.production_runtime = production_runtime
    app.include_router(
        create_dashboard_router(
            dashboard_runtime.overview_facade,
            runtime_diagnostics_supplier=_get_runtime_diagnostics,
            bybit_connector_toggle_handler=_set_bybit_connector_enabled
            if production_runtime is not None or enable_canonical_runtime
            else None,
        )
    )

    logger.info("Создано dashboard FastAPI приложение")
    return app
