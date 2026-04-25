from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from cryptotechnolog.config.settings import Settings
from cryptotechnolog.live_feed.bybit_spot_module import (
    BybitSpotModule,
    BybitSpotModuleDeps,
    _build_product_snapshot_contract_flags,
    _is_product_snapshot_publishable,
    _resolve_product_snapshot_reason,
    _resolve_exact_query_profile,
    _spot_scope_truth_is_final_for_settings,
    query_exact_trade_count_snapshots_by_symbol_uncached,
)


def _make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "debug": True,
        "base_r_percent": 0.01,
        "max_r_per_trade": 0.02,
        "max_portfolio_r": 0.05,
        "risk_max_total_exposure_usd": 25000.0,
        "risk_kelly_fraction_cap": 0.25,
        "risk_min_order_notional_usd": 20.0,
        "redis_url": "redis://localhost:6379/0",
        "database_url": "postgresql://user:pass@localhost:5432/test_db",
        "jwt_secret_key": "test-secret-key-for-jwt-minimum-32-chars",
        "secret_key": "test-secret-key-minimum-32-chars!!!",
        "bybit_spot_market_data_connector_enabled": True,
        "bybit_spot_universe_min_trade_count_24h": 20000,
        "bybit_spot_quote_asset_filter": "usdt_usdc",
    }
    values.update(overrides)
    return Settings.model_validate(values)


def _make_deps() -> BybitSpotModuleDeps:
    return BybitSpotModuleDeps(
        build_connector_screen_projection=lambda **_: {
            "enabled": True,
            "lifecycle_state": "waiting_for_scope",
            "recovery_status": "waiting_for_scope",
            "derived_trade_count_backfill_status": None,
        },
        resolve_runtime_generation=lambda **_: "v2",
        build_runtime_signature=lambda **_: ("spot", True),
        build_trade_ledger_query_service=lambda **_: object(),
        reuse_scope_if_possible=lambda **_: None,
        resolve_canonical_scope_async=AsyncMock(),
        build_runtime_apply_truth=lambda **_: object(),
        build_selected_connector=lambda **_: None,
        build_transport_connector=lambda **kwargs: SimpleNamespace(
            symbols=tuple(kwargs["resolved_scope"].symbols),
            run=AsyncMock(),
            stop=AsyncMock(),
            get_transport_diagnostics=lambda: {
                "started": False,
                "transport_status": "idle",
                "symbols": tuple(kwargs["resolved_scope"].symbols),
            },
        ),
        build_recovery_orchestrator=lambda **kwargs: SimpleNamespace(
            symbols=tuple(kwargs["resolved_scope"].symbols),
            run=AsyncMock(),
            stop=AsyncMock(),
            get_recovery_diagnostics=lambda: {
                "started": False,
                "status": "waiting_for_scope",
                "target_symbols": tuple(kwargs["resolved_scope"].symbols),
            },
        ),
        resolve_disabled_toggle_scope=lambda **_: SimpleNamespace(
            symbols=(),
            truth=SimpleNamespace(
                selected_symbols=(),
                coarse_selected_symbols=(),
                trade_count_filter_minimum=0,
                instruments_passed_final_filter=0,
                discovery_signature=("spot",),
            ),
        ),
        resolve_monitoring_symbols=lambda **kwargs: tuple(kwargs["resolved_scope"].truth.coarse_selected_symbols),
        resolve_min_trade_count_24h=lambda **_: 20000,
        resolve_spot_primary_lifecycle_state=lambda **_: "connected_live",
        join_timeout_seconds=0.1,
        query_exact_trade_counts_uncached=AsyncMock(return_value={}),
        query_exact_trade_count_snapshots_uncached=AsyncMock(return_value={}),
        update_settings=lambda _updates: _make_settings(bybit_spot_market_data_connector_enabled=False),
    )


def _make_runtime() -> SimpleNamespace:
    return SimpleNamespace(
        settings=_make_settings(),
        bybit_spot_market_data_connector=None,
        bybit_spot_market_data_connector_task=None,
        bybit_spot_market_data_scope_summary=None,
        bybit_spot_market_data_apply_truth=None,
        bybit_spot_v2_transport=None,
        bybit_spot_v2_transport_task=None,
        bybit_spot_v2_recovery=None,
        bybit_spot_v2_recovery_task=None,
        _BYBIT_SPOT_INCOMPLETE_COVERAGE_RETENTION_SECONDS=60,
        _BYBIT_SPOT_FINAL_SCOPE_REFRESH_SECONDS=30,
        _BYBIT_SPOT_STABLE_FINAL_SCOPE_REFRESH_SECONDS=90,
        _BYBIT_SPOT_RETENTION_MAINTENANCE_SECONDS=3600,
        _started=True,
        market_data_runtime=SimpleNamespace(is_started=True, start=AsyncMock()),
        db_manager=object(),
        _track_background_connector_shutdown=lambda **_: None,
        _refresh_runtime_health_after_bybit_toggle=AsyncMock(),
        get_runtime_diagnostics=lambda: {"ok": True},
        get_bybit_spot_v2_transport_diagnostics=lambda: {"transport_status": "idle"},
        get_bybit_spot_v2_recovery_diagnostics=lambda: {"status": "waiting_for_scope"},
    )


def test_module_projection_keeps_waiting_for_scope_without_transport() -> None:
    runtime = _make_runtime()
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())

    projection = module.get_connector_screen_projection()

    assert projection["lifecycle_state"] == "waiting_for_scope"
    assert projection["recovery_status"] == "waiting_for_scope"


def test_module_private_publishable_contract_accepts_connected_live() -> None:
    assert _is_product_snapshot_publishable(
        {
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "subscription_alive": True,
            "selected_symbols_count": 1,
        }
    )


def test_module_private_final_scope_truth_contract_requires_matching_trade_counts() -> None:
    settings = _make_settings()
    truth = SimpleNamespace(
        discovery_signature=(
            "spot",
            "https://api-testnet.bybit.com" if settings.bybit_testnet else "https://api.bybit.com",
            float(settings.bybit_spot_universe_min_quote_volume_24h_usd),
            str(settings.bybit_spot_quote_asset_filter),
        ),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
        coarse_selected_symbols=("BTC/USDT",),
        selected_symbols=("BTC/USDT",),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 20000),),
        selected_trade_count_24h_is_final=True,
    )

    assert _spot_scope_truth_is_final_for_settings(settings=settings, truth=truth)


def test_module_private_final_scope_truth_contract_accepts_exact_empty_result() -> None:
    settings = _make_settings()
    truth = SimpleNamespace(
        discovery_signature=(
            "spot",
            "https://api-testnet.bybit.com" if settings.bybit_testnet else "https://api.bybit.com",
            float(settings.bybit_spot_universe_min_quote_volume_24h_usd),
            str(settings.bybit_spot_quote_asset_filter),
        ),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=0,
        coarse_selected_symbols=("BTC/USDT", "ETH/USDT"),
        selected_symbols=(),
        selected_trade_count_24h_by_symbol=(),
        selected_trade_count_24h_is_final=True,
        selected_trade_count_24h_empty_scope_confirmed=True,
    )

    assert _spot_scope_truth_is_final_for_settings(settings=settings, truth=truth)


def test_module_private_final_scope_truth_contract_rejects_unconfirmed_empty_result() -> None:
    settings = _make_settings()
    truth = SimpleNamespace(
        discovery_signature=(
            "spot",
            "https://api-testnet.bybit.com" if settings.bybit_testnet else "https://api.bybit.com",
            float(settings.bybit_spot_universe_min_quote_volume_24h_usd),
            str(settings.bybit_spot_quote_asset_filter),
        ),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=0,
        coarse_selected_symbols=("BTC/USDT", "ETH/USDT"),
        selected_symbols=(),
        selected_trade_count_24h_by_symbol=(),
        selected_trade_count_24h_is_final=True,
    )

    assert not _spot_scope_truth_is_final_for_settings(settings=settings, truth=truth)


def test_module_private_final_scope_truth_contract_rejects_incomplete_reuse() -> None:
    settings = _make_settings()
    truth = SimpleNamespace(
        discovery_signature=(
            "spot",
            "https://api-testnet.bybit.com" if settings.bybit_testnet else "https://api.bybit.com",
            float(settings.bybit_spot_universe_min_quote_volume_24h_usd),
            str(settings.bybit_spot_quote_asset_filter),
        ),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
        coarse_selected_symbols=("BTC/USDT",),
        selected_symbols=("BTC/USDT",),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        selected_trade_count_24h_is_final=False,
    )

    assert not _spot_scope_truth_is_final_for_settings(settings=settings, truth=truth)


def test_module_runtime_status_uses_coarse_screen_scope_while_trade_truth_is_incomplete() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        scope_mode="selected",
        total_instruments_discovered=631,
        instruments_passed_coarse_filter=307,
        instruments_passed_final_filter=0,
        selected_symbols=(),
        coarse_selected_symbols=tuple(f"SYM{i}/USDT" for i in range(307)),
    )
    runtime.get_bybit_spot_v2_transport_diagnostics = lambda: {
        "transport_status": "connected",
        "subscription_alive": True,
        "symbols": tuple(f"SYM{i}/USDT" for i in range(307)),
        "trade_ingest_count": 1,
        "orderbook_ingest_count": 1,
        "trade_seen": True,
        "orderbook_seen": True,
    }
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {"status": "running"}
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())

    status = module.get_runtime_status()

    assert status["volume_filtered_symbols_count"] == 307
    assert status["filtered_symbols_count"] == 307
    assert status["selected_symbols_count"] == 307
    assert status["symbols"] == tuple(f"SYM{i}/USDT" for i in range(307))
    assert status["monitoring_symbols_count"] == 307
    assert status["screen_scope_reason"] == "resolved_scope_pending_exact"
    assert status["contract_flags"] == {
        "trade_truth_incomplete": True,
        "strict_published_scope_empty": True,
        "coarse_scope_nonempty": True,
        "screen_scope_nonempty": True,
        "empty_screen_scope_with_live_coarse_universe": False,
    }


@pytest.mark.asyncio
async def test_exact_trade_snapshot_query_chunks_large_scope_without_single_full_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []

    async def fake_query(self, *, symbols, observed_at, window_hours=24):  # type: ignore[no-untyped-def]
        calls.append(("query", tuple(symbols)))
        return {
            str(symbol): SimpleNamespace(
                normalized_symbol=str(symbol),
                live_trade_count_24h=1,
                archive_trade_count_24h=2,
                persisted_trade_count_24h=3,
                coverage_status="hybrid",
            )
            for symbol in symbols
        }

    monkeypatch.setattr(
        "cryptotechnolog.live_feed.bybit_spot_module.BybitSpotV2PersistedQueryService.query_rolling_trade_count_snapshots",
        fake_query,
    )

    snapshots = await query_exact_trade_count_snapshots_by_symbol_uncached(
        db_manager=object(),
        symbols=("A", "B", "C", "D"),
        observed_at=datetime.now(tz=UTC),
        chunk_size=2,
        batch_concurrency=2,
    )

    assert tuple(calls) == (("query", ("A", "B")), ("query", ("C", "D")))
    assert tuple(snapshots.keys()) == ("A", "B", "C", "D")


@pytest.mark.asyncio
async def test_exact_trade_snapshot_query_falls_back_to_chunked_mode_after_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []

    async def fake_query(self, *, symbols, observed_at, window_hours=24):  # type: ignore[no-untyped-def]
        symbol_tuple = tuple(symbols)
        calls.append(("query", symbol_tuple))
        if len(symbol_tuple) > 2:
            raise TimeoutError
        return {
            str(symbol): SimpleNamespace(
                normalized_symbol=str(symbol),
                live_trade_count_24h=1,
                archive_trade_count_24h=0,
                persisted_trade_count_24h=1,
                coverage_status="live_only",
            )
            for symbol in symbol_tuple
        }

    monkeypatch.setattr(
        "cryptotechnolog.live_feed.bybit_spot_module.BybitSpotV2PersistedQueryService.query_rolling_trade_count_snapshots",
        fake_query,
    )

    snapshots = await query_exact_trade_count_snapshots_by_symbol_uncached(
        db_manager=object(),
        symbols=("A", "B", "C", "D"),
        observed_at=datetime.now(tz=UTC),
        chunk_size=2,
        batch_concurrency=2,
    )

    assert calls == [("query", ("A", "B")), ("query", ("C", "D"))]
    assert tuple(snapshots.keys()) == ("A", "B", "C", "D")


@pytest.mark.asyncio
async def test_module_apply_runtime_plan_resolves_strict_final_scope_before_restart() -> None:
    runtime = _make_runtime()
    runtime._started = False
    deps = _make_deps()
    module = BybitSpotModule(runtime=runtime, deps=deps)
    resolved_scope = SimpleNamespace(
        symbols=("BTC/USDT", "ETH/USDT", "USDC/USDT"),
        truth=SimpleNamespace(
            selected_symbols=("BTC/USDT",),
            coarse_selected_symbols=("BTC/USDT", "ETH/USDT", "USDC/USDT"),
            selected_quote_volume_24h_usd_by_symbol=(),
            coarse_selected_quote_volume_24h_usd_by_symbol=(),
            selected_trade_count_24h_by_symbol=(),
            trade_count_filter_minimum=20000,
            instruments_passed_final_filter=1,
            discovery_signature=("spot",),
        ),
    )
    module.resolve_final_scope = AsyncMock(return_value=resolved_scope)  # type: ignore[method-assign]

    await module.apply_runtime_plan(
        settings=runtime.settings,
        resolved_scope=resolved_scope,
        restart_required=True,
    )

    module.resolve_final_scope.assert_awaited_once()
    assert runtime.bybit_spot_market_data_scope_summary is resolved_scope.truth
    assert tuple(runtime.bybit_spot_v2_transport.symbols) == (
        "BTC/USDT",
        "ETH/USDT",
        "USDC/USDT",
    )


@pytest.mark.asyncio
async def test_module_start_runtime_blocks_on_finalized_startup_before_transport() -> None:
    runtime = _make_runtime()
    deps = _make_deps()
    module = BybitSpotModule(runtime=runtime, deps=deps)
    module.start_market_data_connector = AsyncMock()  # type: ignore[method-assign]
    module.ensure_scope_refresh_loop = Mock()  # type: ignore[method-assign]
    module.await_finalized_startup = AsyncMock()  # type: ignore[method-assign]
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        discovery_signature=("other",),
        trade_count_filter_minimum=0,
        instruments_passed_final_filter=None,
        selected_symbols=(),
        coarse_selected_symbols=("BTC/USDT",),
    )

    await module.start_runtime()

    module.await_finalized_startup.assert_awaited_once()


@pytest.mark.asyncio
async def test_module_apply_runtime_plan_restart_resolves_strict_scope_before_runtime_start() -> None:
    runtime = _make_runtime()
    deps = _make_deps()
    module = BybitSpotModule(runtime=runtime, deps=deps)
    module.stop_v2_recovery = AsyncMock()  # type: ignore[method-assign]
    module.stop_v2_transport = AsyncMock()  # type: ignore[method-assign]
    module.stop_market_data_connector = AsyncMock()  # type: ignore[method-assign]
    module.start_v2_transport = AsyncMock()  # type: ignore[method-assign]
    module.start_v2_recovery = AsyncMock()  # type: ignore[method-assign]
    resolved_scope = SimpleNamespace(
        symbols=("BTC/USDT", "ETH/USDT"),
        truth=SimpleNamespace(
            selected_symbols=(),
            coarse_selected_symbols=("BTC/USDT", "ETH/USDT"),
            selected_quote_volume_24h_usd_by_symbol=(),
            coarse_selected_quote_volume_24h_usd_by_symbol=(),
            selected_trade_count_24h_by_symbol=(),
            trade_count_filter_minimum=20000,
            instruments_passed_final_filter=None,
            discovery_signature=("other",),
        ),
    )
    module.resolve_final_scope = AsyncMock(return_value=resolved_scope)  # type: ignore[method-assign]

    await module.apply_runtime_plan(
        settings=runtime.settings,
        resolved_scope=resolved_scope,
        restart_required=True,
    )

    module.resolve_final_scope.assert_awaited_once()
    module.start_v2_recovery.assert_awaited_once()


@pytest.mark.asyncio
async def test_module_apply_runtime_plan_resolves_strict_finalization_during_live_restart() -> None:
    runtime = _make_runtime()
    deps = _make_deps()
    module = BybitSpotModule(runtime=runtime, deps=deps)
    resolved_scope = SimpleNamespace(
        symbols=("BTC/USDT",),
        truth=SimpleNamespace(
            selected_symbols=(),
            coarse_selected_symbols=("BTC/USDT",),
            selected_quote_volume_24h_usd_by_symbol=(),
            coarse_selected_quote_volume_24h_usd_by_symbol=(),
            selected_trade_count_24h_by_symbol=(),
            trade_count_filter_minimum=1,
            instruments_passed_final_filter=None,
            discovery_signature=("spot",),
        ),
    )
    resolved_final_scope = SimpleNamespace(
        symbols=("BTC/USDT",),
        truth=SimpleNamespace(
            selected_symbols=("BTC/USDT",),
            coarse_selected_symbols=("BTC/USDT",),
            selected_quote_volume_24h_usd_by_symbol=(),
            coarse_selected_quote_volume_24h_usd_by_symbol=(),
            selected_trade_count_24h_by_symbol=(("BTC/USDT", 1),),
            selected_trade_count_24h_is_final=True,
            trade_count_filter_minimum=1,
            instruments_passed_final_filter=1,
            discovery_signature=(
                "spot",
                "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
                float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
                str(runtime.settings.bybit_spot_quote_asset_filter),
            ),
        ),
    )
    module.resolve_final_scope = AsyncMock(return_value=resolved_final_scope)  # type: ignore[method-assign]
    module.schedule_exact_trade_cache_refresh = Mock()  # type: ignore[method-assign]
    module.ensure_finalized_startup_if_needed = Mock()  # type: ignore[method-assign]

    await module.apply_runtime_plan(
        settings=_make_settings(bybit_spot_universe_min_trade_count_24h=1),
        resolved_scope=resolved_scope,
        restart_required=True,
    )

    module.resolve_final_scope.assert_awaited_once()
    assert runtime.bybit_spot_market_data_scope_summary is resolved_final_scope.truth
    module.schedule_exact_trade_cache_refresh.assert_not_called()
    module.ensure_finalized_startup_if_needed.assert_not_called()


@pytest.mark.asyncio
async def test_module_apply_runtime_plan_defers_strict_finalization_on_timeout() -> None:
    runtime = _make_runtime()
    deps = _make_deps()
    module = BybitSpotModule(runtime=runtime, deps=deps)
    resolved_scope = SimpleNamespace(
        symbols=("BTC/USDT",),
        truth=SimpleNamespace(
            selected_symbols=("BTC/USDT",),
            coarse_selected_symbols=("BTC/USDT",),
            selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
            coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
            selected_trade_count_24h_by_symbol=(),
            trade_count_filter_minimum=1,
            instruments_passed_final_filter=None,
            discovery_signature=("spot",),
        ),
    )
    module.resolve_final_scope = AsyncMock(side_effect=TimeoutError())  # type: ignore[method-assign]

    await module.apply_runtime_plan(
        settings=_make_settings(bybit_spot_universe_min_trade_count_24h=1),
        resolved_scope=resolved_scope,
        restart_required=True,
    )

    assert runtime.bybit_spot_market_data_scope_summary is resolved_scope.truth
    assert tuple(runtime.bybit_spot_v2_transport.symbols) == ("BTC/USDT",)
    assert module._state.finalized_startup_retry_after is not None


@pytest.mark.asyncio
async def test_module_apply_runtime_plan_restarts_immediately_even_when_exact_cache_is_ready() -> None:
    runtime = _make_runtime()
    runtime._started = False
    deps = _make_deps()
    deps.resolve_min_trade_count_24h = lambda *, settings, **_: int(  # type: ignore[assignment]
        settings.bybit_spot_universe_min_trade_count_24h
    )
    module = BybitSpotModule(runtime=runtime, deps=deps)
    module.get_runtime_status = lambda: {"symbols": ()}  # type: ignore[method-assign]
    now = datetime.now(tz=UTC)
    module._state.exact_trade_cache_by_symbol = {
        "BTC/USDT": SimpleNamespace(persisted_trade_count_24h=1000, coverage_status="live_only"),
        "ETH/USDT": SimpleNamespace(persisted_trade_count_24h=2000, coverage_status="live_only"),
        "USDC/USDT": SimpleNamespace(persisted_trade_count_24h=50, coverage_status="live_only"),
    }
    module._state.exact_trade_cache_symbols = ("BTC/USDT", "ETH/USDT", "USDC/USDT")
    module._state.exact_trade_cache_expires_at = now + timedelta(seconds=60)
    resolved_scope = SimpleNamespace(
        symbols=("BTC/USDT", "ETH/USDT", "USDC/USDT"),
        truth=SimpleNamespace(
            selected_symbols=("BTC/USDT",),
            coarse_selected_symbols=("BTC/USDT", "ETH/USDT", "USDC/USDT"),
            selected_quote_volume_24h_usd_by_symbol=(),
            coarse_selected_quote_volume_24h_usd_by_symbol=(),
            selected_trade_count_24h_by_symbol=(("BTC/USDT", 1000),),
            trade_count_filter_minimum=1,
            instruments_passed_final_filter=None,
            discovery_signature=(
                "spot",
                "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
                float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
                str(runtime.settings.bybit_spot_quote_asset_filter),
            ),
        ),
    )

    await module.apply_runtime_plan(
        settings=_make_settings(bybit_spot_universe_min_trade_count_24h=1),
        resolved_scope=resolved_scope,
        restart_required=True,
    )

    assert runtime.bybit_spot_market_data_scope_summary is not resolved_scope.truth
    assert module._state.exact_trade_cache_by_symbol is None
    assert module._state.exact_trade_cache_symbols is None


@pytest.mark.asyncio
async def test_module_snapshot_uses_module_cache_refresh_path() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        trade_count_filter_minimum=20000,
    )
    deps = _make_deps()
    module = BybitSpotModule(runtime=runtime, deps=deps)
    module._state.product_snapshot_cache_payload = {
        "lifecycle_state": "connected_live",
        "selected_symbols_count": 1,
        "symbols": ("BTC/USDT",),
        "instrument_rows": [{"symbol": "BTC/USDT", "trade_count_24h": 25000}],
        "persistence_24h": {"persisted_trade_count_24h": 25000},
    }
    module._state.product_snapshot_cache_expires_at = datetime.now(tz=UTC) + timedelta(seconds=30)
    module.get_runtime_status = lambda: {  # type: ignore[method-assign]
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "connected_live",
        "transport_status": "connected",
        "selected_symbols_count": 1,
        "symbols": ("BTC/USDT",),
    }
    scheduled: list[tuple[str, ...]] = []
    module.schedule_exact_trade_cache_refresh = lambda **kwargs: scheduled.append(tuple(kwargs["symbols"]))  # type: ignore[method-assign]
    module.schedule_product_snapshot_refresh = lambda: None  # type: ignore[method-assign]
    module.is_final_scope_refresh_due = lambda **_: False  # type: ignore[method-assign]

    snapshot = await module.get_product_snapshot()

    assert snapshot["instrument_rows"] == [{"symbol": "BTC/USDT", "trade_count_24h": 25000}]
    assert scheduled == []


@pytest.mark.asyncio
async def test_module_snapshot_does_not_reuse_expired_cache_payload() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(),
        trade_count_filter_minimum=1000,
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.deps.resolve_min_trade_count_24h = lambda **_: 1000  # type: ignore[assignment]
    module._state.product_snapshot_cache_payload = {
        "lifecycle_state": "connected_live",
        "selected_symbols_count": 1,
        "symbols": ("BTC/USDT",),
        "observed_at": "stale",
        "instrument_rows": [{"symbol": "BTC/USDT", "trade_count_24h": 25000}],
        "persistence_24h": {"persisted_trade_count_24h": 25000},
    }
    module._state.product_snapshot_cache_expires_at = datetime.now(tz=UTC) - timedelta(seconds=1)
    module.get_runtime_status = lambda: {  # type: ignore[method-assign]
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "connected_live",
        "transport_status": "connected",
        "selected_symbols_count": 1,
        "filtered_symbols_count": 1,
        "symbols": ("BTC/USDT",),
    }
    module.is_final_scope_refresh_due = lambda **_: False  # type: ignore[method-assign]
    module.schedule_finalized_startup = lambda: None  # type: ignore[method-assign]

    snapshot = await module.get_product_snapshot()

    assert snapshot["observed_at"] != "stale"
    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": None,
        }
    ]
    assert snapshot["persistence_24h"]["coverage_status"] == "pending_recovery"


@pytest.mark.asyncio
async def test_module_product_snapshot_waits_for_inflight_finalized_startup_before_returning_pending() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
        scope_mode="selected",
        total_instruments_discovered=1,
        instruments_passed_coarse_filter=1,
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.get_runtime_status = lambda: {  # type: ignore[method-assign]
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "connected_live",
        "transport_status": "connected",
        "selected_symbols_count": 1,
        "filtered_symbols_count": 1,
        "symbols": ("BTC/USDT",),
    }
    module.is_final_scope_refresh_due = lambda **_: False  # type: ignore[method-assign]
    module.schedule_finalized_startup = lambda: None  # type: ignore[method-assign]

    ready = asyncio.Event()
    exact_snapshot = SimpleNamespace(
        live_trade_count_24h=234,
        archive_trade_count_24h=1000,
        persisted_trade_count_24h=1234,
        earliest_trade_at=None,
        latest_trade_at=None,
        coverage_status="hybrid",
    )

    async def finalized() -> None:
        await ready.wait()
        await asyncio.sleep(0)
        module._state.exact_trade_cache_by_symbol = {"BTC/USDT": exact_snapshot}
        module._state.exact_trade_cache_symbols = ("BTC/USDT",)
        module._state.exact_trade_cache_expires_at = datetime.now(tz=UTC) + timedelta(seconds=10)

    async def fake_fast_payload(*, now, runtime_status):  # type: ignore[no-untyped-def]
        assert module._state.exact_trade_cache_by_symbol is not None
        return {
            **runtime_status,
            "observed_at": now.isoformat(),
            "persistence_24h": {
                "live_trade_count_24h": 234,
                "archive_trade_count_24h": 1000,
                "persisted_trade_count_24h": 1234,
                "first_persisted_trade_at": None,
                "last_persisted_trade_at": None,
                "coverage_status": "hybrid",
            },
            "instrument_rows": [
                {
                    "symbol": "BTC/USDT",
                    "volume_24h_usd": "1000.0",
                    "trade_count_24h": 1234,
                }
            ],
        }

    module.build_product_snapshot_fast_payload = fake_fast_payload  # type: ignore[method-assign]
    task = asyncio.create_task(finalized())
    module._state.finalized_startup_task = task
    ready.set()

    snapshot = await module.get_product_snapshot()
    await task

    assert snapshot["instrument_rows"][0]["trade_count_24h"] == 1234
    assert snapshot["persistence_24h"]["persisted_trade_count_24h"] == 1234


@pytest.mark.asyncio
async def test_module_product_snapshot_keeps_pending_cache_ttl_short_when_exact_rows_are_missing() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
        scope_mode="selected",
        total_instruments_discovered=1,
        instruments_passed_coarse_filter=1,
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.get_runtime_status = lambda: {  # type: ignore[method-assign]
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "connected_live",
        "transport_status": "connected",
        "selected_symbols_count": 1,
        "filtered_symbols_count": 1,
        "symbols": ("BTC/USDT",),
    }
    module.is_final_scope_refresh_due = lambda **_: False  # type: ignore[method-assign]
    module.schedule_finalized_startup = lambda: None  # type: ignore[method-assign]

    snapshot = await module.get_product_snapshot()

    assert snapshot["instrument_rows"][0]["trade_count_24h"] is None
    assert module._state.product_snapshot_cache_expires_at is not None
    ttl_seconds = (
        module._state.product_snapshot_cache_expires_at - datetime.now(tz=UTC)
    ).total_seconds()
    assert ttl_seconds < 1


@pytest.mark.asyncio
async def test_module_product_snapshot_does_not_retrigger_finalized_startup_while_recovery_incomplete() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
        discovery_signature=("stale",),
    )
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {  # type: ignore[method-assign]
        "status": "running",
        "reason": None,
    }
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.get_runtime_status = lambda: {  # type: ignore[method-assign]
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "connected_live",
        "transport_status": "connected",
        "selected_symbols_count": 1,
        "filtered_symbols_count": 1,
        "symbols": ("BTC/USDT",),
    }
    module.is_final_scope_refresh_due = lambda **_: True  # type: ignore[method-assign]
    module.schedule_finalized_startup = Mock()  # type: ignore[method-assign]

    await module.get_product_snapshot()

    module.schedule_finalized_startup.assert_not_called()


def test_module_treats_planned_recovery_as_incomplete_coverage() -> None:
    runtime = _make_runtime()
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {  # type: ignore[method-assign]
        "status": "planned",
        "stage": "planning",
        "reason": None,
    }
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())

    assert module.is_trade_truth_coverage_incomplete() is True


@pytest.mark.asyncio
async def test_module_fast_snapshot_publishes_scope_rows_without_fake_exact_counts() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        trade_count_filter_minimum=20000,
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())

    snapshot = await module.build_product_snapshot_fast_payload(
        now=datetime.now(tz=UTC),
        runtime_status={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "selected_symbols_count": 1,
            "filtered_symbols_count": 1,
            "symbols": ("BTC/USDT",),
        },
    )

    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": None,
        }
    ]
    assert snapshot["persistence_24h"]["coverage_status"] == "pending_recovery"
    assert snapshot["persistence_24h"]["persisted_trade_count_24h"] == 0
    assert snapshot["symbols"] == ("BTC/USDT",)
    assert snapshot["selected_symbols_count"] == 1
    assert snapshot["filtered_symbols_count"] == 1


@pytest.mark.asyncio
async def test_module_fast_fallback_snapshot_ignores_stale_runtime_counters() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT", "ETH/USDT"),
        coarse_selected_symbols=("BTC/USDT", "ETH/USDT"),
        selected_quote_volume_24h_usd_by_symbol=(
            ("BTC/USDT", "1000.0"),
            ("ETH/USDT", "2000.0"),
        ),
        coarse_selected_quote_volume_24h_usd_by_symbol=(
            ("BTC/USDT", "1000.0"),
            ("ETH/USDT", "2000.0"),
        ),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000), ("ETH/USDT", 18000)),
        trade_count_filter_minimum=20000,
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())

    snapshot = await module.build_product_snapshot_fast_payload(
        now=datetime.now(tz=UTC),
        runtime_status={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "selected_symbols_count": 99,
            "filtered_symbols_count": 77,
            "symbols": ("STALE/USDT",),
        },
    )

    assert snapshot["symbols"] == ("BTC/USDT", "ETH/USDT")
    assert snapshot["selected_symbols_count"] == 2
    assert snapshot["filtered_symbols_count"] == 2
    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": None,
        },
        {
            "symbol": "ETH/USDT",
            "volume_24h_usd": "2000.0",
            "trade_count_24h": None,
        },
    ]


@pytest.mark.asyncio
async def test_module_fast_fallback_snapshot_uses_coarse_symbols_when_published_scope_is_empty() -> None:
    runtime = _make_runtime()
    runtime.settings = _make_settings(bybit_spot_universe_min_trade_count_24h=2000)
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=(),
        coarse_selected_symbols=("BTC/USDT", "ETH/USDT"),
        selected_quote_volume_24h_usd_by_symbol=(),
        coarse_selected_quote_volume_24h_usd_by_symbol=(
            ("BTC/USDT", "1000.0"),
            ("ETH/USDT", "2000.0"),
        ),
        selected_trade_count_24h_by_symbol=(),
        trade_count_filter_minimum=2000,
        instruments_passed_final_filter=0,
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())

    snapshot = await module.build_product_snapshot_fast_payload(
        now=datetime.now(tz=UTC),
        runtime_status={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "selected_symbols_count": 0,
            "filtered_symbols_count": 0,
            "symbols": (),
        },
    )

    assert snapshot["symbols"] == ("BTC/USDT", "ETH/USDT")
    assert snapshot["selected_symbols_count"] == 2
    assert snapshot["filtered_symbols_count"] == 2
    assert snapshot["screen_scope_reason"] == "fallback_provisional_scope"
    assert snapshot["contract_flags"] == {
        "row_count_matches_selected_symbols_count": True,
        "row_symbols_match_symbols": True,
        "pending_archive_rows_masked": True,
        "numeric_rows_respect_min_trade_count": True,
        "runtime_scope_diverges_from_snapshot": False,
    }
    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": None,
        },
        {
            "symbol": "ETH/USDT",
            "volume_24h_usd": "2000.0",
            "trade_count_24h": None,
        },
    ]


@pytest.mark.asyncio
async def test_module_fast_snapshot_marks_exact_cache_as_exact_truth() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        trade_count_filter_minimum=20000,
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module._state.exact_trade_cache_by_symbol = {
        "BTC/USDT": SimpleNamespace(
            live_trade_count_24h=25000,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=25000,
            earliest_trade_at=datetime.now(tz=UTC) - timedelta(hours=1),
            latest_trade_at=datetime.now(tz=UTC),
            coverage_status="live_only",
        )
    }
    module._state.exact_trade_cache_symbols = ("BTC/USDT",)

    snapshot = await module.build_product_snapshot_fast_payload(
        now=datetime.now(tz=UTC),
        runtime_status={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "selected_symbols_count": 1,
            "filtered_symbols_count": 1,
            "symbols": ("BTC/USDT",),
        },
    )

    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": None,
        }
    ]
    assert snapshot["symbols"] == ("BTC/USDT",)
    assert snapshot["selected_symbols_count"] == 1
    assert snapshot["persistence_24h"]["coverage_status"] == "pending_recovery"
    assert snapshot["filtered_symbols_count"] == 1


@pytest.mark.asyncio
async def test_module_fast_snapshot_prefers_transport_turnover_over_scope_snapshot() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        trade_count_filter_minimum=20000,
    )
    runtime.get_bybit_spot_v2_transport_diagnostics = lambda: {
        "transport_status": "connected",
        "subscription_alive": True,
        "quote_turnover_24h_by_symbol": {"BTC/USDT": "2000.0"},
    }
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module._state.exact_trade_cache_by_symbol = {
        "BTC/USDT": SimpleNamespace(
            live_trade_count_24h=25000,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=25000,
            earliest_trade_at=datetime.now(tz=UTC) - timedelta(hours=1),
            latest_trade_at=datetime.now(tz=UTC),
            coverage_status="live_only",
        )
    }
    module._state.exact_trade_cache_symbols = ("BTC/USDT",)

    snapshot = await module.build_product_snapshot_fast_payload(
        now=datetime.now(tz=UTC),
        runtime_status={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "selected_symbols_count": 1,
            "filtered_symbols_count": 1,
            "symbols": ("BTC/USDT",),
        },
    )

    assert snapshot["instrument_rows"][0]["volume_24h_usd"] == "2000.0"


@pytest.mark.asyncio
async def test_module_fast_snapshot_publishes_exact_filtered_count_after_apply() -> None:
    runtime = _make_runtime()
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {  # type: ignore[method-assign]
        "status": "running",
        "stage": "archive_day_fetch_started",
        "reason": None,
    }
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=0,
        selected_trade_count_24h_is_final=False,
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module._state.exact_trade_cache_by_symbol = {
        "BTC/USDT": SimpleNamespace(
            live_trade_count_24h=15000,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=15000,
            earliest_trade_at=datetime.now(tz=UTC) - timedelta(hours=1),
            latest_trade_at=datetime.now(tz=UTC),
            coverage_status="live_only",
        )
    }
    module._state.exact_trade_cache_symbols = ("BTC/USDT",)

    snapshot = await module.build_product_snapshot_fast_payload(
        now=datetime.now(tz=UTC),
        runtime_status={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "selected_symbols_count": 1,
            "filtered_symbols_count": 1,
            "symbols": ("BTC/USDT",),
        },
    )

    assert snapshot["symbols"] == ("BTC/USDT",)
    assert snapshot["filtered_symbols_count"] == 1
    assert snapshot["selected_symbols_count"] == 1
    assert snapshot["screen_scope_reason"] == "fallback_provisional_scope"
    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": None,
        }
    ]


@pytest.mark.asyncio
async def test_module_product_snapshot_does_not_publish_false_empty_scope_when_runtime_scope_is_live() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT", "ETH/USDT"),
        coarse_selected_symbols=("BTC/USDT", "ETH/USDT"),
        selected_quote_volume_24h_usd_by_symbol=(
            ("BTC/USDT", "1000.0"),
            ("ETH/USDT", "2000.0"),
        ),
        coarse_selected_quote_volume_24h_usd_by_symbol=(
            ("BTC/USDT", "1000.0"),
            ("ETH/USDT", "2000.0"),
        ),
        selected_trade_count_24h_by_symbol=(),
        trade_count_filter_minimum=20000,
        instruments_passed_coarse_filter=2,
        instruments_passed_final_filter=0,
        selected_trade_count_24h_is_final=False,
    )
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {  # type: ignore[method-assign]
        "status": "running",
        "stage": "archive_day_parse_started",
        "reason": None,
    }
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    observed_at = datetime.now(tz=UTC)
    module._state.exact_trade_cache_by_symbol = {
        "BTC/USDT": SimpleNamespace(
            live_trade_count_24h=12000,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=12000,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="pending_archive",
        ),
        "ETH/USDT": SimpleNamespace(
            live_trade_count_24h=8000,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=8000,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="pending_archive",
        ),
    }
    module._state.exact_trade_cache_symbols = ("BTC/USDT", "ETH/USDT")
    module.get_runtime_status = lambda: {  # type: ignore[method-assign]
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "connected_live",
        "transport_status": "connected",
        "subscription_alive": True,
        "selected_symbols_count": 2,
        "filtered_symbols_count": 2,
        "volume_filtered_symbols_count": 2,
        "symbols": ("BTC/USDT", "ETH/USDT"),
    }

    snapshot = await module.get_product_snapshot()

    assert snapshot["filtered_symbols_count"] == 2
    assert snapshot["selected_symbols_count"] == 2
    assert snapshot["symbols"] == ("BTC/USDT", "ETH/USDT")
    assert snapshot["screen_scope_reason"] == "fallback_provisional_scope"
    assert snapshot["contract_flags"]["runtime_scope_diverges_from_snapshot"] is False
    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": None,
        },
        {
            "symbol": "ETH/USDT",
            "volume_24h_usd": "2000.0",
            "trade_count_24h": None,
        },
    ]


@pytest.mark.asyncio
async def test_module_fast_snapshot_keeps_provisional_rows_when_exact_cache_is_incomplete() -> None:
    runtime = _make_runtime()
    runtime.settings = _make_settings(bybit_spot_universe_min_trade_count_24h=1000)
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT", "ETH/USDT"),
        coarse_selected_symbols=("BTC/USDT", "ETH/USDT"),
        selected_quote_volume_24h_usd_by_symbol=(
            ("BTC/USDT", "1000.0"),
            ("ETH/USDT", "2000.0"),
        ),
        coarse_selected_quote_volume_24h_usd_by_symbol=(
            ("BTC/USDT", "1000.0"),
            ("ETH/USDT", "2000.0"),
        ),
        selected_trade_count_24h_by_symbol=(),
        trade_count_filter_minimum=1000,
        instruments_passed_final_filter=0,
        selected_trade_count_24h_is_final=False,
    )
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {  # type: ignore[method-assign]
        "status": "running",
        "stage": "archive_day_fetch_started",
        "reason": None,
    }
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module._state.exact_trade_cache_by_symbol = {
        "BTC/USDT": SimpleNamespace(
            live_trade_count_24h=0,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=0,
            earliest_trade_at=None,
            latest_trade_at=None,
            coverage_status="pending_archive",
        ),
        "ETH/USDT": SimpleNamespace(
            live_trade_count_24h=0,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=0,
            earliest_trade_at=None,
            latest_trade_at=None,
            coverage_status="pending_archive",
        ),
    }

    snapshot = await module.build_product_snapshot_fast_payload(
        now=datetime.now(tz=UTC),
        runtime_status={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "selected_symbols_count": 2,
            "filtered_symbols_count": 2,
            "symbols": ("BTC/USDT", "ETH/USDT"),
        },
    )

    assert snapshot["symbols"] == ("BTC/USDT", "ETH/USDT")
    assert snapshot["selected_symbols_count"] == 2
    assert snapshot["filtered_symbols_count"] == 2
    assert snapshot["screen_scope_reason"] == "fallback_provisional_scope"
    assert snapshot["contract_flags"]["runtime_scope_diverges_from_snapshot"] is False
    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": None,
        },
        {
            "symbol": "ETH/USDT",
            "volume_24h_usd": "2000.0",
            "trade_count_24h": None,
        },
    ]
    assert snapshot["persistence_24h"]["coverage_status"] == "pending_recovery"


@pytest.mark.asyncio
async def test_module_fast_snapshot_adds_published_contract_flags_without_changing_result() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        trade_count_filter_minimum=20000,
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    now = datetime.now(tz=UTC)
    module._state.exact_trade_cache_by_symbol = {
        "BTC/USDT": SimpleNamespace(
            live_trade_count_24h=25000,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=25000,
            earliest_trade_at=now - timedelta(hours=1),
            latest_trade_at=now,
            coverage_status="archive_only",
        )
    }
    module._state.exact_trade_cache_symbols = ("BTC/USDT",)

    snapshot = await module.build_product_snapshot_fast_payload(
        now=now,
        runtime_status={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "selected_symbols_count": 1,
            "filtered_symbols_count": 1,
            "symbols": ("BTC/USDT",),
        },
    )

    assert snapshot["symbols"] == ("BTC/USDT",)
    assert snapshot["selected_symbols_count"] == 1
    assert snapshot["filtered_symbols_count"] == 1
    assert snapshot["screen_scope_reason"] == "strict_published_scope_pending_archive_masked"
    assert snapshot["contract_flags"] == {
        "row_count_matches_selected_symbols_count": True,
        "row_symbols_match_symbols": True,
        "pending_archive_rows_masked": True,
        "numeric_rows_respect_min_trade_count": True,
        "runtime_scope_diverges_from_snapshot": False,
    }


@pytest.mark.asyncio
async def test_module_product_snapshot_uses_exact_cache_during_connected_no_flow_after_apply() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module._state.exact_trade_cache_by_symbol = {
        "BTC/USDT": SimpleNamespace(
            live_trade_count_24h=25000,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=25000,
            earliest_trade_at=datetime.now(tz=UTC) - timedelta(hours=1),
            latest_trade_at=datetime.now(tz=UTC),
            coverage_status="live_only",
        )
    }
    module._state.exact_trade_cache_symbols = ("BTC/USDT",)
    module.get_runtime_status = lambda: {  # type: ignore[method-assign]
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "connected_no_flow",
        "transport_status": "connected",
        "selected_symbols_count": 1,
        "filtered_symbols_count": 1,
        "symbols": ("BTC/USDT",),
    }
    module.is_final_scope_refresh_due = lambda **_: False  # type: ignore[method-assign]
    module.schedule_finalized_startup = lambda: None  # type: ignore[method-assign]

    snapshot = await module.get_product_snapshot()

    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": None,
        }
    ]
    assert snapshot["screen_scope_reason"] == "fallback_provisional_scope"
    assert snapshot["symbols"] == ("BTC/USDT",)
    assert snapshot["selected_symbols_count"] == 1
    assert snapshot["filtered_symbols_count"] == 1
    assert snapshot["persistence_24h"]["coverage_status"] == "pending_live"


@pytest.mark.asyncio
async def test_module_schedules_recovery_retry_for_pending_archive() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_v2_recovery = SimpleNamespace()
    runtime.bybit_spot_v2_recovery_task = None
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    retry_calls: list[str] = []

    async def fake_start_v2_recovery() -> None:
        retry_calls.append("started")

    module.start_v2_recovery = fake_start_v2_recovery  # type: ignore[method-assign]

    module.ensure_archive_recovery_if_needed(coverage_status="pending_archive")
    await asyncio.sleep(0)

    assert retry_calls == ["started"]


@pytest.mark.asyncio
async def test_module_product_snapshot_keeps_provisional_rows_during_connected_no_flow_without_exact_cache() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
        discovery_signature=(
            "spot",
            "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
            float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
            str(runtime.settings.bybit_spot_quote_asset_filter),
        ),
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.get_runtime_status = lambda: {  # type: ignore[method-assign]
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "connected_no_flow",
        "transport_status": "connected",
        "selected_symbols_count": 1,
        "filtered_symbols_count": 1,
        "symbols": ("BTC/USDT",),
    }
    module.is_final_scope_refresh_due = lambda **_: False  # type: ignore[method-assign]
    module.schedule_finalized_startup = lambda: None  # type: ignore[method-assign]

    snapshot = await module.get_product_snapshot()

    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": None,
        }
    ]
    assert snapshot["persistence_24h"]["coverage_status"] == "pending_live"


@pytest.mark.asyncio
async def test_module_product_snapshot_keeps_provisional_rows_during_startup_without_exact_cache() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
        discovery_signature=(
            "spot",
            "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
            float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
            str(runtime.settings.bybit_spot_quote_asset_filter),
        ),
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.get_runtime_status = lambda: {  # type: ignore[method-assign]
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "starting",
        "transport_status": "idle",
        "selected_symbols_count": 1,
        "filtered_symbols_count": 1,
        "symbols": ("BTC/USDT",),
    }
    module.is_final_scope_refresh_due = lambda **_: False  # type: ignore[method-assign]
    module.schedule_finalized_startup = lambda: None  # type: ignore[method-assign]

    snapshot = await module.get_product_snapshot()

    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": None,
        }
    ]
    assert snapshot["persistence_24h"]["coverage_status"] == "pending_startup"


@pytest.mark.asyncio
async def test_module_product_snapshot_waits_briefly_for_exact_cache_when_live_snapshot_is_publishable() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        trade_count_filter_minimum=1,
        instruments_passed_final_filter=1,
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.get_runtime_status = lambda: {  # type: ignore[method-assign]
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "connected_live",
        "transport_status": "connected",
        "subscription_alive": True,
        "selected_symbols_count": 1,
        "filtered_symbols_count": 1,
        "symbols": ("BTC/USDT",),
    }
    module.is_final_scope_refresh_due = lambda **_: False  # type: ignore[method-assign]
    module.build_product_snapshot_fast_payload = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "selected_symbols_count": 1,
            "filtered_symbols_count": 1,
            "symbols": ("BTC/USDT",),
            "observed_at": datetime.now(tz=UTC).isoformat(),
            "persistence_24h": {
                "live_trade_count_24h": 1,
                "archive_trade_count_24h": 2,
                "persisted_trade_count_24h": 3,
                "first_persisted_trade_at": None,
                "last_persisted_trade_at": None,
                "coverage_status": "hybrid",
            },
            "instrument_rows": [{"symbol": "BTC/USDT", "trade_count_24h": 3}],
        }
    )
    module._state.exact_trade_cache_by_symbol = {
        "BTC/USDT": SimpleNamespace(
            live_trade_count_24h=1,
            archive_trade_count_24h=2,
            persisted_trade_count_24h=3,
            earliest_trade_at=None,
            latest_trade_at=None,
            coverage_status="hybrid",
        )
    }
    module._state.exact_trade_cache_symbols = ("BTC/USDT",)
    module._state.exact_trade_cache_expires_at = datetime.now(tz=UTC) + timedelta(seconds=30)
    completed = asyncio.get_running_loop().create_future()
    completed.set_result(None)
    module._state.exact_trade_cache_refresh_task = completed

    snapshot = await module.get_product_snapshot()

    assert snapshot["instrument_rows"] == [{"symbol": "BTC/USDT", "trade_count_24h": 3}]
    module.build_product_snapshot_fast_payload.assert_awaited_once()


def test_module_snapshot_cache_is_not_usable_when_selected_scope_changed() -> None:
    runtime = _make_runtime()
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())

    usable = module.is_product_snapshot_cache_usable(
        cache_payload={
            "lifecycle_state": "connected_live",
            "selected_symbols_count": 24,
            "symbols": tuple(f"SYM{i}/USDT" for i in range(24)),
            "instrument_rows": [{"symbol": "SYM0/USDT", "trade_count_24h": 1000}],
            "persistence_24h": {"persisted_trade_count_24h": 1000},
        },
        runtime_status={
            "lifecycle_state": "connected_live",
            "selected_symbols_count": 3,
        },
    )

    assert usable is False


def test_module_snapshot_cache_is_not_usable_when_symbol_set_changed_with_same_size() -> None:
    runtime = _make_runtime()
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())

    usable = module.is_product_snapshot_cache_usable(
        cache_payload={
            "lifecycle_state": "connected_live",
            "selected_symbols_count": 2,
            "symbols": ("BTC/USDT", "ETH/USDT"),
            "instrument_rows": [
                {"symbol": "BTC/USDT", "trade_count_24h": 1000},
                {"symbol": "ETH/USDT", "trade_count_24h": 1000},
            ],
            "persistence_24h": {"persisted_trade_count_24h": 2000},
        },
        runtime_status={
            "lifecycle_state": "connected_live",
            "selected_symbols_count": 2,
            "symbols": ("BTC/USDT", "SOL/USDT"),
        },
    )

    assert usable is False


def test_module_private_exact_query_profile_uses_low_pressure_mode_for_large_scope() -> None:
    assert _resolve_exact_query_profile(symbol_count=302) == (512, 1)
    assert _resolve_exact_query_profile(symbol_count=140) == (256, 1)
    assert _resolve_exact_query_profile(symbol_count=70) == (128, 1)
    assert _resolve_exact_query_profile(symbol_count=10) == (24, 4)


@pytest.mark.asyncio
async def test_module_cached_exact_trade_query_uses_low_pressure_profile_for_large_scope() -> None:
    runtime = _make_runtime()
    deps = _make_deps()
    captured: dict[str, object] = {}

    async def fake_query(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return {
            symbol: SimpleNamespace(
                normalized_symbol=symbol,
                live_trade_count_24h=1,
                archive_trade_count_24h=2,
                persisted_trade_count_24h=3,
                earliest_trade_at=None,
                latest_trade_at=None,
                coverage_status="hybrid",
            )
            for symbol in kwargs["symbols"]
        }

    deps.query_exact_trade_count_snapshots_uncached = fake_query  # type: ignore[assignment]
    module = BybitSpotModule(runtime=runtime, deps=deps)
    symbols = tuple(f"SYM{i}/USDT" for i in range(302))

    snapshots = await module.get_cached_exact_trade_counts_by_symbol(
        symbols=symbols,
        observed_at=datetime.now(tz=UTC),
    )

    assert len(snapshots) == 302
    assert captured["chunk_size"] == 512
    assert captured["batch_concurrency"] == 1


@pytest.mark.asyncio
async def test_module_final_scope_retains_current_selected_scope_when_incomplete_refresh_would_zero_it() -> None:
    runtime = _make_runtime()
    current_truth = SimpleNamespace(
        scope_mode="universe",
        total_instruments_discovered=2,
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT", "ETH/USDT"),
        instruments_passed_coarse_filter=2,
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(
            ("BTC/USDT", "1000.0"),
            ("ETH/USDT", "900.0"),
        ),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
    )
    runtime.bybit_spot_market_data_scope_summary = current_truth
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {
        "status": "running",
        "reason": "coverage_incomplete",
    }
    deps = _make_deps()
    deps.query_exact_trade_count_snapshots_uncached = AsyncMock(return_value={})
    module = BybitSpotModule(runtime=runtime, deps=deps)
    module._state.finalized_scope_resolved_at = datetime.now(tz=UTC)
    resolved_scope = SimpleNamespace(
        symbols=("BTC/USDT", "ETH/USDT"),
        truth=SimpleNamespace(
            scope_mode="universe",
            total_instruments_discovered=2,
            discovery_signature=(
                "spot",
                "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
                float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
                str(runtime.settings.bybit_spot_quote_asset_filter),
            ),
            selected_symbols=(),
            coarse_selected_symbols=("BTC/USDT", "ETH/USDT"),
            instruments_passed_coarse_filter=2,
            selected_quote_volume_24h_usd_by_symbol=(),
            coarse_selected_quote_volume_24h_usd_by_symbol=(
                ("BTC/USDT", "1000.0"),
                ("ETH/USDT", "900.0"),
            ),
            selected_trade_count_24h_by_symbol=(),
            trade_count_filter_minimum=20000,
            instruments_passed_final_filter=0,
        ),
    )

    final_scope = await module.resolve_final_scope(
        settings=runtime.settings,
        resolved_scope=resolved_scope,
    )

    assert final_scope.symbols == ("BTC/USDT", "ETH/USDT")
    assert final_scope.truth.selected_symbols == ()
    assert final_scope.truth.selected_trade_count_24h_by_symbol == ()
    assert final_scope.truth.selected_trade_count_24h_is_final is False


@pytest.mark.asyncio
async def test_module_final_scope_reuses_exact_snapshot_cache() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        discovery_signature=(
            "spot",
            "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
            float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
            str(runtime.settings.bybit_spot_quote_asset_filter),
        ),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        selected_trade_count_24h_is_final=True,
    )
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {"status": "idle", "reason": None}
    deps = _make_deps()
    deps.query_exact_trade_count_snapshots_uncached = AsyncMock(
        side_effect=AssertionError("should_reuse_cache")
    )
    module = BybitSpotModule(runtime=runtime, deps=deps)
    now = datetime.now(tz=UTC)
    module._state.exact_trade_cache_by_symbol = {
        "BTC/USDT": SimpleNamespace(
            persisted_trade_count_24h=25000,
            coverage_status="live_only",
        )
    }
    module._state.exact_trade_cache_symbols = ("BTC/USDT",)
    module._state.exact_trade_cache_expires_at = now + timedelta(seconds=60)
    module._state.finalized_scope_resolved_at = now
    resolved_scope = SimpleNamespace(
        symbols=("BTC/USDT",),
        truth=SimpleNamespace(
            selected_symbols=("BTC/USDT",),
            coarse_selected_symbols=("BTC/USDT",),
            selected_quote_volume_24h_usd_by_symbol=(),
            coarse_selected_quote_volume_24h_usd_by_symbol=(),
            selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
            trade_count_filter_minimum=20000,
            instruments_passed_final_filter=1,
        ),
    )

    final_scope = await module.resolve_final_scope(
        settings=runtime.settings,
        resolved_scope=resolved_scope,
    )

    assert final_scope.truth.selected_trade_count_24h_by_symbol == (("BTC/USDT", 25000),)


@pytest.mark.asyncio
async def test_module_final_scope_keeps_incomplete_symbols_in_monitoring_scope_but_not_published_scope() -> None:
    runtime = _make_runtime()
    runtime.settings = _make_settings(bybit_spot_universe_min_trade_count_24h=1)
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {
        "status": "running",
        "reason": "coverage_incomplete",
    }
    deps = _make_deps()
    deps.resolve_min_trade_count_24h = lambda *, settings, **_: int(  # type: ignore[assignment]
        settings.bybit_spot_universe_min_trade_count_24h
    )
    coarse_symbols = tuple(f"SYM{i}/USDT" for i in range(315))
    deps.query_exact_trade_count_snapshots_uncached = AsyncMock(
        return_value={
            **{
                symbol: SimpleNamespace(
                    persisted_trade_count_24h=0,
                    coverage_status="pending_archive",
                )
                for symbol in coarse_symbols[:-2]
            },
            coarse_symbols[-2]: SimpleNamespace(
                persisted_trade_count_24h=1,
                coverage_status="hybrid",
            ),
            coarse_symbols[-1]: SimpleNamespace(
                persisted_trade_count_24h=1,
                coverage_status="hybrid",
            ),
        }
    )
    module = BybitSpotModule(runtime=runtime, deps=deps)
    resolved_scope = SimpleNamespace(
        symbols=coarse_symbols,
        truth=SimpleNamespace(
            scope_mode="universe",
            total_instruments_discovered=633,
            selected_symbols=(),
            coarse_selected_symbols=coarse_symbols,
            instruments_passed_coarse_filter=315,
            selected_quote_volume_24h_usd_by_symbol=(),
            coarse_selected_quote_volume_24h_usd_by_symbol=tuple(
                (symbol, "1000.0") for symbol in coarse_symbols
            ),
            selected_trade_count_24h_by_symbol=(),
            trade_count_filter_minimum=1,
            instruments_passed_final_filter=0,
        ),
    )

    final_scope = await module.resolve_final_scope(
        settings=runtime.settings,
        resolved_scope=resolved_scope,
    )

    assert len(final_scope.symbols) == 315
    assert final_scope.truth.selected_symbols == coarse_symbols[-2:]
    assert final_scope.truth.instruments_passed_final_filter == 2
    assert final_scope.truth.selected_trade_count_24h_is_final is False
    assert final_scope.truth.selected_trade_count_24h_by_symbol == (
        (coarse_symbols[-2], 1),
        (coarse_symbols[-1], 1),
    )


@pytest.mark.asyncio
async def test_module_final_scope_treats_empty_bootstrap_snapshots_as_incomplete_before_recovery_starts() -> None:
    runtime = _make_runtime()
    runtime.settings = _make_settings(bybit_spot_universe_min_trade_count_24h=1)
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {
        "status": "waiting_for_scope",
        "reason": None,
    }
    deps = _make_deps()
    deps.resolve_min_trade_count_24h = lambda *, settings, **_: int(  # type: ignore[assignment]
        settings.bybit_spot_universe_min_trade_count_24h
    )
    coarse_symbols = tuple(f"SYM{i}/USDT" for i in range(313))
    deps.query_exact_trade_count_snapshots_uncached = AsyncMock(
        return_value={
            coarse_symbols[0]: SimpleNamespace(
                persisted_trade_count_24h=5,
                coverage_status="hybrid",
            ),
            coarse_symbols[1]: SimpleNamespace(
                persisted_trade_count_24h=3,
                coverage_status="hybrid",
            ),
        }
    )
    module = BybitSpotModule(runtime=runtime, deps=deps)
    resolved_scope = SimpleNamespace(
        symbols=coarse_symbols,
        truth=SimpleNamespace(
            scope_mode="universe",
            total_instruments_discovered=633,
            selected_symbols=(),
            coarse_selected_symbols=coarse_symbols,
            instruments_passed_coarse_filter=313,
            selected_quote_volume_24h_usd_by_symbol=(),
            coarse_selected_quote_volume_24h_usd_by_symbol=tuple(
                (symbol, "1000.0") for symbol in coarse_symbols
            ),
            selected_trade_count_24h_by_symbol=(),
            trade_count_filter_minimum=1,
            instruments_passed_final_filter=0,
        ),
    )

    final_scope = await module.resolve_final_scope(
        settings=runtime.settings,
        resolved_scope=resolved_scope,
    )

    assert len(final_scope.symbols) == 313
    assert final_scope.truth.selected_symbols == (coarse_symbols[0], coarse_symbols[1])
    assert final_scope.truth.instruments_passed_final_filter == 2
    assert final_scope.truth.selected_trade_count_24h_is_final is False


@pytest.mark.asyncio
async def test_module_final_scope_marks_exact_empty_result_as_confirmed_only_after_complete_resolution() -> None:
    runtime = _make_runtime()
    runtime.settings = _make_settings(bybit_spot_universe_min_trade_count_24h=20000)
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {
        "status": "idle",
        "reason": None,
    }
    deps = _make_deps()
    deps.resolve_min_trade_count_24h = lambda *, settings, **_: int(  # type: ignore[assignment]
        settings.bybit_spot_universe_min_trade_count_24h
    )
    deps.query_exact_trade_count_snapshots_uncached = AsyncMock(
        return_value={
            "BTC/USDT": SimpleNamespace(
                persisted_trade_count_24h=0,
                coverage_status="archive_only",
            ),
            "ETH/USDT": SimpleNamespace(
                persisted_trade_count_24h=0,
                coverage_status="archive_only",
            ),
        }
    )
    module = BybitSpotModule(runtime=runtime, deps=deps)
    module._state.finalized_scope_resolved_at = datetime.now(tz=UTC)
    resolved_scope = SimpleNamespace(
        symbols=("BTC/USDT", "ETH/USDT"),
        truth=SimpleNamespace(
            scope_mode="universe",
            total_instruments_discovered=2,
            discovery_signature=(
                "spot",
                "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
                float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
                str(runtime.settings.bybit_spot_quote_asset_filter),
            ),
            selected_symbols=(),
            coarse_selected_symbols=("BTC/USDT", "ETH/USDT"),
            instruments_passed_coarse_filter=2,
            selected_quote_volume_24h_usd_by_symbol=(),
            coarse_selected_quote_volume_24h_usd_by_symbol=(
                ("BTC/USDT", "1000.0"),
                ("ETH/USDT", "900.0"),
            ),
            selected_trade_count_24h_by_symbol=(),
            trade_count_filter_minimum=20000,
            instruments_passed_final_filter=0,
        ),
    )

    final_scope = await module.resolve_final_scope(
        settings=runtime.settings,
        resolved_scope=resolved_scope,
    )

    assert final_scope.truth.selected_symbols == ()
    assert final_scope.truth.selected_trade_count_24h_is_final is True
    assert final_scope.truth.selected_trade_count_24h_empty_scope_confirmed is True
    assert _spot_scope_truth_is_final_for_settings(
        settings=runtime.settings,
        truth=final_scope.truth,
    )


@pytest.mark.asyncio
async def test_module_final_scope_bypasses_stale_exact_cache_when_current_scope_empty() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        scope_mode="universe",
        selected_symbols=(),
        coarse_selected_symbols=("BTC/USDT",),
        selected_trade_count_24h_by_symbol=(),
        instruments_passed_final_filter=0,
        instruments_passed_coarse_filter=1,
    )
    deps = _make_deps()
    deps.query_exact_trade_count_snapshots_uncached = AsyncMock(
        return_value={
            "BTC/USDT": SimpleNamespace(
                persisted_trade_count_24h=25000,
                coverage_status="hybrid",
            )
        }
    )
    module = BybitSpotModule(runtime=runtime, deps=deps)
    module.get_runtime_status = lambda: {"symbols": ()}  # type: ignore[method-assign]
    now = datetime.now(tz=UTC)
    module._state.exact_trade_cache_by_symbol = {
        "BTC/USDT": SimpleNamespace(
            persisted_trade_count_24h=0,
            coverage_status="empty",
        )
    }
    module._state.exact_trade_cache_symbols = ("BTC/USDT",)
    module._state.exact_trade_cache_expires_at = now + timedelta(seconds=60)
    resolved_scope = SimpleNamespace(
        symbols=("BTC/USDT",),
        truth=SimpleNamespace(
            selected_symbols=(),
            coarse_selected_symbols=("BTC/USDT",),
            selected_quote_volume_24h_usd_by_symbol=(),
            coarse_selected_quote_volume_24h_usd_by_symbol=(),
            selected_trade_count_24h_by_symbol=(),
            trade_count_filter_minimum=20000,
            instruments_passed_final_filter=0,
        ),
    )

    final_scope = await module.resolve_final_scope(
        settings=runtime.settings,
        resolved_scope=resolved_scope,
    )

    deps.query_exact_trade_count_snapshots_uncached.assert_awaited_once()
    assert final_scope.truth.selected_symbols == ("BTC/USDT",)
    assert final_scope.truth.selected_trade_count_24h_by_symbol == (("BTC/USDT", 25000),)


def test_module_stable_final_scope_refresh_uses_longer_interval() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        discovery_signature=(
            "spot",
            "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
            float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
            str(runtime.settings.bybit_spot_quote_asset_filter),
        ),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
        coarse_selected_symbols=("BTC/USDT",),
        selected_symbols=("BTC/USDT",),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        selected_trade_count_24h_is_final=True,
    )
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {"status": "idle", "reason": None}
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module._state.finalized_scope_resolved_at = datetime.now(tz=UTC) - timedelta(seconds=40)

    due = module.is_final_scope_refresh_due(
        now=datetime.now(tz=UTC),
        runtime_status={"lifecycle_state": "connected_live"},
    )

    assert due is False


def test_module_runtime_status_caps_operator_rtt_by_fresh_message_age() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        scope_mode="selected",
        total_instruments_discovered=1,
        instruments_passed_coarse_filter=1,
        instruments_passed_final_filter=1,
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
    )
    runtime.get_bybit_spot_v2_transport_diagnostics = lambda: {
        "transport_status": "connected",
        "subscription_alive": True,
        "transport_rtt_ms": 3500,
        "last_message_at": datetime.now(tz=UTC).isoformat(),
        "symbols": ("BTC/USDT",),
        "trade_ingest_count": 1,
        "orderbook_ingest_count": 1,
        "trade_seen": True,
        "orderbook_seen": True,
    }
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {"status": "idle", "reason": None}
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())

    status = module.get_runtime_status()

    assert status["transport_rtt_ms"] is not None
    assert status["transport_rtt_ms"] < 1000


def test_module_resolve_snapshot_symbols_prefers_final_scope_truth_over_runtime_symbols() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT", "ETH/USDT"),
        coarse_selected_symbols=("BTC/USDT", "ETH/USDT", "SOL/USDT"),
    )
    deps = _make_deps()
    deps.resolve_min_trade_count_24h = lambda **_: 1000  # type: ignore[assignment]
    module = BybitSpotModule(runtime=runtime, deps=deps)

    symbols = module.resolve_snapshot_symbols(
        runtime_status={"symbols": ("BTC/USDT", "ETH/USDT", "SOL/USDT")}
    )

    assert symbols == ("BTC/USDT", "ETH/USDT")


def test_module_projection_caps_operator_rtt_by_fresh_message_age() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        trade_count_filter_minimum=1,
    )
    runtime.get_bybit_spot_v2_transport_diagnostics = lambda: {
        "transport_status": "connected",
        "subscription_alive": True,
        "transport_rtt_ms": 4200,
        "last_message_at": datetime.now(tz=UTC).isoformat(),
        "symbols": ("BTC/USDT",),
    }
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {"status": "idle", "reason": None}
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())

    projection = module.get_connector_screen_projection()

    assert projection["transport_rtt_ms"] is not None
    assert projection["transport_rtt_ms"] < 1000


@pytest.mark.asyncio
async def test_module_refresh_product_snapshot_cache_falls_back_to_fast_payload_on_timeout() -> None:
    runtime = _make_runtime()
    runtime.get_bybit_spot_v2_transport_diagnostics = lambda: {
        "transport_status": "connected",
        "subscription_alive": True,
        "symbols": ("BTC/USDT",),
        "trade_ingest_count": 1,
        "orderbook_ingest_count": 1,
        "trade_seen": True,
        "orderbook_seen": True,
    }
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {"status": "running"}
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        scope_mode="selected",
        total_instruments_discovered=1,
        instruments_passed_coarse_filter=1,
        instruments_passed_final_filter=1,
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        trade_count_filter_minimum=1,
    )
    deps = _make_deps()
    deps.resolve_min_trade_count_24h = lambda **_: 1  # type: ignore[assignment]
    module = BybitSpotModule(runtime=runtime, deps=deps)
    module.build_product_snapshot_payload = AsyncMock(side_effect=TimeoutError())  # type: ignore[method-assign]
    module.build_product_snapshot_fast_payload = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "lifecycle_state": "connected_live",
            "selected_symbols_count": 1,
            "filtered_symbols_count": 1,
            "symbols": ("BTC/USDT",),
            "persistence_24h": {"persisted_trade_count_24h": 0},
            "instrument_rows": [],
        }
    )

    await module.refresh_product_snapshot_cache()

    module.build_product_snapshot_fast_payload.assert_awaited_once()
    assert module._state.product_snapshot_cache_payload is not None
    assert module._state.product_snapshot_cache_payload["selected_symbols_count"] == 1


@pytest.mark.asyncio
async def test_module_refresh_exact_trade_cache_swallows_timeout_and_clears_refresh_task() -> None:
    runtime = _make_runtime()
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.get_fresh_exact_trade_counts_by_symbol = AsyncMock(side_effect=TimeoutError())  # type: ignore[method-assign]
    module._state.exact_trade_cache_expires_at = datetime.now(tz=UTC) + timedelta(seconds=60)
    module._state.exact_trade_cache_refresh_task = asyncio.create_task(asyncio.sleep(0))

    await module.refresh_exact_trade_cache(symbols=("BTC/USDT",))

    assert module._state.exact_trade_cache_expires_at is None
    assert module._state.exact_trade_cache_refresh_task is None


@pytest.mark.asyncio
async def test_module_refresh_exact_trade_cache_retriggers_finalized_startup_for_non_final_scope() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_trade_count_24h_by_symbol=(),
        trade_count_filter_minimum=20000,
        discovery_signature=("stale",),
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.get_fresh_exact_trade_counts_by_symbol = AsyncMock(return_value={  # type: ignore[method-assign]
        "BTC/USDT": SimpleNamespace(persisted_trade_count_24h=25000, coverage_status="live_only")
    })
    module.schedule_product_snapshot_refresh = Mock()  # type: ignore[method-assign]
    module.schedule_finalized_startup = Mock()  # type: ignore[method-assign]
    module._state.finalized_startup_retry_after = datetime.now(tz=UTC) + timedelta(seconds=60)

    await module.refresh_exact_trade_cache(symbols=("BTC/USDT",))

    module.schedule_product_snapshot_refresh.assert_called_once()
    module.schedule_finalized_startup.assert_not_called()
    assert module._state.finalized_startup_retry_after is not None


@pytest.mark.asyncio
async def test_module_refresh_exact_trade_cache_does_not_retrigger_finalized_startup_while_coverage_incomplete() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_trade_count_24h_by_symbol=(),
        trade_count_filter_minimum=20000,
        discovery_signature=("stale",),
    )
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {  # type: ignore[method-assign]
        "status": "running",
        "reason": None,
    }
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.get_cached_exact_trade_counts_by_symbol = AsyncMock(return_value={  # type: ignore[method-assign]
        "BTC/USDT": SimpleNamespace(
            persisted_trade_count_24h=25000,
            coverage_status="pending_archive",
        )
    })
    module.schedule_product_snapshot_refresh = Mock()  # type: ignore[method-assign]
    module.schedule_finalized_startup = Mock()  # type: ignore[method-assign]
    module._state.finalized_startup_retry_after = datetime.now(tz=UTC) + timedelta(seconds=60)

    await module.refresh_exact_trade_cache(symbols=("BTC/USDT",))

    module.schedule_product_snapshot_refresh.assert_called_once()
    module.schedule_finalized_startup.assert_not_called()
    assert module._state.finalized_startup_retry_after > datetime.now(tz=UTC)


@pytest.mark.asyncio
async def test_module_refresh_exact_trade_cache_bypasses_stale_cache_contract() -> None:
    runtime = _make_runtime()
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.get_cached_exact_trade_counts_by_symbol = AsyncMock()  # type: ignore[method-assign]
    module.get_fresh_exact_trade_counts_by_symbol = AsyncMock(return_value={  # type: ignore[method-assign]
        "BTC/USDT": SimpleNamespace(
            persisted_trade_count_24h=26000,
            coverage_status="hybrid",
        )
    })
    module.schedule_product_snapshot_refresh = Mock()  # type: ignore[method-assign]
    module.schedule_finalized_startup = Mock()  # type: ignore[method-assign]

    await module.refresh_exact_trade_cache(symbols=("BTC/USDT",))

    module.get_cached_exact_trade_counts_by_symbol.assert_not_called()
    module.get_fresh_exact_trade_counts_by_symbol.assert_awaited_once()
    module.schedule_product_snapshot_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_module_product_snapshot_does_not_retrigger_finalized_startup_on_transient_idle_transport() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        trade_count_filter_minimum=20000,
        selected_trade_count_24h_is_final=True,
        instruments_passed_final_filter=1,
        discovery_signature=(
            "spot",
            "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
            float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
            str(runtime.settings.bybit_spot_quote_asset_filter),
        ),
    )
    runtime.bybit_spot_v2_transport_task = asyncio.create_task(asyncio.sleep(60))
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module._state.product_snapshot_cache_payload = {
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "connected_live",
        "transport_status": "connected",
        "selected_symbols_count": 1,
        "filtered_symbols_count": 1,
        "symbols": ("BTC/USDT",),
        "observed_at": datetime.now(tz=UTC).isoformat(),
        "persistence_24h": {
            "live_trade_count_24h": 25000,
            "archive_trade_count_24h": 0,
            "persisted_trade_count_24h": 25000,
            "coverage_status": "live_only",
        },
        "instrument_rows": [{"symbol": "BTC/USDT", "trade_count_24h": 25000}],
    }
    module._state.product_snapshot_cache_expires_at = datetime.now(tz=UTC) + timedelta(seconds=30)
    module.get_runtime_status = lambda: {  # type: ignore[method-assign]
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "connected_live",
        "transport_status": "idle",
        "selected_symbols_count": 1,
        "filtered_symbols_count": 1,
        "symbols": ("BTC/USDT",),
    }
    module.is_final_scope_refresh_due = lambda **_: False  # type: ignore[method-assign]
    module.schedule_finalized_startup = Mock()  # type: ignore[method-assign]

    try:
        await module.get_product_snapshot()
    finally:
        runtime.bybit_spot_v2_transport_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await runtime.bybit_spot_v2_transport_task

    module.schedule_finalized_startup.assert_not_called()


@pytest.mark.asyncio
async def test_module_product_snapshot_does_not_retrigger_finalized_startup_during_starting_idle_bootstrap() -> None:
    runtime = _make_runtime()
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.get_runtime_status = lambda: {  # type: ignore[method-assign]
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "starting",
        "transport_status": "idle",
        "selected_symbols_count": 0,
        "filtered_symbols_count": 0,
        "symbols": (),
    }
    module.schedule_finalized_startup = Mock()  # type: ignore[method-assign]

    await module.get_product_snapshot()

    module.schedule_finalized_startup.assert_not_called()


@pytest.mark.asyncio
async def test_module_finalized_startup_defers_to_exact_cache_warmup_on_timeout() -> None:
    runtime = _make_runtime()
    deps = _make_deps()
    resolved_scope = SimpleNamespace(
        symbols=("BTC/USDT",),
        truth=SimpleNamespace(
            selected_symbols=("BTC/USDT",),
            coarse_selected_symbols=("BTC/USDT",),
            selected_trade_count_24h_by_symbol=(),
            selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
            coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
            trade_count_filter_minimum=20000,
            instruments_passed_final_filter=0,
        ),
    )
    deps.resolve_canonical_scope_async = AsyncMock(return_value=resolved_scope)
    module = BybitSpotModule(runtime=runtime, deps=deps)
    module.resolve_final_scope = AsyncMock(side_effect=TimeoutError())  # type: ignore[method-assign]
    module.start_v2_transport = AsyncMock()  # type: ignore[method-assign]
    module.start_v2_recovery = AsyncMock()  # type: ignore[method-assign]
    module.schedule_exact_trade_cache_refresh = Mock()  # type: ignore[method-assign]

    await module.run_finalized_startup()

    assert runtime.bybit_spot_market_data_scope_summary is resolved_scope.truth
    module.start_v2_transport.assert_awaited_once()
    module.start_v2_recovery.assert_awaited_once()
    module.schedule_exact_trade_cache_refresh.assert_called_once_with(symbols=("BTC/USDT",))
    assert module._state.finalized_scope_resolved_at is None
    assert module._state.finalized_startup_retry_after is not None


@pytest.mark.asyncio
async def test_module_finalized_startup_reuses_exact_snapshots_from_final_scope() -> None:
    runtime = _make_runtime()
    deps = _make_deps()
    resolved_scope = SimpleNamespace(
        symbols=("BTC/USDT",),
        truth=SimpleNamespace(
            selected_symbols=("BTC/USDT",),
            coarse_selected_symbols=("BTC/USDT",),
            selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
            selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
            coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
            trade_count_filter_minimum=20000,
            instruments_passed_final_filter=1,
            discovery_signature=(
                "spot",
                "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
                float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
                str(runtime.settings.bybit_spot_quote_asset_filter),
            ),
        ),
    )
    deps.resolve_canonical_scope_async = AsyncMock(return_value=resolved_scope)
    module = BybitSpotModule(runtime=runtime, deps=deps)
    observed_at = datetime.now(tz=UTC)
    module.resolve_final_scope = AsyncMock(return_value=resolved_scope)  # type: ignore[method-assign]
    module.start_v2_transport = AsyncMock()  # type: ignore[method-assign]
    module.start_v2_recovery = AsyncMock()  # type: ignore[method-assign]
    module.schedule_exact_trade_cache_refresh = Mock()  # type: ignore[method-assign]
    module._state.latest_final_scope_exact_snapshots = {
        "BTC/USDT": SimpleNamespace(
            live_trade_count_24h=1000,
            archive_trade_count_24h=24000,
            persisted_trade_count_24h=25000,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="hybrid",
        )
    }
    module._state.latest_final_scope_exact_symbols = ("BTC/USDT",)
    module._state.latest_final_scope_exact_observed_at = observed_at

    await module.run_finalized_startup()

    assert runtime.bybit_spot_market_data_scope_summary is resolved_scope.truth
    assert module._state.exact_trade_cache_by_symbol is not None
    assert module._state.exact_trade_cache_by_symbol["BTC/USDT"].persisted_trade_count_24h == 25000
    assert module._state.exact_trade_cache_symbols == ("BTC/USDT",)
    module.schedule_exact_trade_cache_refresh.assert_not_called()


@pytest.mark.asyncio
async def test_module_fast_snapshot_reuses_latest_final_exact_snapshots_before_cache_refresh() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("BTC/USDT",),
        coarse_selected_symbols=("BTC/USDT",),
        selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
        selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
        discovery_signature=(
            "spot",
            "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
            float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
            str(runtime.settings.bybit_spot_quote_asset_filter),
        ),
    )
    runtime.get_bybit_spot_v2_transport_diagnostics = lambda: {
        "transport_status": "connected",
        "subscription_alive": True,
        "quote_turnover_24h_by_symbol": {"BTC/USDT": "1000.0"},
    }
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    observed_at = datetime.now(tz=UTC)
    module._state.latest_final_scope_exact_snapshots = {
        "BTC/USDT": SimpleNamespace(
            live_trade_count_24h=1000,
            archive_trade_count_24h=24000,
            persisted_trade_count_24h=25000,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="hybrid",
        )
    }
    module._state.latest_final_scope_exact_symbols = ("BTC/USDT",)
    module._state.latest_final_scope_exact_observed_at = observed_at

    snapshot = await module.build_product_snapshot_fast_payload(
        now=observed_at,
        runtime_status={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "subscription_alive": True,
            "selected_symbols_count": 1,
            "filtered_symbols_count": 1,
            "symbols": ("BTC/USDT",),
        },
    )

    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": 25000,
        }
    ]
    assert snapshot["screen_scope_reason"] == "strict_published_scope"
    assert snapshot["contract_flags"] == {
        "row_count_matches_selected_symbols_count": True,
        "row_symbols_match_symbols": True,
        "pending_archive_rows_masked": True,
        "numeric_rows_respect_min_trade_count": True,
        "runtime_scope_diverges_from_snapshot": False,
    }
    assert snapshot["persistence_24h"]["persisted_trade_count_24h"] == 25000
    assert snapshot["persistence_24h"]["coverage_status"] == "hybrid"


def test_module_product_snapshot_diagnostics_marks_empty_scope_with_live_runtime() -> None:
    runtime_status = {
        "filtered_symbols_count": 3,
        "volume_filtered_symbols_count": 7,
    }
    persistence_24h = {
        "coverage_status": "empty",
    }
    instrument_rows: list[dict[str, object]] = []
    symbols: tuple[str, ...] = ()

    reason = _resolve_product_snapshot_reason(
        symbols=symbols,
        instrument_rows=instrument_rows,
        persistence_24h=persistence_24h,
        runtime_status=runtime_status,
    )
    flags = _build_product_snapshot_contract_flags(
        symbols=symbols,
        instrument_rows=instrument_rows,
        persistence_24h=persistence_24h,
        runtime_status=runtime_status,
        min_trade_count_24h=2000,
    )

    assert reason == "empty_scope_with_live_runtime"
    assert flags == {
        "row_count_matches_selected_symbols_count": True,
        "row_symbols_match_symbols": True,
        "pending_archive_rows_masked": True,
        "numeric_rows_respect_min_trade_count": True,
        "runtime_scope_diverges_from_snapshot": True,
    }


@pytest.mark.asyncio
async def test_module_fast_snapshot_excludes_incomplete_rows_that_do_not_pass_published_trade_filter() -> None:
    runtime = _make_runtime()
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {"status": "running"}
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("CHIP/USDT",),
        coarse_selected_symbols=("CHIP/USDT",),
        selected_trade_count_24h_by_symbol=(("CHIP/USDT", 62000),),
        selected_quote_volume_24h_usd_by_symbol=(("CHIP/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("CHIP/USDT", "1000.0"),),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
        discovery_signature=(
            "spot",
            "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
            float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
            str(runtime.settings.bybit_spot_quote_asset_filter),
        ),
    )
    runtime.get_bybit_spot_v2_transport_diagnostics = lambda: {
        "transport_status": "connected",
        "subscription_alive": True,
        "quote_turnover_24h_by_symbol": {"CHIP/USDT": "1000.0"},
    }
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    observed_at = datetime.now(tz=UTC)
    module._state.latest_final_scope_exact_snapshots = {
        "CHIP/USDT": SimpleNamespace(
            live_trade_count_24h=12000,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=12000,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="pending_archive",
        )
    }
    module._state.latest_final_scope_exact_symbols = ("CHIP/USDT",)
    module._state.latest_final_scope_exact_observed_at = observed_at
    module._state.finalized_scope_resolved_at = observed_at

    snapshot = await module.build_product_snapshot_fast_payload(
        now=observed_at,
        runtime_status={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "subscription_alive": True,
            "selected_symbols_count": 1,
            "filtered_symbols_count": 1,
            "symbols": ("CHIP/USDT",),
        },
    )

    assert snapshot["instrument_rows"] == [
        {
            "symbol": "CHIP/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": None,
        }
    ]
    assert snapshot["symbols"] == ("CHIP/USDT",)
    assert snapshot["selected_symbols_count"] == 1
    assert snapshot["filtered_symbols_count"] == 1
    assert snapshot["screen_scope_reason"] == "fallback_provisional_scope"
    assert snapshot["persistence_24h"]["persisted_trade_count_24h"] == 0
    assert snapshot["persistence_24h"]["coverage_status"] == "pending_recovery"


@pytest.mark.asyncio
async def test_module_full_snapshot_excludes_incomplete_rows_that_do_not_pass_published_trade_filter() -> None:
    runtime = _make_runtime()
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {"status": "running"}
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("CHIP/USDT",),
        coarse_selected_symbols=("CHIP/USDT",),
        selected_trade_count_24h_by_symbol=(("CHIP/USDT", 62000),),
        selected_quote_volume_24h_usd_by_symbol=(("CHIP/USDT", "1000.0"),),
        coarse_selected_quote_volume_24h_usd_by_symbol=(("CHIP/USDT", "1000.0"),),
        trade_count_filter_minimum=20000,
        instruments_passed_final_filter=1,
        discovery_signature=(
            "spot",
            "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
            float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
            str(runtime.settings.bybit_spot_quote_asset_filter),
        ),
    )
    runtime.get_bybit_spot_v2_transport_diagnostics = lambda: {
        "transport_status": "connected",
        "subscription_alive": True,
        "quote_turnover_24h_by_symbol": {"CHIP/USDT": "1000.0"},
    }
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    observed_at = datetime.now(tz=UTC)
    module._state.finalized_scope_resolved_at = observed_at
    module.get_cached_exact_trade_counts_by_symbol = AsyncMock(return_value={  # type: ignore[method-assign]
        "CHIP/USDT": SimpleNamespace(
            live_trade_count_24h=12000,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=12000,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="pending_archive",
        )
    })

    snapshot = await module.build_product_snapshot_payload(
        now=observed_at,
        runtime_status={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "subscription_alive": True,
            "selected_symbols_count": 1,
            "filtered_symbols_count": 1,
            "symbols": ("CHIP/USDT",),
        },
    )

    assert snapshot["instrument_rows"] == [
        {
            "symbol": "CHIP/USDT",
            "volume_24h_usd": "1000.0",
            "trade_count_24h": None,
        }
    ]
    assert snapshot["symbols"] == ("CHIP/USDT",)
    assert snapshot["selected_symbols_count"] == 1
    assert snapshot["filtered_symbols_count"] == 1
    assert snapshot["screen_scope_reason"] == "fallback_provisional_scope"


@pytest.mark.asyncio
async def test_module_full_snapshot_excludes_numeric_rows_below_min_trade_count() -> None:
    runtime = _make_runtime()
    runtime.settings = _make_settings(bybit_spot_universe_min_trade_count_24h=2000)
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {"status": "running"}
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("USDE/USDT", "ADA/USDT", "BTC/USDT"),
        coarse_selected_symbols=("USDE/USDT", "ADA/USDT", "BTC/USDT"),
        selected_trade_count_24h_by_symbol=(
            ("USDE/USDT", 211),
            ("ADA/USDT", 1823),
            ("BTC/USDT", 25000),
        ),
        selected_quote_volume_24h_usd_by_symbol=(
            ("USDE/USDT", "1000.0"),
            ("ADA/USDT", "2000.0"),
            ("BTC/USDT", "3000.0"),
        ),
        coarse_selected_quote_volume_24h_usd_by_symbol=(
            ("USDE/USDT", "1000.0"),
            ("ADA/USDT", "2000.0"),
            ("BTC/USDT", "3000.0"),
        ),
        trade_count_filter_minimum=2000,
        instruments_passed_final_filter=3,
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    observed_at = datetime.now(tz=UTC)
    module.get_cached_exact_trade_counts_by_symbol = AsyncMock(return_value={  # type: ignore[method-assign]
        "USDE/USDT": SimpleNamespace(
            live_trade_count_24h=211,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=211,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="hybrid",
        ),
        "ADA/USDT": SimpleNamespace(
            live_trade_count_24h=1823,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=1823,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="hybrid",
        ),
        "BTC/USDT": SimpleNamespace(
            live_trade_count_24h=1000,
            archive_trade_count_24h=24000,
            persisted_trade_count_24h=25000,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="hybrid",
        ),
    })

    snapshot = await module.build_product_snapshot_payload(
        now=observed_at,
        runtime_status={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "subscription_alive": True,
            "selected_symbols_count": 3,
            "filtered_symbols_count": 3,
            "symbols": ("USDE/USDT", "ADA/USDT", "BTC/USDT"),
        },
    )

    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "3000.0",
            "trade_count_24h": 25000,
        }
    ]
    assert snapshot["symbols"] == ("BTC/USDT",)
    assert snapshot["selected_symbols_count"] == 1
    assert snapshot["filtered_symbols_count"] == 1


@pytest.mark.asyncio
async def test_module_fast_snapshot_excludes_numeric_rows_below_min_trade_count() -> None:
    runtime = _make_runtime()
    runtime.settings = _make_settings(bybit_spot_universe_min_trade_count_24h=2000)
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("USDE/USDT", "ADA/USDT", "BTC/USDT"),
        coarse_selected_symbols=("USDE/USDT", "ADA/USDT", "BTC/USDT"),
        selected_trade_count_24h_by_symbol=(
            ("USDE/USDT", 211),
            ("ADA/USDT", 1823),
            ("BTC/USDT", 25000),
        ),
        selected_quote_volume_24h_usd_by_symbol=(
            ("USDE/USDT", "1000.0"),
            ("ADA/USDT", "2000.0"),
            ("BTC/USDT", "3000.0"),
        ),
        coarse_selected_quote_volume_24h_usd_by_symbol=(
            ("USDE/USDT", "1000.0"),
            ("ADA/USDT", "2000.0"),
            ("BTC/USDT", "3000.0"),
        ),
        trade_count_filter_minimum=2000,
        instruments_passed_final_filter=3,
    )
    runtime.get_bybit_spot_v2_transport_diagnostics = lambda: {
        "transport_status": "connected",
        "subscription_alive": True,
        "quote_turnover_24h_by_symbol": {
            "USDE/USDT": "1000.0",
            "ADA/USDT": "2000.0",
            "BTC/USDT": "3000.0",
        },
    }
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    observed_at = datetime.now(tz=UTC)
    module._state.latest_final_scope_exact_snapshots = {
        "USDE/USDT": SimpleNamespace(
            live_trade_count_24h=211,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=211,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="hybrid",
        ),
        "ADA/USDT": SimpleNamespace(
            live_trade_count_24h=1823,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=1823,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="hybrid",
        ),
        "BTC/USDT": SimpleNamespace(
            live_trade_count_24h=1000,
            archive_trade_count_24h=24000,
            persisted_trade_count_24h=25000,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="hybrid",
        ),
    }
    module._state.latest_final_scope_exact_symbols = ("USDE/USDT", "ADA/USDT", "BTC/USDT")
    module._state.latest_final_scope_exact_observed_at = observed_at

    snapshot = await module.build_product_snapshot_fast_payload(
        now=observed_at,
        runtime_status={
            "generation": "v2",
            "desired_running": True,
            "lifecycle_state": "connected_live",
            "transport_status": "connected",
            "subscription_alive": True,
            "selected_symbols_count": 3,
            "filtered_symbols_count": 3,
            "symbols": ("USDE/USDT", "ADA/USDT", "BTC/USDT"),
        },
    )

    assert snapshot["instrument_rows"] == [
        {
            "symbol": "BTC/USDT",
            "volume_24h_usd": "3000.0",
            "trade_count_24h": 25000,
        }
    ]
    assert snapshot["symbols"] == ("BTC/USDT",)
    assert snapshot["selected_symbols_count"] == 1
    assert snapshot["filtered_symbols_count"] == 1


@pytest.mark.asyncio
async def test_module_full_and_fast_snapshot_publish_same_symbol_set_for_same_exact_truth() -> None:
    runtime = _make_runtime()
    runtime.settings = _make_settings(bybit_spot_universe_min_trade_count_24h=2000)
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {"status": "running"}
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=("USDE/USDT", "ADA/USDT", "BTC/USDT", "CHIP/USDT"),
        coarse_selected_symbols=("USDE/USDT", "ADA/USDT", "BTC/USDT", "CHIP/USDT"),
        selected_trade_count_24h_by_symbol=(
            ("USDE/USDT", 211),
            ("ADA/USDT", 1823),
            ("BTC/USDT", 25000),
            ("CHIP/USDT", 40000),
        ),
        selected_quote_volume_24h_usd_by_symbol=(
            ("USDE/USDT", "1000.0"),
            ("ADA/USDT", "2000.0"),
            ("BTC/USDT", "3000.0"),
            ("CHIP/USDT", "4000.0"),
        ),
        coarse_selected_quote_volume_24h_usd_by_symbol=(
            ("USDE/USDT", "1000.0"),
            ("ADA/USDT", "2000.0"),
            ("BTC/USDT", "3000.0"),
            ("CHIP/USDT", "4000.0"),
        ),
        trade_count_filter_minimum=2000,
        instruments_passed_final_filter=4,
    )
    runtime.get_bybit_spot_v2_transport_diagnostics = lambda: {
        "transport_status": "connected",
        "subscription_alive": True,
        "quote_turnover_24h_by_symbol": {
            "USDE/USDT": "1000.0",
            "ADA/USDT": "2000.0",
            "BTC/USDT": "3000.0",
            "CHIP/USDT": "4000.0",
        },
    }
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    observed_at = datetime.now(tz=UTC)
    exact_snapshots = {
        "USDE/USDT": SimpleNamespace(
            live_trade_count_24h=211,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=211,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="hybrid",
        ),
        "ADA/USDT": SimpleNamespace(
            live_trade_count_24h=1823,
            archive_trade_count_24h=0,
            persisted_trade_count_24h=1823,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="hybrid",
        ),
        "BTC/USDT": SimpleNamespace(
            live_trade_count_24h=1000,
            archive_trade_count_24h=24000,
            persisted_trade_count_24h=25000,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="hybrid",
        ),
        "CHIP/USDT": SimpleNamespace(
            live_trade_count_24h=12000,
            archive_trade_count_24h=28000,
            persisted_trade_count_24h=40000,
            earliest_trade_at=observed_at - timedelta(hours=1),
            latest_trade_at=observed_at,
            coverage_status="hybrid",
        ),
    }
    module.get_cached_exact_trade_counts_by_symbol = AsyncMock(return_value=exact_snapshots)  # type: ignore[method-assign]
    module._state.latest_final_scope_exact_snapshots = dict(exact_snapshots)
    module._state.latest_final_scope_exact_symbols = tuple(exact_snapshots.keys())
    module._state.latest_final_scope_exact_observed_at = observed_at

    runtime_status = {
        "generation": "v2",
        "desired_running": True,
        "lifecycle_state": "connected_live",
        "transport_status": "connected",
        "subscription_alive": True,
        "selected_symbols_count": 4,
        "filtered_symbols_count": 4,
        "symbols": ("USDE/USDT", "ADA/USDT", "BTC/USDT", "CHIP/USDT"),
    }
    full_snapshot = await module.build_product_snapshot_payload(
        now=observed_at,
        runtime_status=runtime_status,
    )
    fast_snapshot = await module.build_product_snapshot_fast_payload(
        now=observed_at,
        runtime_status=runtime_status,
    )

    assert full_snapshot["symbols"] == ("BTC/USDT", "CHIP/USDT")
    assert fast_snapshot["symbols"] == ("BTC/USDT", "CHIP/USDT")
    assert full_snapshot["instrument_rows"] == fast_snapshot["instrument_rows"]
    assert full_snapshot["selected_symbols_count"] == 2
    assert fast_snapshot["selected_symbols_count"] == 2


@pytest.mark.asyncio
async def test_module_start_v2_transport_prepares_storage_before_run() -> None:
    runtime = _make_runtime()
    transport = SimpleNamespace(
        symbols=("BTC/USDT",),
        prepare_storage=AsyncMock(),
        run=AsyncMock(),
        get_transport_diagnostics=lambda: {"started": False, "transport_status": "idle", "symbols": ("BTC/USDT",)},
    )
    recovery = SimpleNamespace(
        symbols=("BTC/USDT",),
        get_recovery_diagnostics=lambda: {"started": False, "status": "waiting_for_scope", "target_symbols": ("BTC/USDT",)},
    )
    deps = _make_deps()
    deps.build_transport_connector = lambda **kwargs: transport
    deps.build_recovery_orchestrator = lambda **kwargs: recovery
    module = BybitSpotModule(runtime=runtime, deps=deps)
    resolved_scope = SimpleNamespace(
        symbols=("BTC/USDT",),
        truth=SimpleNamespace(
            selected_symbols=("BTC/USDT",),
            coarse_selected_symbols=("BTC/USDT",),
            selected_trade_count_24h_by_symbol=(("BTC/USDT", 25000),),
            trade_count_filter_minimum=20000,
            instruments_passed_final_filter=1,
            discovery_signature=(
                "spot",
                "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
                float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
                str(runtime.settings.bybit_spot_quote_asset_filter),
            ),
        ),
    )

    await module.start_v2_transport(resolved_scope=resolved_scope)

    transport.prepare_storage.assert_awaited_once()


@pytest.mark.asyncio
async def test_module_finalized_startup_does_not_restart_runtime_when_monitoring_scope_matches() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_v2_transport = SimpleNamespace(
        symbols=("BTC/USDT", "ETH/USDT"),
        get_transport_diagnostics=lambda: {
            "started": True,
            "transport_status": "connected",
            "symbols": ("BTC/USDT", "ETH/USDT"),
        },
    )
    runtime.bybit_spot_v2_transport_task = asyncio.create_task(asyncio.sleep(1))
    runtime.bybit_spot_v2_recovery = SimpleNamespace(
        symbols=("BTC/USDT", "ETH/USDT"),
        get_recovery_diagnostics=lambda: {
            "started": True,
            "status": "running",
            "target_symbols": ("BTC/USDT", "ETH/USDT"),
        },
    )
    runtime.bybit_spot_v2_recovery_task = asyncio.create_task(asyncio.sleep(1))
    deps = _make_deps()
    module = BybitSpotModule(runtime=runtime, deps=deps)
    resolved_scope = SimpleNamespace(
        symbols=("BTC/USDT", "ETH/USDT"),
        truth=SimpleNamespace(
            selected_symbols=("BTC/USDT",),
            coarse_selected_symbols=("BTC/USDT", "ETH/USDT"),
            selected_quote_volume_24h_usd_by_symbol=(("BTC/USDT", "1000.0"),),
            coarse_selected_quote_volume_24h_usd_by_symbol=(
                ("BTC/USDT", "1000.0"),
                ("ETH/USDT", "900.0"),
            ),
            selected_trade_count_24h_by_symbol=(("BTC/USDT", 1000),),
            selected_trade_count_24h_is_final=True,
            trade_count_filter_minimum=50,
            instruments_passed_final_filter=1,
            discovery_signature=(
                "spot",
                "https://api-testnet.bybit.com" if runtime.settings.bybit_testnet else "https://api.bybit.com",
                float(runtime.settings.bybit_spot_universe_min_quote_volume_24h_usd),
                str(runtime.settings.bybit_spot_quote_asset_filter),
            ),
        ),
    )
    deps.reuse_scope_if_possible = lambda **kwargs: resolved_scope  # type: ignore[assignment]
    module.resolve_final_scope = AsyncMock(return_value=resolved_scope)  # type: ignore[method-assign]
    module.start_v2_transport = AsyncMock()  # type: ignore[method-assign]
    module.start_v2_recovery = AsyncMock()  # type: ignore[method-assign]

    await module.run_finalized_startup()

    module.start_v2_transport.assert_not_awaited()
    module.start_v2_recovery.assert_not_awaited()
    assert runtime.bybit_spot_market_data_scope_summary is resolved_scope.truth

    runtime.bybit_spot_v2_transport_task.cancel()
    runtime.bybit_spot_v2_recovery_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await runtime.bybit_spot_v2_transport_task
    with contextlib.suppress(asyncio.CancelledError):
        await runtime.bybit_spot_v2_recovery_task


@pytest.mark.asyncio
async def test_module_start_v2_recovery_prepares_storage_before_run() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_v2_transport = SimpleNamespace()
    recovery = SimpleNamespace(
        prepare_storage=AsyncMock(),
        run=AsyncMock(),
    )
    runtime.bybit_spot_v2_recovery = recovery
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())

    await module.start_v2_recovery()

    recovery.prepare_storage.assert_awaited_once()


@pytest.mark.asyncio
async def test_module_retriggers_recovery_when_retry_is_scheduled() -> None:
    runtime = _make_runtime()
    runtime._started = True
    runtime.bybit_spot_v2_recovery = SimpleNamespace(
        get_recovery_diagnostics=lambda: {
            "status": "retry_scheduled",
            "reason": "persisted_live_tail_incomplete",
        }
    )
    runtime.get_bybit_spot_v2_recovery_diagnostics = lambda: {
        "status": "retry_scheduled",
        "reason": "persisted_live_tail_incomplete",
    }
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.start_v2_recovery = AsyncMock()  # type: ignore[method-assign]

    module.ensure_archive_recovery_if_needed(coverage_status="hybrid")
    await asyncio.sleep(0)

    module.start_v2_recovery.assert_awaited_once()


@pytest.mark.asyncio
async def test_module_retention_maintenance_loop_runs_periodically() -> None:
    runtime = _make_runtime()
    runtime._BYBIT_SPOT_RETENTION_MAINTENANCE_SECONDS = 0.01
    runtime.bybit_spot_v2_transport = SimpleNamespace()
    recovery = SimpleNamespace(
        prepare_storage=AsyncMock(),
        run=AsyncMock(),
        stop=AsyncMock(),
        get_recovery_diagnostics=lambda: {"status": "waiting_for_scope"},
    )
    runtime.bybit_spot_v2_recovery = recovery
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())

    await module.start_v2_recovery()
    await asyncio.sleep(0.08)
    await module.stop_runtime()

    assert recovery.prepare_storage.await_count >= 2


@pytest.mark.asyncio
async def test_module_disable_stops_retention_maintenance_loop() -> None:
    runtime = _make_runtime()
    runtime._BYBIT_SPOT_RETENTION_MAINTENANCE_SECONDS = 0.01
    runtime.bybit_spot_v2_transport = SimpleNamespace(stop=AsyncMock())
    runtime.bybit_spot_v2_recovery = SimpleNamespace(
        prepare_storage=AsyncMock(),
        run=AsyncMock(),
        stop=AsyncMock(),
        get_recovery_diagnostics=lambda: {"status": "waiting_for_scope"},
    )
    runtime.bybit_spot_v2_transport_task = asyncio.create_task(asyncio.sleep(1))
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module._state.retention_maintenance_task = asyncio.create_task(asyncio.sleep(1))
    module.schedule_product_snapshot_refresh = Mock()  # type: ignore[method-assign]

    await module.set_enabled(False)

    assert module._state.retention_maintenance_task is None


@pytest.mark.asyncio
async def test_module_start_runtime_awaits_finalized_startup_when_truth_is_not_final() -> None:
    runtime = _make_runtime()
    runtime.bybit_spot_market_data_scope_summary = SimpleNamespace(
        selected_symbols=(),
        coarse_selected_symbols=("BTC/USDT",),
        instruments_passed_final_filter=None,
        trade_count_filter_minimum=20000,
        discovery_signature=("stale",),
    )
    module = BybitSpotModule(runtime=runtime, deps=_make_deps())
    module.await_finalized_startup = AsyncMock()  # type: ignore[method-assign]

    await module.start_runtime()

    module.await_finalized_startup.assert_awaited_once()
