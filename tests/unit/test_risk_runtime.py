from __future__ import annotations

from unittest.mock import patch

import pytest

from cryptotechnolog.config.settings import Settings
from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.core.event import Event, SystemEventType
import cryptotechnolog.core.listeners.base as listeners_base_module
from cryptotechnolog.core.listeners.base import ListenerRegistry
from cryptotechnolog.core.system_controller import SystemController
from cryptotechnolog.risk.engine import RiskEngineEventType
from cryptotechnolog.risk.persistence import RiskPersistenceRepository
from cryptotechnolog.risk.runtime import create_risk_runtime


class _FakePool:
    """Минимальный stub pool для wiring optional repository."""


@pytest.fixture
def isolated_listener_registry():
    """Изолировать глобальный ListenerRegistry для runtime-тестов."""
    original_registry = getattr(listeners_base_module, "_listener_registry", None)
    listeners_base_module._listener_registry = ListenerRegistry()
    try:
        yield
    finally:
        listeners_base_module._listener_registry = original_registry


def make_settings() -> Settings:
    """Собрать локальный settings instance для runtime-тестов."""
    return Settings(
        environment="test",
        debug=True,
        base_r_percent=0.01,
        max_r_per_trade=0.02,
        max_portfolio_r=0.05,
        risk_max_total_exposure_usd=25000.0,
        max_position_size=5000.0,
        risk_starting_equity=10000.0,
        feature_funding_rate_arbitrage=True,
    )


class TestRiskRuntime:
    """Integration-тесты runtime/bootstrap integration нового Risk Engine."""

    @pytest.mark.asyncio
    async def test_builds_phase5_runtime_without_persistence(
        self, isolated_listener_registry
    ) -> None:
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        controller = SystemController(event_bus=bus, test_mode=True)

        runtime = await create_risk_runtime(
            event_bus=bus,
            controller=controller,
            settings=make_settings(),
            enable_persistence=False,
        )

        assert runtime.persistence_repository is None
        assert runtime.config.funding_feature_enabled is True
        assert controller.get_component("phase5_risk_engine") is runtime.risk_engine
        assert controller.get_component("phase5_risk_listener") is runtime.risk_listener
        assert controller.get_component("phase5_funding_manager") is runtime.funding_manager

    @pytest.mark.asyncio
    async def test_wires_optional_repository_when_pool_is_available(
        self,
        isolated_listener_registry,
    ) -> None:
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)

        runtime = await create_risk_runtime(
            event_bus=bus,
            settings=make_settings(),
            db_pool=_FakePool(),
            enable_persistence=True,
        )

        assert isinstance(runtime.persistence_repository, RiskPersistenceRepository)

    @pytest.mark.asyncio
    async def test_start_registers_only_phase5_listener_without_legacy_risk_mix(
        self,
        isolated_listener_registry,
    ) -> None:
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        runtime = await create_risk_runtime(
            event_bus=bus,
            settings=make_settings(),
            enable_persistence=False,
        )
        published_events: list[Event] = []
        bus.on(RiskEngineEventType.RISK_POSITION_REGISTERED, published_events.append)

        await runtime.start()

        assert bus.listener_registry is not None
        listener_names = [listener.name for listener in bus.listener_registry.all_listeners]
        assert "risk_engine_listener" in listener_names
        assert "risk_check_listener" not in listener_names

        await bus.publish(
            Event.new(
                SystemEventType.ORDER_FILLED,
                "test_runtime",
                {
                    "position_id": "pos-runtime-1",
                    "symbol": "BTC/USDT",
                    "side": "buy",
                    "avg_price": "100",
                    "stop_loss": "95",
                    "filled_qty": "2",
                    "risk_capital_usd": "10000",
                },
            )
        )
        await bus.drain(timeout=5.0)

        assert runtime.risk_ledger.get_position_record("pos-runtime-1").symbol == "BTC/USDT"
        assert len(published_events) == 1
        assert published_events[0].event_type == RiskEngineEventType.RISK_POSITION_REGISTERED

        await runtime.stop()

    @pytest.mark.asyncio
    async def test_repository_can_be_wired_via_project_database_infrastructure(
        self,
        isolated_listener_registry,
    ) -> None:
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        fake_pool = _FakePool()

        with patch("cryptotechnolog.risk.runtime.get_db_pool", return_value=fake_pool):
            runtime = await create_risk_runtime(
                event_bus=bus,
                settings=make_settings(),
                enable_persistence=True,
            )

        assert isinstance(runtime.persistence_repository, RiskPersistenceRepository)
