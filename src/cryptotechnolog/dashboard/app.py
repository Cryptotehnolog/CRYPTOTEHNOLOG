"""FastAPI app factory для backend-слоя панели управления."""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from cryptotechnolog.bootstrap import (
    ProductionRuntime,
    build_production_runtime,
)
from cryptotechnolog.config import (
    get_logger,
    get_settings,
)
from cryptotechnolog.config import (
    persist_settings_updates as update_settings,
)
from cryptotechnolog.core import EnhancedEventBus
from cryptotechnolog.runtime_identity import get_runtime_version

from .api.router import create_dashboard_router
from .dto.settings import LiveFeedPolicySettingsDTO
from .runtime import DashboardRuntime, create_dashboard_runtime

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)

_FRONTEND_DIST_DIR = Path(__file__).resolve().parents[3] / "dashboard-frontend" / "dist"

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
    startup_task: asyncio.Task[None] | None = None


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

    def _ensure_canonical_runtime_startup_task() -> None:
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is None:
            return
        if canonical_runtime_holder.startup_task is not None:
            if canonical_runtime_holder.startup_task.done():
                canonical_runtime_holder.startup_task = None
            else:
                return
        if getattr(canonical_runtime, "is_started", False):
            return

        async def _run_startup() -> None:
            try:
                await canonical_runtime.startup(defer_post_start_bringup=True)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Canonical production runtime startup завершился ошибкой в background")

        canonical_runtime_holder.startup_task = asyncio.create_task(
            _run_startup(),
            name="dashboard_canonical_runtime_startup",
        )

    def _get_runtime_diagnostics() -> dict[str, Any]:
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is not None:
            return canonical_runtime.get_runtime_diagnostics()
        return dashboard_runtime.get_runtime_diagnostics()

    def _get_bybit_connector_projection() -> dict[str, Any]:
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is None:
            diagnostics = dashboard_runtime.get_runtime_diagnostics()
            return dict(diagnostics.get("bybit_market_data_connector", {}))
        if hasattr(canonical_runtime, "get_bybit_connector_screen_projection"):
            return canonical_runtime.get_bybit_connector_screen_projection()
        diagnostics = canonical_runtime.get_runtime_diagnostics()
        return dict(diagnostics.get("bybit_market_data_connector", {}))

    def _get_bybit_spot_connector_projection() -> dict[str, Any]:
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is None:
            diagnostics = dashboard_runtime.get_runtime_diagnostics()
            return dict(diagnostics.get("bybit_spot_market_data_connector", {}))
        if hasattr(canonical_runtime, "get_bybit_spot_connector_screen_projection"):
            return canonical_runtime.get_bybit_spot_connector_screen_projection()
        diagnostics = canonical_runtime.get_runtime_diagnostics()
        return dict(diagnostics.get("bybit_spot_market_data_connector", {}))

    async def _get_bybit_spot_v2_compact_diagnostics() -> dict[str, Any]:
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is None:
            return {
                "generation": "v2",
                "status": "disabled",
                "observed_at": None,
                "symbols": [],
                "transport": {
                    "transport_status": "disabled",
                    "subscription_alive": False,
                    "transport_rtt_ms": None,
                    "last_message_at": None,
                    "messages_received_count": 0,
                },
                "ingest": {
                    "trade_seen": False,
                    "orderbook_seen": False,
                    "best_bid": None,
                    "best_ask": None,
                    "trade_ingest_count": 0,
                    "orderbook_ingest_count": 0,
                },
                "persistence": {
                    "requested_window_started_at": None,
                    "count_window_started_at": None,
                    "window_ended_at": None,
                    "window_contract": "rolling_24h_exact",
                    "split_contract": "archive_origin_plus_live_residual_inside_same_window",
                    "live_trade_count_24h": 0,
                    "archive_trade_count_24h": 0,
                    "persisted_trade_count_24h": 0,
                    "first_persisted_trade_at": None,
                    "last_persisted_trade_at": None,
                    "earliest_trade_at": None,
                    "latest_trade_at": None,
                    "symbols_covered": [],
                    "coverage_status": "empty",
                },
                "recovery": {
                    "status": "disabled",
                    "stage": "disabled",
                    "reason": None,
                    "last_progress_checkpoint": None,
                },
                "reconciliation": {
                    "scope_verdict": "unavailable",
                    "scope_reason": "runtime_unavailable",
                    "symbols": [],
                },
            }
        return await canonical_runtime.get_bybit_spot_v2_compact_diagnostics()

    def _get_bybit_spot_runtime_status() -> dict[str, Any]:
        _ensure_canonical_runtime_startup_task()
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is None:
            return {
                "generation": "v2",
                "desired_running": False,
                "transport_status": "disabled",
                "subscription_alive": False,
                "transport_rtt_ms": None,
                "last_message_at": None,
                "messages_received_count": 0,
                "trade_ingest_count": 0,
                "orderbook_ingest_count": 0,
                "trade_seen": False,
                "orderbook_seen": False,
                "best_bid": None,
                "best_ask": None,
                "recovery_status": "disabled",
                "recovery_stage": "disabled",
                "recovery_reason": None,
                "scope_mode": "universe",
                "total_instruments_discovered": None,
                "selected_symbols_count": 0,
                "symbols": (),
            }
        return canonical_runtime.get_bybit_spot_runtime_status()

    async def _get_bybit_spot_product_snapshot() -> dict[str, Any]:
        _ensure_canonical_runtime_startup_task()
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is None:
            return {
                "generation": "v2",
                "desired_running": False,
                "transport_status": "disabled",
                "subscription_alive": False,
                "transport_rtt_ms": None,
                "last_message_at": None,
                "messages_received_count": 0,
                "trade_ingest_count": 0,
                "orderbook_ingest_count": 0,
                "trade_seen": False,
                "orderbook_seen": False,
                "best_bid": None,
                "best_ask": None,
                "persisted_trade_count": 0,
                "last_persisted_trade_at": None,
                "last_persisted_trade_symbol": None,
                "recovery_status": "disabled",
                "recovery_stage": "disabled",
                "recovery_reason": None,
                "scope_mode": "universe",
                "total_instruments_discovered": None,
                "selected_symbols_count": 0,
                "symbols": (),
                "observed_at": None,
                "persistence_24h": {
                    "live_trade_count_24h": 0,
                    "archive_trade_count_24h": 0,
                    "persisted_trade_count_24h": 0,
                    "first_persisted_trade_at": None,
                    "last_persisted_trade_at": None,
                    "coverage_status": "unavailable",
                },
                "instrument_rows": [],
            }
        startup_task = canonical_runtime_holder.startup_task
        if startup_task is not None and not startup_task.done():
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(startup_task), timeout=15.0)
        with contextlib.suppress(asyncio.TimeoutError):
            await canonical_runtime.await_post_start_bringup(timeout_seconds=15.0)
        try:
            return await canonical_runtime.get_bybit_spot_product_snapshot()
        except Exception:
            logger.exception("Bybit spot product snapshot endpoint failed")
            raise

    async def _set_bybit_connector_enabled(enabled: bool) -> dict[str, Any]:
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is None:
            raise RuntimeError("Canonical backend runtime ещё не поднят")
        return await canonical_runtime.set_bybit_market_data_connector_enabled(enabled)

    async def _set_bybit_spot_connector_enabled(enabled: bool) -> dict[str, Any]:
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is None:
            raise RuntimeError("Canonical backend runtime ещё не поднят")
        return await canonical_runtime.set_bybit_spot_market_data_connector_enabled(enabled)

    async def _set_bybit_spot_runtime_state(desired_running: bool) -> dict[str, Any]:
        _ensure_canonical_runtime_startup_task()
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is None:
            raise RuntimeError("Canonical backend runtime ещё не поднят")
        return await canonical_runtime.set_bybit_spot_runtime_desired_running(desired_running)

    async def _update_live_feed_policy(
        payload: LiveFeedPolicySettingsDTO,
    ) -> LiveFeedPolicySettingsDTO:
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is None:
            settings = update_settings(payload.to_settings_update())
            return LiveFeedPolicySettingsDTO.from_settings(settings)
        settings = await canonical_runtime.update_live_feed_policy_settings(
            payload.to_settings_update()
        )
        return LiveFeedPolicySettingsDTO.from_settings(settings)

    async def _get_live_feed_policy() -> LiveFeedPolicySettingsDTO:
        canonical_runtime = canonical_runtime_holder.runtime
        if canonical_runtime is None:
            return LiveFeedPolicySettingsDTO.from_settings(get_settings())
        return LiveFeedPolicySettingsDTO.from_settings(canonical_runtime.settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        owned_production_runtime: ProductionRuntime | None = None
        if canonical_runtime_holder.runtime is None and enable_canonical_runtime:
            owned_production_runtime = await build_production_runtime()
            canonical_runtime_holder.runtime = owned_production_runtime
            _app.state.production_runtime = owned_production_runtime
            _ensure_canonical_runtime_startup_task()
        elif canonical_runtime_holder.runtime is not None:
            _ensure_canonical_runtime_startup_task()
        await dashboard_runtime.start()
        try:
            yield
        finally:
            await dashboard_runtime.stop()
            if canonical_runtime_holder.startup_task is not None:
                canonical_runtime_holder.startup_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await canonical_runtime_holder.startup_task
                canonical_runtime_holder.startup_task = None
            if owned_production_runtime is not None:
                await owned_production_runtime.shutdown()
                canonical_runtime_holder.runtime = None
                _app.state.production_runtime = None
            elif canonical_runtime_holder.runtime is not None and getattr(
                canonical_runtime_holder.runtime,
                "is_started",
                False,
            ):
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
            bybit_connector_projection_supplier=_get_bybit_connector_projection,
            bybit_spot_connector_projection_supplier=_get_bybit_spot_connector_projection,
            bybit_spot_v2_compact_diagnostics_supplier=_get_bybit_spot_v2_compact_diagnostics,
            bybit_spot_runtime_status_supplier=_get_bybit_spot_runtime_status,
            bybit_spot_product_snapshot_supplier=_get_bybit_spot_product_snapshot,
            live_feed_policy_get_handler=_get_live_feed_policy,
            live_feed_policy_update_handler=_update_live_feed_policy,
            bybit_connector_toggle_handler=_set_bybit_connector_enabled
            if production_runtime is not None or enable_canonical_runtime
            else None,
            bybit_spot_connector_toggle_handler=_set_bybit_spot_connector_enabled
            if production_runtime is not None or enable_canonical_runtime
            else None,
            bybit_spot_runtime_state_handler=_set_bybit_spot_runtime_state
            if production_runtime is not None or enable_canonical_runtime
            else None,
        )
    )

    if _FRONTEND_DIST_DIR.exists():
        assets_dir = _FRONTEND_DIST_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="dashboard_assets")

        index_file = _FRONTEND_DIST_DIR / "index.html"

        @app.get("/", include_in_schema=False)
        async def _serve_dashboard_root() -> FileResponse:
            return FileResponse(index_file)

        @app.get("/terminal/{path:path}", include_in_schema=False)
        async def _serve_dashboard_terminal(path: str) -> FileResponse:
            return FileResponse(index_file)

    logger.info("Создано dashboard FastAPI приложение")
    return app
