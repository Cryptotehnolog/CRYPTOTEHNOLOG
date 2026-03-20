from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cryptotechnolog import __version__
from cryptotechnolog.bootstrap import (
    PHASE5_RISK_PATH,
    ProductionBootstrapError,
    ProductionBootstrapPolicy,
    build_production_runtime,
    start_production_runtime,
)
from cryptotechnolog.config.settings import Settings
from cryptotechnolog.core.event import SystemEventType
from cryptotechnolog.core.health import HealthStatus, SystemHealth
import cryptotechnolog.core.listeners.base as listeners_base_module
from cryptotechnolog.core.listeners.base import ListenerRegistry
from cryptotechnolog.core.listeners.risk import RiskListener
from cryptotechnolog.core.system_controller import (
    ShutdownPhase,
    ShutdownResult,
    StartupPhase,
    StartupResult,
)
from cryptotechnolog.market_data import MarketDataTimeframe, OHLCVBarContract
from cryptotechnolog.market_data.events import (
    BarCompletedPayload,
    MarketDataEventType,
    build_market_data_event,
)


def make_settings() -> Settings:
    """Собрать settings для bootstrap-тестов без внешних подключений."""
    return Settings(
        environment="test",
        debug=True,
        base_r_percent=0.01,
        max_r_per_trade=0.02,
        max_portfolio_r=0.05,
        risk_max_total_exposure_usd=25000.0,
        max_position_size=5000.0,
        risk_starting_equity=10000.0,
        event_bus_redis_url="redis://localhost:6379",
    )


def make_completed_bar(index: int = 0) -> OHLCVBarContract:
    """Собрать completed bar для узких runtime wiring тестов."""
    open_time = datetime(2026, 3, 20, 12, index, tzinfo=UTC)
    close_time = datetime(2026, 3, 20, 12, index + 1, tzinfo=UTC)
    return OHLCVBarContract(
        symbol="BTC/USDT",
        exchange="bybit",
        timeframe=MarketDataTimeframe.M1,
        open_time=open_time,
        close_time=close_time,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("100"),
        close=Decimal("109"),
        volume=Decimal("15"),
        bid_volume=Decimal("5"),
        ask_volume=Decimal("10"),
        trades_count=3,
        is_closed=True,
    )


def _fake_shutdown_with_component_stop(
    runtime,
    *,
    components_stopped: list[str],
):
    async def _shutdown(*, force: bool = False) -> ShutdownResult:
        _ = force
        if runtime.intelligence_runtime.is_started:
            await runtime.intelligence_runtime.stop()
        if runtime.shared_analysis_runtime.is_started:
            await runtime.shared_analysis_runtime.stop()
        if runtime.market_data_runtime.is_started:
            await runtime.market_data_runtime.stop()
        return ShutdownResult(
            success=True,
            duration_ms=3,
            phase_reached=ShutdownPhase.COMPLETED,
            components_stopped=components_stopped,
        )

    return _shutdown


@pytest.fixture
def isolated_global_listener_registry():
    """Изолировать глобальный ListenerRegistry для bootstrap-тестов."""
    original_registry = getattr(listeners_base_module, "_listener_registry", None)
    listeners_base_module._listener_registry = ListenerRegistry()
    try:
        yield listeners_base_module._listener_registry
    finally:
        listeners_base_module._listener_registry = original_registry


class TestProductionBootstrap:
    """Тесты composition root Шага 2."""

    @pytest.mark.asyncio
    async def test_builds_official_production_composition_root(self) -> None:
        """Bootstrap должен собирать единый production runtime."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        assert runtime.identity.bootstrap_module == "cryptotechnolog.bootstrap"
        assert runtime.identity.version == __version__
        assert runtime.identity.version == runtime.settings.project_version
        assert runtime.identity.active_risk_path == PHASE5_RISK_PATH
        assert runtime.identity.config_identity == runtime.settings.get_config_identity()
        assert runtime.identity.config_revision == runtime.settings.get_config_revision()
        assert runtime.event_bus.listener_registry is runtime.listener_registry
        assert runtime.event_bus.active_risk_path == PHASE5_RISK_PATH
        assert runtime.event_bus.enforce_single_risk_path is True
        assert runtime.health_checker.get_runtime_identity() == runtime.identity
        assert runtime.get_runtime_diagnostics()["composition_root_built"] is True
        assert runtime.get_runtime_diagnostics()["runtime_ready"] is False
        assert (
            runtime.get_runtime_diagnostics()["config_identity"] == runtime.identity.config_identity
        )
        assert (
            runtime.get_runtime_diagnostics()["config_revision"] == runtime.identity.config_revision
        )
        assert runtime.get_runtime_diagnostics()["market_data_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["market_data_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["shared_analysis_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["shared_analysis_runtime"]["ready"] is False
        assert runtime.get_runtime_diagnostics()["intelligence_runtime"]["started"] is False
        assert runtime.get_runtime_diagnostics()["intelligence_runtime"]["ready"] is False
        controller_component = runtime.controller.get_component("event_bus")
        assert controller_component is not None
        assert controller_component is runtime.event_bus
        assert runtime.controller.get_component("phase5_risk_runtime") is runtime.risk_runtime
        assert (
            runtime.controller.get_component("phase6_market_data_runtime")
            is runtime.market_data_runtime
        )
        assert (
            runtime.controller.get_component("phase7_intelligence_runtime")
            is runtime.intelligence_runtime
        )
        assert (
            runtime.controller.get_component("c7r_shared_analysis_runtime")
            is runtime.shared_analysis_runtime
        )
        assert SystemEventType.BAR_COMPLETED in runtime.event_bus.handlers
        assert SystemEventType.BAR_COMPLETED not in runtime.risk_runtime.risk_listener.event_types
        assert SystemEventType.RISK_BAR_COMPLETED in runtime.risk_runtime.risk_listener.event_types

        listener_names = [listener.name for listener in runtime.listener_registry.all_listeners]
        assert "risk_check_listener" not in listener_names
        assert "risk_engine_listener" not in listener_names

    @pytest.mark.asyncio
    async def test_runtime_startup_validates_started_runtime_contract(self) -> None:
        """startup() должен проверять обязательный runtime contract composition root."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.controller.startup = AsyncMock(  # type: ignore[method-assign]
            return_value=StartupResult(
                success=True,
                duration_ms=5,
                phase_reached=StartupPhase.READY,
                components_initialized=["database", "redis", "event_bus", "phase5_risk_runtime"],
                components_failed=[],
            )
        )
        runtime.health_checker.check_system = AsyncMock(  # type: ignore[method-assign]
            return_value=SystemHealth(
                overall_status=HealthStatus.HEALTHY,
                components={},
                runtime_identity=runtime.identity,
            )
        )
        runtime.db_manager._connected = True
        runtime.db_manager._pool = Mock()
        runtime.redis_manager._connected = True
        runtime.redis_manager._redis = Mock()
        runtime.event_bus.register_listener(runtime.risk_runtime.risk_listener)
        runtime.risk_runtime._listener_registered = True
        runtime.market_data_runtime._started = True
        runtime.market_data_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.shared_analysis_runtime._started = True
        runtime.shared_analysis_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
        )
        runtime.intelligence_runtime._started = True
        runtime.intelligence_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )

        result = await runtime.startup()

        assert result.phase_reached == StartupPhase.READY
        assert runtime.is_started is True
        assert runtime.last_health is not None
        diagnostics = runtime.get_runtime_diagnostics()
        assert diagnostics["runtime_started"] is True
        assert diagnostics["runtime_ready"] is True
        assert diagnostics["active_risk_path"] == PHASE5_RISK_PATH
        assert diagnostics["config_identity"] == runtime.identity.config_identity
        assert diagnostics["config_revision"] == runtime.identity.config_revision
        assert diagnostics["market_data_runtime"]["ready"] is True
        assert diagnostics["shared_analysis_runtime"]["ready"] is True
        assert diagnostics["intelligence_runtime"]["ready"] is True

    @pytest.mark.asyncio
    async def test_runtime_startup_fail_fast_exposes_block_reason_in_diagnostics(self) -> None:
        """Fail-fast path должен быть виден в readiness и runtime diagnostics."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.controller.startup = AsyncMock(  # type: ignore[method-assign]
            return_value=StartupResult(
                success=True,
                duration_ms=5,
                phase_reached=StartupPhase.READY,
                components_initialized=["database", "redis", "event_bus", "phase5_risk_runtime"],
                components_failed=[],
            )
        )

        with pytest.raises(ProductionBootstrapError, match="подключение к БД"):
            await runtime.startup()

        diagnostics = runtime.get_runtime_diagnostics()
        assert diagnostics["runtime_started"] is False
        assert diagnostics["runtime_ready"] is False
        assert diagnostics["startup_state"] == "failed"
        assert "подключение к БД" in diagnostics["failure_reason"]

        health = await runtime.health_checker.check_system()
        assert health.readiness_status == "not_ready"
        assert any(reason.startswith("startup_failed:") for reason in health.readiness_reasons)

    @pytest.mark.asyncio
    async def test_runtime_startup_exposes_market_data_not_ready_as_degraded(self) -> None:
        """Production startup не должен маскировать неготовый market data слой как ready."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.controller.startup = AsyncMock(  # type: ignore[method-assign]
            return_value=StartupResult(
                success=True,
                duration_ms=5,
                phase_reached=StartupPhase.READY,
                components_initialized=[
                    "database",
                    "redis",
                    "event_bus",
                    "phase5_risk_runtime",
                    "phase6_market_data_runtime",
                    "c7r_shared_analysis_runtime",
                    "phase7_intelligence_runtime",
                ],
                components_failed=[],
            )
        )
        runtime.health_checker.check_system = AsyncMock(  # type: ignore[method-assign]
            return_value=SystemHealth(
                overall_status=HealthStatus.HEALTHY,
                components={},
                runtime_identity=runtime.identity,
                diagnostics={
                    "market_data_runtime": runtime.market_data_runtime.get_runtime_diagnostics()
                },
            )
        )
        runtime.db_manager._connected = True
        runtime.db_manager._pool = Mock()
        runtime.redis_manager._connected = True
        runtime.redis_manager._redis = Mock()
        runtime.event_bus.register_listener(runtime.risk_runtime.risk_listener)
        runtime.risk_runtime._listener_registered = True
        runtime.market_data_runtime._started = True
        runtime.market_data_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="not_ready",
            readiness_reasons=("no_raw_universe_snapshot", "no_universe_quality_assessment"),
            degraded_reasons=(),
        )
        runtime.shared_analysis_runtime._started = True
        runtime.shared_analysis_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="warming",
            readiness_reasons=("derived_inputs_warming",),
        )
        runtime.intelligence_runtime._started = True
        runtime.intelligence_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=False,
            lifecycle_state="warming",
            readiness_reasons=("derya_history_warming",),
            degraded_reasons=(),
        )

        await runtime.startup()

        diagnostics = runtime.get_runtime_diagnostics()
        assert diagnostics["runtime_started"] is True
        assert diagnostics["runtime_ready"] is False
        assert diagnostics["startup_state"] == "degraded"
        assert "phase6_market_data:not_ready" in diagnostics["degraded_reasons"]
        assert "c7r_shared_analysis:not_ready" in diagnostics["degraded_reasons"]
        assert "phase7_intelligence:not_ready" in diagnostics["degraded_reasons"]
        assert diagnostics["market_data_runtime"]["ready"] is False
        assert diagnostics["shared_analysis_runtime"]["ready"] is False
        assert diagnostics["intelligence_runtime"]["ready"] is False

    @pytest.mark.asyncio
    async def test_runtime_startup_exposes_degraded_readiness_when_health_is_degraded(self) -> None:
        """Деградированный startup не должен выглядеть как fully ready."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.controller.startup = AsyncMock(  # type: ignore[method-assign]
            return_value=StartupResult(
                success=True,
                duration_ms=5,
                phase_reached=StartupPhase.READY,
                components_initialized=["database", "redis", "event_bus", "phase5_risk_runtime"],
                components_failed=[],
            )
        )
        runtime.health_checker.check_system = AsyncMock(  # type: ignore[method-assign]
            return_value=SystemHealth(
                overall_status=HealthStatus.DEGRADED,
                components={
                    "metrics": Mock(
                        component="metrics",
                        status=HealthStatus.DEGRADED,
                    )
                },
                runtime_identity=runtime.identity,
            )
        )
        runtime.db_manager._connected = True
        runtime.db_manager._pool = Mock()
        runtime.redis_manager._connected = True
        runtime.redis_manager._redis = Mock()
        runtime.event_bus.register_listener(runtime.risk_runtime.risk_listener)
        runtime.risk_runtime._listener_registered = True

        await runtime.startup()

        diagnostics = runtime.get_runtime_diagnostics()
        assert diagnostics["runtime_started"] is True
        assert diagnostics["runtime_ready"] is False
        assert diagnostics["startup_state"] == "degraded"
        assert "metrics:degraded" in diagnostics["degraded_reasons"]

    @pytest.mark.asyncio
    async def test_runtime_shutdown_updates_runtime_diagnostics(self) -> None:
        """Shutdown lifecycle должен отражаться в operator-facing diagnostics."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.controller.startup = AsyncMock(  # type: ignore[method-assign]
            return_value=StartupResult(
                success=True,
                duration_ms=5,
                phase_reached=StartupPhase.READY,
                components_initialized=["database", "redis", "event_bus", "phase5_risk_runtime"],
                components_failed=[],
            )
        )
        runtime.controller.shutdown = AsyncMock(  # type: ignore[method-assign]
            side_effect=_fake_shutdown_with_component_stop(
                runtime,
                components_stopped=["phase5_risk_runtime", "event_bus"],
            )
        )
        runtime.health_checker.check_system = AsyncMock(  # type: ignore[method-assign]
            return_value=SystemHealth(
                overall_status=HealthStatus.HEALTHY,
                components={},
                runtime_identity=runtime.identity,
            )
        )
        runtime.db_manager._connected = True
        runtime.db_manager._pool = Mock()
        runtime.redis_manager._connected = True
        runtime.redis_manager._redis = Mock()
        runtime.event_bus.register_listener(runtime.risk_runtime.risk_listener)
        runtime.risk_runtime._listener_registered = True
        runtime.market_data_runtime._started = True
        runtime.market_data_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )
        runtime.shared_analysis_runtime._started = True
        runtime.shared_analysis_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
        )
        runtime.intelligence_runtime._started = True
        runtime.intelligence_runtime._refresh_diagnostics(  # type: ignore[attr-defined]
            ready=True,
            lifecycle_state="ready",
            readiness_reasons=(),
            degraded_reasons=(),
        )

        await runtime.startup()
        shutdown_result = await runtime.shutdown()

        diagnostics = runtime.get_runtime_diagnostics()
        assert shutdown_result.phase_reached == ShutdownPhase.COMPLETED
        assert runtime.is_started is False
        assert diagnostics["runtime_started"] is False
        assert diagnostics["runtime_ready"] is False
        assert diagnostics["shutdown_state"] == ShutdownPhase.COMPLETED.value
        assert "runtime_stopped" in diagnostics["degraded_reasons"]
        assert diagnostics["shared_analysis_runtime"]["started"] is False
        assert diagnostics["shared_analysis_runtime"]["ready"] is False
        assert diagnostics["shared_analysis_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["shared_analysis_runtime"]["readiness_reasons"] == ["runtime_stopped"]
        assert diagnostics["intelligence_runtime"]["started"] is False
        assert diagnostics["intelligence_runtime"]["ready"] is False
        assert diagnostics["intelligence_runtime"]["lifecycle_state"] == "stopped"
        assert diagnostics["intelligence_runtime"]["readiness_reasons"] == ["runtime_stopped"]
        assert diagnostics["intelligence_runtime"]["degraded_reasons"] == []

    @pytest.mark.asyncio
    async def test_start_production_runtime_preserves_fail_fast_truth_after_cleanup(self) -> None:
        """Entry helper не должен маскировать startup failure как обычный stopped runtime."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )
        runtime.controller.startup = AsyncMock(  # type: ignore[method-assign]
            return_value=StartupResult(
                success=True,
                duration_ms=5,
                phase_reached=StartupPhase.READY,
                components_initialized=["database", "redis", "event_bus", "phase5_risk_runtime"],
                components_failed=[],
            )
        )
        runtime.controller.shutdown = AsyncMock(  # type: ignore[method-assign]
            return_value=ShutdownResult(
                success=True,
                duration_ms=3,
                phase_reached=ShutdownPhase.COMPLETED,
                components_stopped=[],
            )
        )
        runtime.health_checker.check_system = AsyncMock(  # type: ignore[method-assign]
            return_value=SystemHealth(
                overall_status=HealthStatus.UNKNOWN,
                components={},
                runtime_identity=runtime.identity,
            )
        )

        with (
            patch(
                "cryptotechnolog.bootstrap.build_production_runtime",
                new=AsyncMock(return_value=runtime),
            ),
            pytest.raises(ProductionBootstrapError, match="подключение к БД"),
        ):
            await start_production_runtime(
                settings=make_settings(),
                policy=ProductionBootstrapPolicy(
                    test_mode=True,
                    enable_event_bus_persistence=False,
                    enable_risk_persistence=False,
                    include_legacy_risk_listener=False,
                ),
            )

        runtime.controller.shutdown.assert_awaited_once_with(force=True)
        diagnostics = runtime.get_runtime_diagnostics()
        assert diagnostics["runtime_started"] is False
        assert diagnostics["runtime_ready"] is False
        assert diagnostics["startup_state"] == "failed"
        assert diagnostics["shutdown_state"] == ShutdownPhase.COMPLETED.value
        assert "подключение к БД" in diagnostics["failure_reason"]
        assert diagnostics["degraded_reasons"] == ["startup_failed_cleanup"]

    @pytest.mark.asyncio
    async def test_enable_listeners_rejects_legacy_global_registry_after_startup(
        self,
        isolated_global_listener_registry: ListenerRegistry,
    ) -> None:
        """После startup production runtime не должен принимать global legacy registry."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.event_bus.register_listener(runtime.risk_runtime.risk_listener)
        runtime.risk_runtime._listener_registered = True
        runtime.event_bus.seal_risk_path_policy()

        isolated_global_listener_registry.register(RiskListener())

        with pytest.raises(ValueError):
            runtime.event_bus.enable_listeners()

    @pytest.mark.asyncio
    async def test_direct_registry_replacement_rejects_mixed_risk_registry_after_startup(
        self,
    ) -> None:
        """После startup production runtime не должен принимать mixed registry."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.event_bus.register_listener(runtime.risk_runtime.risk_listener)
        runtime.risk_runtime._listener_registered = True
        runtime.event_bus.seal_risk_path_policy()

        mixed_registry = ListenerRegistry()
        mixed_registry.register(runtime.risk_runtime.risk_listener)
        mixed_registry.register(RiskListener())

        with pytest.raises(ValueError):
            runtime.event_bus.listener_registry = mixed_registry

    @pytest.mark.asyncio
    async def test_production_runtime_rejects_legacy_risk_listener_policy(self) -> None:
        """Production root не должен позволять legacy risk path."""
        with pytest.raises(ProductionBootstrapError):
            await build_production_runtime(
                settings=make_settings(),
                policy=ProductionBootstrapPolicy(
                    test_mode=True,
                    enable_event_bus_persistence=False,
                    enable_risk_persistence=False,
                    include_legacy_risk_listener=True,
                ),
            )

    @pytest.mark.asyncio
    async def test_event_bus_blocks_double_risk_wiring_in_production_runtime(self) -> None:
        """После подключения Phase 5 path legacy listener не должен регистрироваться."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        await runtime.risk_runtime.start()

        with pytest.raises(ValueError):
            runtime.event_bus.register_listener(RiskListener())

        await runtime.risk_runtime.stop()

    @pytest.mark.asyncio
    async def test_bar_completed_wiring_marks_intelligence_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """BAR_COMPLETED wiring должен честно переводить intelligence runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.intelligence_runtime._started = True
        runtime.intelligence_runtime.ingest_bar_completed_payload = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("derya_ingest_failure")
        )
        handler = runtime.event_bus.handlers[SystemEventType.BAR_COMPLETED][0]
        event = build_market_data_event(
            event_type=MarketDataEventType.BAR_COMPLETED,
            payload=BarCompletedPayload.from_contract(make_completed_bar()),
        )

        with pytest.raises(RuntimeError, match="derya_ingest_failure"):
            await handler(event)

        diagnostics = runtime.intelligence_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert diagnostics["last_failure_reason"] == "bar_ingest_failed:derya_ingest_failure"
        assert diagnostics["degraded_reasons"] == ["bar_ingest_failed:derya_ingest_failure"]

    @pytest.mark.asyncio
    async def test_bar_completed_wiring_marks_shared_analysis_runtime_degraded_on_ingest_failure(
        self,
    ) -> None:
        """BAR_COMPLETED wiring должен честно переводить shared analysis runtime в degraded."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        runtime.shared_analysis_runtime._started = True
        runtime.shared_analysis_runtime.ingest_bar_completed_payload = Mock(  # type: ignore[method-assign]
            side_effect=RuntimeError("analysis_ingest_failure")
        )
        handler = runtime.event_bus.handlers[SystemEventType.BAR_COMPLETED][1]
        event = build_market_data_event(
            event_type=MarketDataEventType.BAR_COMPLETED,
            payload=BarCompletedPayload.from_contract(make_completed_bar()),
        )

        with pytest.raises(
            RuntimeError, match="shared_analysis_bar_ingest_failed:analysis_ingest_failure"
        ):
            await handler(event)

        diagnostics = runtime.shared_analysis_runtime.get_runtime_diagnostics()
        assert diagnostics["started"] is True
        assert diagnostics["ready"] is False
        assert diagnostics["lifecycle_state"] == "degraded"
        assert diagnostics["last_failure_reason"] == "bar_ingest_failed:analysis_ingest_failure"
        assert diagnostics["degraded_reasons"] == ["bar_ingest_failed:analysis_ingest_failure"]

    @pytest.mark.asyncio
    async def test_composition_root_keeps_market_data_bar_boundary_separate_from_risk_listener(
        self,
    ) -> None:
        """Composition root не должен смешивать raw BAR_COMPLETED с risk-специфичным bar path."""
        runtime = await build_production_runtime(
            settings=make_settings(),
            policy=ProductionBootstrapPolicy(
                test_mode=True,
                enable_event_bus_persistence=False,
                enable_risk_persistence=False,
                include_legacy_risk_listener=False,
            ),
        )

        assert SystemEventType.BAR_COMPLETED in runtime.event_bus.handlers
        assert SystemEventType.BAR_COMPLETED not in runtime.risk_runtime.risk_listener.event_types
        assert SystemEventType.RISK_BAR_COMPLETED in runtime.risk_runtime.risk_listener.event_types
