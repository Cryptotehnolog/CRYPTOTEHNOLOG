from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from cryptotechnolog.bootstrap import (
    PHASE5_RISK_PATH,
    ProductionBootstrapPolicy,
    build_production_runtime,
)
from cryptotechnolog.config.settings import Settings
from cryptotechnolog.core.event import SystemEventType
from cryptotechnolog.core.health import HealthStatus


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, query: str, *args: object) -> str:
        self.executed.append((query, args))
        normalized = " ".join(query.split())
        if "UPDATE state_machine_states" in normalized:
            return "UPDATE 1"
        if normalized in {"BEGIN", "COMMIT", "ROLLBACK"}:
            return normalized
        return "OK"


class _FakePool:
    def __init__(self) -> None:
        self.connection = _FakeConnection()

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


class _FakeCounter:
    def inc(self) -> None:
        return None


class _FakeGauge:
    def set(self, _value: object) -> None:
        return None


def _make_settings() -> Settings:
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


def _install_fake_database(runtime, fake_pool: _FakePool) -> None:
    async def db_connect() -> None:
        runtime.db_manager._connected = True
        runtime.db_manager._pool = fake_pool

    async def db_disconnect() -> None:
        runtime.db_manager._connected = False
        runtime.db_manager._pool = None

    async def db_health_check() -> dict[str, object]:
        return {
            "status": "healthy" if runtime.db_manager.is_connected else "unhealthy",
            "connected": runtime.db_manager.is_connected,
            "pool_size": 1,
            "pool_max_size": 1,
        }

    async def db_fetchrow(query: str, *_args: object):
        normalized = " ".join(query.split())
        if "SELECT current_state, version FROM state_machine_states" in normalized:
            return {
                "current_state": "boot",
                "version": 0,
            }
        return None

    async def db_execute(query: str, *args: object) -> str:
        return await fake_pool.connection.execute(query, *args)

    runtime.db_manager.connect = db_connect  # type: ignore[method-assign]
    runtime.db_manager.disconnect = db_disconnect  # type: ignore[method-assign]
    runtime.db_manager.close = db_disconnect  # type: ignore[method-assign]
    runtime.db_manager.health_check = db_health_check  # type: ignore[method-assign]
    runtime.db_manager.fetchrow = db_fetchrow  # type: ignore[method-assign]
    runtime.db_manager.execute = db_execute  # type: ignore[method-assign]


def _install_fake_redis(runtime) -> None:
    async def redis_ping() -> None:
        runtime.redis_manager._connected = True
        runtime.redis_manager._redis = object()

    async def redis_disconnect() -> None:
        runtime.redis_manager._connected = False
        runtime.redis_manager._redis = None

    async def redis_health_check() -> dict[str, object]:
        return {
            "status": "healthy" if runtime.redis_manager.is_connected else "unhealthy",
            "connected": runtime.redis_manager.is_connected,
            "max_connections": 1,
        }

    runtime.redis_manager.ping = redis_ping  # type: ignore[method-assign]
    runtime.redis_manager.disconnect = redis_disconnect  # type: ignore[method-assign]
    runtime.redis_manager.close = redis_disconnect  # type: ignore[method-assign]
    runtime.redis_manager.health_check = redis_health_check  # type: ignore[method-assign]


def _install_fake_metrics(runtime) -> None:
    runtime.metrics_collector.get_counter = lambda _name: _FakeCounter()  # type: ignore[method-assign]
    runtime.metrics_collector.get_gauge = lambda _name: _FakeGauge()  # type: ignore[method-assign]


def _capture_lifecycle_events(runtime) -> list[str]:
    lifecycle_events: list[str] = []

    def capture_lifecycle_event(event) -> None:
        lifecycle_events.append(event.event_type)

    runtime.event_bus.on(SystemEventType.SYSTEM_BOOT, capture_lifecycle_event)
    runtime.event_bus.on(SystemEventType.SYSTEM_READY, capture_lifecycle_event)
    return lifecycle_events


@pytest.mark.asyncio
@pytest.mark.integration
async def test_production_composition_root_builds_and_starts_real_runtime_contract() -> None:
    """Composition root должен реально собрать и поднять production runtime contract."""
    runtime = await build_production_runtime(
        settings=_make_settings(),
        policy=ProductionBootstrapPolicy(
            test_mode=True,
            enable_event_bus_persistence=False,
            enable_risk_persistence=False,
        ),
    )

    fake_pool = _FakePool()
    lifecycle_events = _capture_lifecycle_events(runtime)
    _install_fake_database(runtime, fake_pool)
    _install_fake_redis(runtime)
    _install_fake_metrics(runtime)

    await runtime.startup()

    diagnostics = runtime.get_runtime_diagnostics()
    health = await runtime.health_checker.check_system()

    assert runtime.is_started is True
    assert runtime.controller.is_running is True
    assert runtime.identity.active_risk_path == PHASE5_RISK_PATH
    assert runtime.event_bus.active_risk_path == PHASE5_RISK_PATH
    assert runtime.event_bus.listener_registry is runtime.listener_registry
    assert runtime.risk_runtime.is_started is True
    assert diagnostics["runtime_started"] is True
    assert diagnostics["runtime_ready"] is False
    assert diagnostics["config_identity"] == runtime.identity.config_identity
    assert diagnostics["config_revision"] == runtime.identity.config_revision
    assert "phase6_market_data:not_ready" in diagnostics["degraded_reasons"]
    assert health.overall_status == HealthStatus.HEALTHY
    assert health.readiness_status == "not_ready"
    assert health.runtime_identity == runtime.identity
    assert health.diagnostics["active_risk_path"] == PHASE5_RISK_PATH
    assert health.diagnostics["config_identity"] == runtime.identity.config_identity
    assert health.diagnostics["config_revision"] == runtime.identity.config_revision
    assert "market_data_runtime_not_ready" in health.readiness_reasons
    assert SystemEventType.SYSTEM_BOOT in lifecycle_events
    assert SystemEventType.SYSTEM_READY in lifecycle_events

    await runtime.shutdown(force=True)
