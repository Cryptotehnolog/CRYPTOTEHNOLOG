from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Awaitable, Callable

from cryptotechnolog.config.logging import get_logger
from cryptotechnolog.config.settings import Settings
from cryptotechnolog.live_feed.bybit_spot_cache_contracts import (
    _is_product_snapshot_cache_usable as _cache_contracts_is_product_snapshot_cache_usable,
)
from cryptotechnolog.live_feed.bybit_spot_exact_cache_access import (
    _get_cached_exact_trade_counts_if_usable as _exact_cache_access_get_cached_exact_trade_counts_if_usable,
    _get_publishable_exact_snapshots as _exact_cache_access_get_publishable_exact_snapshots,
)
from cryptotechnolog.live_feed.bybit_spot_diagnostics_contracts import (
    _build_product_snapshot_contract_flags as _diagnostics_build_product_snapshot_contract_flags,
    _build_runtime_contract_flags as _diagnostics_build_runtime_contract_flags,
    _resolve_product_snapshot_reason as _diagnostics_resolve_product_snapshot_reason,
    _resolve_runtime_screen_scope_reason as _diagnostics_resolve_runtime_screen_scope_reason,
)
from cryptotechnolog.live_feed.bybit_spot_scope_resolution import (
    _resolve_fallback_snapshot_symbols_from_truth as _scope_resolution_resolve_fallback_snapshot_symbols_from_truth,
    _resolve_scope_trade_counts_from_truth as _scope_resolution_resolve_scope_trade_counts_from_truth,
    _resolve_snapshot_symbols_from_truth as _scope_resolution_resolve_snapshot_symbols_from_truth,
)
from cryptotechnolog.live_feed.bybit_spot_snapshot_contracts import (
    _build_fallback_snapshot_contract as _snapshot_contracts_build_fallback_snapshot_contract,
    _build_published_snapshot_contract as _snapshot_contracts_build_published_snapshot_contract,
    _fallback_snapshot_contract_is_consistent as _snapshot_contracts_fallback_snapshot_contract_is_consistent,
    _published_snapshot_contract_is_consistent as _snapshot_contracts_published_snapshot_contract_is_consistent,
    _resolve_exact_window_coverage_status as _snapshot_contracts_resolve_exact_window_coverage_status,
    _snapshot_passes_final_trade_filter_for_publication as _snapshot_contracts_snapshot_passes_final_trade_filter_for_publication,
)
from cryptotechnolog.live_feed.bybit_spot_v2_persisted_query import BybitSpotV2PersistedQueryService


_BYBIT_SPOT_FINAL_SCOPE_REFRESH_SECONDS = 30.0
_BYBIT_SPOT_STABLE_FINAL_SCOPE_REFRESH_SECONDS = 90.0
_BYBIT_SPOT_INCOMPLETE_COVERAGE_RETENTION_SECONDS = 30.0
_BYBIT_SPOT_EXACT_QUERY_BATCH_TIMEOUT_SECONDS = 20.0
_BYBIT_SPOT_FINALIZED_STARTUP_RETRY_BACKOFF_SECONDS = 10.0
_BYBIT_SPOT_EXACT_CACHE_RETRY_BACKOFF_SECONDS = 10.0
_BYBIT_SPOT_BROWSER_EXACT_WAIT_SECONDS = 4.0
_BYBIT_SPOT_BROWSER_STARTUP_EXACT_WAIT_SECONDS = 10.0
_BYBIT_SPOT_RECOVERY_RETRY_BACKOFF_SECONDS = 30.0
_BYBIT_SPOT_RETENTION_MAINTENANCE_SECONDS = 3600.0


def _resolve_exact_query_profile(*, symbol_count: int) -> tuple[int, int]:
    if symbol_count >= 256:
        return (512, 1)
    if symbol_count >= 128:
        return (256, 1)
    if symbol_count >= 64:
        return (128, 1)
    return (24, 4)


def _resolve_operator_message_age_ms(transport: dict[str, object]) -> int | None:
    raw_message_age_ms = transport.get("message_age_ms")
    if isinstance(raw_message_age_ms, int):
        return raw_message_age_ms
    raw_last_message_at = transport.get("last_message_at")
    if not isinstance(raw_last_message_at, str):
        return None
    with contextlib.suppress(ValueError):
        last_message_at = datetime.fromisoformat(raw_last_message_at)
        return max(0, int((datetime.now(tz=UTC) - last_message_at).total_seconds() * 1000))
    return None


def _resolve_operator_transport_rtt_ms(transport: dict[str, object]) -> int | None:
    raw_transport_rtt_ms = transport.get("transport_rtt_ms")
    transport_rtt_ms = raw_transport_rtt_ms if isinstance(raw_transport_rtt_ms, int) else None
    if str(transport.get("transport_status", "idle")) != "connected":
        return transport_rtt_ms
    if not bool(transport.get("subscription_alive", False)):
        return transport_rtt_ms
    message_age_ms = _resolve_operator_message_age_ms(transport)
    if message_age_ms is None:
        return transport_rtt_ms
    if transport_rtt_ms is None:
        return message_age_ms
    if message_age_ms <= 2000:
        return min(transport_rtt_ms, message_age_ms)
    return transport_rtt_ms


def _replace_truth(truth: Any, /, **changes: Any) -> Any:
    if hasattr(truth, "__dataclass_fields__"):
        return replace(truth, **changes)
    values = dict(vars(truth))
    values.update(changes)
    return SimpleNamespace(**values)


def _resolve_spot_min_quote_volume_24h_usd(*, settings: Settings) -> float:
    return float(settings.bybit_spot_universe_min_quote_volume_24h_usd)


def _resolve_spot_min_trade_count_24h(*, settings: Settings) -> int:
    return int(settings.bybit_spot_universe_min_trade_count_24h)


def _resolve_spot_quote_asset_filter(*, settings: Settings) -> str:
    return str(settings.bybit_spot_quote_asset_filter)


def _build_spot_discovery_signature(*, settings: Settings) -> tuple[object, ...]:
    return (
        "spot",
        "https://api-testnet.bybit.com" if settings.bybit_testnet else "https://api.bybit.com",
        _resolve_spot_min_quote_volume_24h_usd(settings=settings),
        _resolve_spot_quote_asset_filter(settings=settings),
    )


def _is_product_snapshot_publishable(runtime_status: dict[str, object]) -> bool:
    lifecycle_state = (
        str(runtime_status.get("lifecycle_state"))
        if isinstance(runtime_status.get("lifecycle_state"), str)
        else ""
    )
    if lifecycle_state == "connected_live":
        return True
    if str(runtime_status.get("transport_status", "idle")) != "connected":
        return False
    if not bool(runtime_status.get("subscription_alive", False)):
        return False
    selected_symbols_count = (
        int(runtime_status.get("selected_symbols_count", 0))
        if isinstance(runtime_status.get("selected_symbols_count"), int)
        else 0
    )
    if selected_symbols_count <= 0:
        return False
    if bool(runtime_status.get("trade_seen", False)):
        return True
    persisted_trade_count = (
        int(runtime_status.get("persisted_trade_count", 0))
        if isinstance(runtime_status.get("persisted_trade_count"), int)
        else 0
    )
    return persisted_trade_count > 0


def _spot_scope_truth_is_final_for_settings(*, settings: Settings, truth: Any) -> bool:
    if getattr(truth, "discovery_signature", None) != _build_spot_discovery_signature(
        settings=settings
    ):
        return False
    expected_min_trade_count = _resolve_spot_min_trade_count_24h(settings=settings)
    if int(getattr(truth, "trade_count_filter_minimum", 0)) != expected_min_trade_count:
        return False
    if getattr(truth, "instruments_passed_final_filter", None) is None:
        return False
    selected_symbols = tuple(str(symbol) for symbol in getattr(truth, "selected_symbols", ()) or ())
    coarse_selected_symbols = tuple(
        str(symbol) for symbol in getattr(truth, "coarse_selected_symbols", ()) or ()
    )
    if expected_min_trade_count <= 0:
        return bool(coarse_selected_symbols or selected_symbols)
    selected_trade_counts = {
        str(symbol): int(trade_count)
        for symbol, trade_count in getattr(truth, "selected_trade_count_24h_by_symbol", ()) or ()
        if isinstance(symbol, str)
    }
    if getattr(truth, "selected_trade_count_24h_is_final", None) is not True:
        return False
    instruments_passed_final_filter = getattr(truth, "instruments_passed_final_filter", None)
    if not selected_symbols:
        return (
            isinstance(instruments_passed_final_filter, int)
            and instruments_passed_final_filter == 0
            and not selected_trade_counts
            and (
                not coarse_selected_symbols
                or getattr(truth, "selected_trade_count_24h_empty_scope_confirmed", None)
                is True
            )
        )
    if len(selected_trade_counts) != len(selected_symbols):
        return False
    return all(
        int(selected_trade_counts.get(symbol, -1)) >= expected_min_trade_count
        for symbol in selected_symbols
    )


def _resolve_snapshot_symbols_from_truth(*, truth: Any | None, settings: Settings) -> tuple[str, ...]:
    return _scope_resolution_resolve_snapshot_symbols_from_truth(
        truth=truth,
        settings=settings,
    )


def _resolve_fallback_snapshot_symbols_from_truth(*, truth: Any | None) -> tuple[str, ...]:
    return _scope_resolution_resolve_fallback_snapshot_symbols_from_truth(
        truth=truth,
    )


def _resolve_scope_trade_counts_from_truth(*, truth: Any | None) -> dict[str, int]:
    return _scope_resolution_resolve_scope_trade_counts_from_truth(
        truth=truth,
    )


def _resolve_exact_window_coverage_status(
    *,
    observed_at: datetime,
    window_started_at: datetime,
    live_trade_count_24h: int,
    archive_trade_count_24h: int,
    symbol_coverage_statuses: tuple[str, ...] = (),
) -> str:
    return _snapshot_contracts_resolve_exact_window_coverage_status(
        observed_at=observed_at,
        window_started_at=window_started_at,
        live_trade_count_24h=live_trade_count_24h,
        archive_trade_count_24h=archive_trade_count_24h,
        symbol_coverage_statuses=symbol_coverage_statuses,
    )


def _snapshot_passes_final_trade_filter_for_publication(
    *,
    exact_snapshot: Any,
    min_trade_count_24h: int,
    module: "BybitSpotModule",
) -> bool:
    return _snapshot_contracts_snapshot_passes_final_trade_filter_for_publication(
        exact_snapshot=exact_snapshot,
        min_trade_count_24h=min_trade_count_24h,
        module=module,
    )


def _build_published_snapshot_contract(
    *,
    candidate_symbols: tuple[str, ...],
    exact_trade_by_symbol: dict[str, Any],
    volume_by_symbol: dict[str, object],
    min_trade_count_24h: int,
    module: "BybitSpotModule",
    observed_at: datetime,
) -> tuple[tuple[str, ...], list[dict[str, object]], dict[str, object]]:
    return _snapshot_contracts_build_published_snapshot_contract(
        candidate_symbols=candidate_symbols,
        exact_trade_by_symbol=exact_trade_by_symbol,
        volume_by_symbol=volume_by_symbol,
        min_trade_count_24h=min_trade_count_24h,
        module=module,
        observed_at=observed_at,
    )


def _published_snapshot_contract_is_consistent(
    *,
    published_symbols: tuple[str, ...],
    instrument_rows: list[dict[str, object]],
    min_trade_count_24h: int,
    coverage_status: str,
) -> bool:
    return _snapshot_contracts_published_snapshot_contract_is_consistent(
        published_symbols=published_symbols,
        instrument_rows=instrument_rows,
        min_trade_count_24h=min_trade_count_24h,
        coverage_status=coverage_status,
    )


def _build_fallback_snapshot_contract(
    *,
    provisional_symbols: tuple[str, ...],
    volume_by_symbol: dict[str, object],
    module: "BybitSpotModule",
) -> tuple[tuple[str, ...], list[dict[str, object]], dict[str, object]]:
    return _snapshot_contracts_build_fallback_snapshot_contract(
        provisional_symbols=provisional_symbols,
        volume_by_symbol=volume_by_symbol,
        module=module,
    )


def _should_publish_fallback_snapshot_contract(
    *,
    candidate_symbols: tuple[str, ...],
    fallback_symbols: tuple[str, ...],
    published_symbols: tuple[str, ...],
    exact_trade_by_symbol: dict[str, Any],
    module: "BybitSpotModule",
) -> bool:
    if not fallback_symbols or published_symbols or not candidate_symbols:
        return False
    if not module.is_trade_truth_coverage_incomplete():
        return False
    return any(
        (symbol_snapshot := exact_trade_by_symbol.get(symbol)) is not None
        and module.is_snapshot_coverage_incomplete(
            coverage_status=str(getattr(symbol_snapshot, "coverage_status", "empty"))
        )
        for symbol in candidate_symbols
    )


def _fallback_snapshot_contract_is_consistent(
    *,
    provisional_symbols: tuple[str, ...],
    instrument_rows: list[dict[str, object]],
) -> bool:
    return _snapshot_contracts_fallback_snapshot_contract_is_consistent(
        provisional_symbols=provisional_symbols,
        instrument_rows=instrument_rows,
    )


def _resolve_runtime_screen_scope_reason(
    *,
    strict_published_symbols: tuple[str, ...],
    resolved_symbols: tuple[str, ...],
    coarse_symbols: tuple[str, ...],
    screen_symbols: tuple[str, ...],
    trade_truth_incomplete: bool,
) -> str:
    return _diagnostics_resolve_runtime_screen_scope_reason(
        strict_published_symbols=strict_published_symbols,
        resolved_symbols=resolved_symbols,
        coarse_symbols=coarse_symbols,
        screen_symbols=screen_symbols,
        trade_truth_incomplete=trade_truth_incomplete,
    )


def _build_runtime_contract_flags(
    *,
    strict_published_symbols: tuple[str, ...],
    coarse_symbols: tuple[str, ...],
    screen_symbols: tuple[str, ...],
    trade_truth_incomplete: bool,
) -> dict[str, bool]:
    return _diagnostics_build_runtime_contract_flags(
        strict_published_symbols=strict_published_symbols,
        coarse_symbols=coarse_symbols,
        screen_symbols=screen_symbols,
        trade_truth_incomplete=trade_truth_incomplete,
    )


def _resolve_product_snapshot_reason(
    *,
    symbols: tuple[str, ...],
    instrument_rows: list[dict[str, object]],
    persistence_24h: dict[str, object],
    runtime_status: dict[str, object],
) -> str:
    return _diagnostics_resolve_product_snapshot_reason(
        symbols=symbols,
        instrument_rows=instrument_rows,
        persistence_24h=persistence_24h,
        runtime_status=runtime_status,
    )


def _build_product_snapshot_contract_flags(
    *,
    symbols: tuple[str, ...],
    instrument_rows: list[dict[str, object]],
    persistence_24h: dict[str, object],
    runtime_status: dict[str, object],
    min_trade_count_24h: int,
) -> dict[str, bool]:
    return _diagnostics_build_product_snapshot_contract_flags(
        symbols=symbols,
        instrument_rows=instrument_rows,
        persistence_24h=persistence_24h,
        runtime_status=runtime_status,
        min_trade_count_24h=min_trade_count_24h,
    )


def _resolve_monitoring_scope(*, resolved_scope: Any, monitoring_symbols: tuple[str, ...]) -> Any:
    if not monitoring_symbols:
        return resolved_scope
    current_symbols = tuple(str(symbol) for symbol in getattr(resolved_scope, "symbols", ()) or ())
    if current_symbols == monitoring_symbols:
        return resolved_scope
    return replace(resolved_scope, symbols=monitoring_symbols)


def _runtime_scope_symbols(connector: Any, diagnostics: dict[str, object], *, diagnostics_attr: str) -> tuple[str, ...]:
    connector_symbols = getattr(connector, "symbols", None)
    if connector_symbols:
        return tuple(str(symbol) for symbol in connector_symbols if isinstance(symbol, str))
    return tuple(
        str(symbol)
        for symbol in diagnostics.get(diagnostics_attr, ())
        if isinstance(symbol, str)
    )


async def query_exact_trade_counts_by_symbol_uncached(
    *,
    db_manager: Any,
    symbols: tuple[str, ...],
    observed_at: datetime,
    window_hours: int = 24,
    chunk_size: int = 24,
    batch_concurrency: int = 4,
) -> dict[str, Any]:
    if not symbols:
        return {}
    service = BybitSpotV2PersistedQueryService(db_manager)

    try:
        exact_trade_by_symbol: dict[str, Any] = {}
        resolved_batch_concurrency = max(1, int(batch_concurrency))
        symbol_chunks = [
            symbols[offset : offset + chunk_size]
            for offset in range(0, len(symbols), chunk_size)
        ]
        for batch_offset in range(0, len(symbol_chunks), resolved_batch_concurrency):
            chunk_batch = symbol_chunks[batch_offset : batch_offset + resolved_batch_concurrency]
            snapshots = await asyncio.wait_for(
                asyncio.gather(
                    *(
                        service.query_rolling_window(
                            symbols=symbol_chunk,
                            observed_at=observed_at,
                            window_hours=window_hours,
                        )
                        for symbol_chunk in chunk_batch
                    )
                ),
                timeout=_BYBIT_SPOT_EXACT_QUERY_BATCH_TIMEOUT_SECONDS,
            )
            for snapshot in snapshots:
                for symbol_snapshot in snapshot.symbols:
                    exact_trade_by_symbol[symbol_snapshot.normalized_symbol] = symbol_snapshot
    except Exception as exc:
        if type(exc).__name__ not in {"DiskFullError", "TimeoutError"}:
            raise
        if batch_concurrency > 1:
            return await query_exact_trade_counts_by_symbol_uncached(
                db_manager=db_manager,
                symbols=symbols,
                observed_at=observed_at,
                window_hours=window_hours,
                chunk_size=chunk_size,
                batch_concurrency=max(1, batch_concurrency // 2),
            )
        if chunk_size <= 1:
            raise
        return await query_exact_trade_counts_by_symbol_uncached(
            db_manager=db_manager,
            symbols=symbols,
            observed_at=observed_at,
            window_hours=window_hours,
            chunk_size=max(1, chunk_size // 2),
            batch_concurrency=1,
        )
    return exact_trade_by_symbol


async def query_exact_trade_count_snapshots_by_symbol_uncached(
    *,
    db_manager: Any,
    symbols: tuple[str, ...],
    observed_at: datetime,
    window_hours: int = 24,
    chunk_size: int = 24,
    batch_concurrency: int = 4,
) -> dict[str, Any]:
    if not symbols:
        return {}
    service = BybitSpotV2PersistedQueryService(db_manager)

    try:
        trade_snapshots_by_symbol: dict[str, Any] = {}
        resolved_batch_concurrency = max(1, int(batch_concurrency))
        symbol_chunks = [
            symbols[offset : offset + chunk_size]
            for offset in range(0, len(symbols), chunk_size)
        ]
        for batch_offset in range(0, len(symbol_chunks), resolved_batch_concurrency):
            chunk_batch = symbol_chunks[batch_offset : batch_offset + resolved_batch_concurrency]
            chunk_snapshots = await asyncio.wait_for(
                asyncio.gather(
                    *(
                        service.query_rolling_trade_count_snapshots(
                            symbols=symbol_chunk,
                            observed_at=observed_at,
                            window_hours=window_hours,
                        )
                        for symbol_chunk in chunk_batch
                    )
                ),
                timeout=_BYBIT_SPOT_EXACT_QUERY_BATCH_TIMEOUT_SECONDS,
            )
            for snapshot_batch in chunk_snapshots:
                trade_snapshots_by_symbol.update(snapshot_batch)
    except Exception as exc:
        if type(exc).__name__ not in {"DiskFullError", "TimeoutError"}:
            raise
        if batch_concurrency > 1:
            return await query_exact_trade_count_snapshots_by_symbol_uncached(
                db_manager=db_manager,
                symbols=symbols,
                observed_at=observed_at,
                window_hours=window_hours,
                chunk_size=chunk_size,
                batch_concurrency=max(1, batch_concurrency // 2),
            )
        if chunk_size <= 1:
            raise
        return await query_exact_trade_count_snapshots_by_symbol_uncached(
            db_manager=db_manager,
            symbols=symbols,
            observed_at=observed_at,
            window_hours=window_hours,
            chunk_size=max(1, chunk_size // 2),
            batch_concurrency=1,
        )
    return trade_snapshots_by_symbol


async def query_exact_trade_count_totals_by_symbol_uncached(
    *,
    db_manager: Any,
    symbols: tuple[str, ...],
    observed_at: datetime,
    window_hours: int = 24,
    chunk_size: int = 24,
) -> dict[str, int]:
    snapshots = await query_exact_trade_count_snapshots_by_symbol_uncached(
        db_manager=db_manager,
        symbols=symbols,
        observed_at=observed_at,
        window_hours=window_hours,
        chunk_size=chunk_size,
    )
    return {
        str(symbol): int(getattr(snapshot, "persisted_trade_count_24h", 0))
        for symbol, snapshot in snapshots.items()
    }


@dataclass(slots=True)
class BybitSpotModuleDeps:
    build_connector_screen_projection: Callable[..., dict[str, object]]
    resolve_runtime_generation: Callable[..., str]
    build_runtime_signature: Callable[..., tuple[object, ...]]
    build_trade_ledger_query_service: Callable[..., Any]
    reuse_scope_if_possible: Callable[..., Any]
    resolve_canonical_scope_async: Callable[..., Awaitable[Any]]
    build_runtime_apply_truth: Callable[..., Any]
    build_selected_connector: Callable[..., Any]
    build_transport_connector: Callable[..., Any]
    build_recovery_orchestrator: Callable[..., Any]
    resolve_disabled_toggle_scope: Callable[..., Any]
    resolve_monitoring_symbols: Callable[..., tuple[str, ...]]
    resolve_min_trade_count_24h: Callable[..., int]
    resolve_spot_primary_lifecycle_state: Callable[..., str]
    join_timeout_seconds: float
    query_exact_trade_counts_uncached: Callable[..., Awaitable[dict[str, Any]]]
    query_exact_trade_count_snapshots_uncached: Callable[..., Awaitable[dict[str, Any]]]
    update_settings: Callable[[dict[str, object]], Settings]


@dataclass(slots=True)
class _BybitSpotModuleState:
    finalized_scope_resolved_at: datetime | None = None
    finalized_startup_task: asyncio.Task[None] | None = None
    finalized_startup_retry_after: datetime | None = None
    scope_refresh_task: asyncio.Task[None] | None = None
    exact_trade_cache_by_symbol: dict[str, Any] | None = None
    exact_trade_cache_symbols: tuple[str, ...] | None = None
    exact_trade_cache_observed_at: datetime | None = None
    exact_trade_cache_expires_at: datetime | None = None
    exact_trade_cache_refresh_task: asyncio.Task[None] | None = None
    exact_trade_cache_retry_after: datetime | None = None
    recovery_retry_after: datetime | None = None
    retention_maintenance_task: asyncio.Task[None] | None = None
    product_snapshot_cache_payload: dict[str, object] | None = None
    product_snapshot_cache_expires_at: datetime | None = None
    product_snapshot_refresh_task: asyncio.Task[None] | None = None
    final_scope_refresh_seconds: float = _BYBIT_SPOT_FINAL_SCOPE_REFRESH_SECONDS
    stable_final_scope_refresh_seconds: float = _BYBIT_SPOT_STABLE_FINAL_SCOPE_REFRESH_SECONDS
    retention_maintenance_seconds: float = _BYBIT_SPOT_RETENTION_MAINTENANCE_SECONDS
    incomplete_coverage_retention_seconds: float = (
        _BYBIT_SPOT_INCOMPLETE_COVERAGE_RETENTION_SECONDS
    )
    latest_final_scope_exact_snapshots: dict[str, Any] | None = None
    latest_final_scope_exact_symbols: tuple[str, ...] | None = None
    latest_final_scope_exact_observed_at: datetime | None = None


class BybitSpotModule:
    def __init__(self, *, runtime: Any, deps: BybitSpotModuleDeps) -> None:
        self.runtime = runtime
        self.deps = deps
        self._state = _BybitSpotModuleState(
            final_scope_refresh_seconds=float(
                getattr(
                    runtime,
                    "_BYBIT_SPOT_FINAL_SCOPE_REFRESH_SECONDS",
                    _BYBIT_SPOT_FINAL_SCOPE_REFRESH_SECONDS,
                )
            ),
            stable_final_scope_refresh_seconds=float(
                getattr(
                    runtime,
                    "_BYBIT_SPOT_STABLE_FINAL_SCOPE_REFRESH_SECONDS",
                    _BYBIT_SPOT_STABLE_FINAL_SCOPE_REFRESH_SECONDS,
                )
            ),
            retention_maintenance_seconds=float(
                getattr(
                    runtime,
                    "_BYBIT_SPOT_RETENTION_MAINTENANCE_SECONDS",
                    _BYBIT_SPOT_RETENTION_MAINTENANCE_SECONDS,
                )
            ),
            incomplete_coverage_retention_seconds=float(
                getattr(
                    runtime,
                    "_BYBIT_SPOT_INCOMPLETE_COVERAGE_RETENTION_SECONDS",
                    _BYBIT_SPOT_INCOMPLETE_COVERAGE_RETENTION_SECONDS,
                )
            ),
        )

    def _get_publishable_exact_snapshots(
        self,
        *,
        symbols: tuple[str, ...],
    ) -> dict[str, Any] | None:
        return _exact_cache_access_get_publishable_exact_snapshots(
            symbols=symbols,
            cached_exact=self._state.exact_trade_cache_by_symbol,
            latest_symbols=self._state.latest_final_scope_exact_symbols,
            latest_snapshots=self._state.latest_final_scope_exact_snapshots,
        )

    def get_connector_screen_projection(self) -> dict[str, object]:
        configured_enabled = bool(
            getattr(self.runtime.settings, "bybit_spot_market_data_connector_enabled", False)
        )
        projection = self.deps.build_connector_screen_projection(
            connector=self.runtime.bybit_spot_market_data_connector,
            exchange="bybit_spot",
            enabled=configured_enabled,
            scope_truth=self.runtime.bybit_spot_market_data_scope_summary,
            apply_truth=self.runtime.bybit_spot_market_data_apply_truth,
        )
        scope_truth = self.runtime.bybit_spot_market_data_scope_summary
        if self.deps.resolve_runtime_generation(contour="spot") == "v2":
            transport = self.runtime.get_bybit_spot_v2_transport_diagnostics()
            recovery = self.runtime.get_bybit_spot_v2_recovery_diagnostics()
            has_transport = self.runtime.bybit_spot_v2_transport is not None
            has_recovery = self.runtime.bybit_spot_v2_recovery is not None
            symbols = (
                tuple(str(symbol) for symbol in scope_truth.selected_symbols)
                if scope_truth is not None and scope_truth.selected_symbols
                else tuple(
                    str(symbol)
                    for symbol in transport.get("symbols", ())
                    if isinstance(symbol, str)
                )
            )
            projection.update(
                {
                    "exchange": "bybit_spot",
                    "symbols": symbols,
                    "transport_status": str(transport.get("transport_status", "idle")),
                    "subscription_alive": bool(transport.get("subscription_alive", False)),
                    "trade_seen": bool(transport.get("trade_seen", False)),
                    "orderbook_seen": bool(transport.get("orderbook_seen", False)),
                    "transport_rtt_ms": _resolve_operator_transport_rtt_ms(transport),
                    "last_message_at": transport.get("last_message_at")
                    if isinstance(transport.get("last_message_at"), str)
                    else None,
                    "message_age_ms": _resolve_operator_message_age_ms(transport),
                    "retry_count": transport.get("retry_count")
                    if isinstance(transport.get("retry_count"), int)
                    else None,
                    "started": (
                        bool(transport.get("started", False))
                        if has_transport
                        else projection.get("started", False)
                    ),
                    "ready": (
                        bool(transport.get("ready", False))
                        if has_transport
                        else projection.get("ready", False)
                    ),
                    "lifecycle_state": transport.get("lifecycle_state")
                    if has_transport and isinstance(transport.get("lifecycle_state"), str)
                    else projection.get("lifecycle_state"),
                    "recovery_status": recovery.get("status")
                    if has_recovery and isinstance(recovery.get("status"), str)
                    else projection.get("recovery_status"),
                    "historical_recovery_reason": recovery.get("reason")
                    if has_recovery and isinstance(recovery.get("reason"), str)
                    else projection.get("historical_recovery_reason"),
                }
            )
        if (
            scope_truth is not None
            and int(scope_truth.trade_count_filter_minimum) > 0
            and not scope_truth.selected_symbols
            and projection.get("derived_trade_count_backfill_status") is None
        ):
            projection["derived_trade_count_backfill_status"] = "not_needed"
            projection["derived_trade_count_backfill_needed"] = False
            projection["trade_count_filter_ready"] = True
        return projection

    def is_trade_truth_coverage_incomplete(self) -> bool:
        recovery = self.runtime.get_bybit_spot_v2_recovery_diagnostics()
        status = str(recovery.get("status", "idle"))
        reason = str(recovery.get("reason", ""))
        if status in {"waiting_for_scope", "idle"}:
            scope_truth = self.runtime.bybit_spot_market_data_scope_summary
            desired_running = bool(
                getattr(self.runtime.settings, "bybit_spot_market_data_connector_enabled", False)
            )
            if desired_running and (
                scope_truth is None
                or not _spot_scope_truth_is_final_for_settings(
                    settings=self.runtime.settings,
                    truth=scope_truth,
                )
                or self._state.finalized_scope_resolved_at is None
            ):
                return True
        return status in {"planned", "running", "failed", "retry_scheduled"} or reason in {
            "coverage_incomplete",
            "persisted_live_tail_incomplete",
        }

    def is_snapshot_coverage_incomplete(self, *, coverage_status: str) -> bool:
        if coverage_status == "pending_archive":
            return True
        if coverage_status == "empty":
            return self.is_trade_truth_coverage_incomplete()
        if coverage_status in {"live_only", "pending_live", "pending_recovery"}:
            return self.is_trade_truth_coverage_incomplete()
        return False

    def ensure_archive_recovery_if_needed(self, *, coverage_status: str) -> None:
        recovery = self.runtime.get_bybit_spot_v2_recovery_diagnostics()
        recovery_status = str(recovery.get("status", "idle"))
        recovery_reason = str(recovery.get("reason", ""))
        retry_needed = (
            coverage_status == "pending_archive"
            or recovery_status == "retry_scheduled"
            or (
                recovery_status == "failed"
                and recovery_reason == "persisted_live_tail_incomplete"
            )
        )
        if not retry_needed:
            return
        if not self.runtime._started:
            return
        if self.runtime.bybit_spot_v2_recovery is None:
            return
        if (
            self.runtime.bybit_spot_v2_recovery_task is not None
            and not self.runtime.bybit_spot_v2_recovery_task.done()
        ):
            return
        retry_after = self._state.recovery_retry_after
        if isinstance(retry_after, datetime) and retry_after > datetime.now(tz=UTC):
            return
        self._state.recovery_retry_after = datetime.now(tz=UTC) + timedelta(
            seconds=_BYBIT_SPOT_RECOVERY_RETRY_BACKOFF_SECONDS
        )
        asyncio.create_task(
            self.start_v2_recovery(),
            name="production_bybit_spot_v2_recovery_retry",
        )

    def resolve_persistence_coverage_status(
        self,
        *,
        live_trade_count_24h: int,
        archive_trade_count_24h: int,
    ) -> str:
        if self.is_trade_truth_coverage_incomplete():
            if live_trade_count_24h > 0 and archive_trade_count_24h == 0:
                return "pending_archive"
            if live_trade_count_24h > 0 and archive_trade_count_24h > 0:
                return "pending_recovery"
            if archive_trade_count_24h > 0:
                return "pending_live"
        if live_trade_count_24h > 0 and archive_trade_count_24h > 0:
            return "hybrid"
        if archive_trade_count_24h > 0:
            return "archive_only"
        if live_trade_count_24h > 0:
            return "live_only"
        return "empty"

    def should_retain_symbol_during_incomplete_coverage(
        self,
        *,
        symbol: str,
        coverage_status: str,
    ) -> bool:
        if not self.is_snapshot_coverage_incomplete(coverage_status=coverage_status):
            return False
        if not self.is_trade_truth_coverage_incomplete():
            return False
        scope_truth = self.runtime.bybit_spot_market_data_scope_summary
        if scope_truth is None or symbol not in set(scope_truth.selected_symbols):
            return False
        last_resolved_at = self._state.finalized_scope_resolved_at
        if not isinstance(last_resolved_at, datetime):
            return False
        retention_seconds = int(self._state.incomplete_coverage_retention_seconds)
        return (datetime.now(tz=UTC) - last_resolved_at).total_seconds() < retention_seconds

    async def run_finalized_startup(self) -> None:
        try:
            get_logger(__name__).info("Bybit spot v2 finalized startup started")
            existing_truth = self.runtime.bybit_spot_market_data_scope_summary
            get_logger(__name__).info("Bybit spot v2 finalized startup resolving canonical scope")
            resolved_scope = self.deps.reuse_scope_if_possible(
                settings=self.runtime.settings,
                contour="spot",
                existing_truth=existing_truth,
            ) or await self.deps.resolve_canonical_scope_async(
                settings=self.runtime.settings,
                capture_discovery_errors=True,
            )
            get_logger(__name__).info(
                "Bybit spot v2 finalized startup canonical scope resolved",
                coarse_symbols=len(getattr(resolved_scope.truth, "coarse_selected_symbols", ()) or ()),
                selected_symbols=len(getattr(resolved_scope.truth, "selected_symbols", ()) or ()),
            )
            get_logger(__name__).info("Bybit spot v2 finalized startup resolving final scope")
            try:
                resolved_scope = await self.resolve_final_scope(
                    settings=self.runtime.settings,
                    resolved_scope=resolved_scope,
                )
            except TimeoutError:
                self.runtime.bybit_spot_market_data_scope_summary = resolved_scope.truth
                self.runtime.bybit_spot_market_data_apply_truth = self.deps.build_runtime_apply_truth(
                    settings=self.runtime.settings,
                    contour="spot",
                    resolved_scope=resolved_scope,
                    connector=self.runtime.bybit_spot_market_data_connector,
                )
                self._state.finalized_startup_retry_after = datetime.now(tz=UTC) + timedelta(
                    seconds=_BYBIT_SPOT_FINALIZED_STARTUP_RETRY_BACKOFF_SECONDS
                )
                await self.start_v2_transport(resolved_scope=resolved_scope)
                await self.start_v2_recovery()
                self.schedule_exact_trade_cache_refresh(
                    symbols=_resolve_snapshot_symbols_from_truth(
                        truth=resolved_scope.truth,
                        settings=self.runtime.settings,
                    )
                )
                self.mark_product_snapshot_stale()
                get_logger(__name__).warning(
                    "Bybit spot v2 finalized startup deferred until exact cache warmup",
                    coarse_symbols=len(getattr(resolved_scope.truth, "coarse_selected_symbols", ()) or ()),
                    selected_symbols=len(getattr(resolved_scope.truth, "selected_symbols", ()) or ()),
                )
                return
            get_logger(__name__).info(
                "Bybit spot v2 finalized startup final scope resolved",
                selected_symbols=len(getattr(resolved_scope.truth, "selected_symbols", ()) or ()),
                selected_trade_counts=len(
                    getattr(resolved_scope.truth, "selected_trade_count_24h_by_symbol", ()) or ()
                ),
            )
            self.runtime.bybit_spot_market_data_scope_summary = resolved_scope.truth
            self.runtime.bybit_spot_market_data_apply_truth = self.deps.build_runtime_apply_truth(
                settings=self.runtime.settings,
                contour="spot",
                resolved_scope=resolved_scope,
                connector=self.runtime.bybit_spot_market_data_connector,
            )
            self._seed_exact_trade_cache_from_final_scope(resolved_scope=resolved_scope)
            self._state.finalized_scope_resolved_at = datetime.now(tz=UTC)
            self._state.finalized_startup_retry_after = None
            get_logger(__name__).info(
                "Bybit spot v2 finalized startup resolved scope",
                coarse_symbols=len(resolved_scope.truth.coarse_selected_symbols),
                selected_symbols=len(resolved_scope.truth.selected_symbols),
                selected_trade_counts=len(resolved_scope.truth.selected_trade_count_24h_by_symbol),
            )
            monitoring_symbols = self.deps.resolve_monitoring_symbols(
                resolved_scope=resolved_scope,
            )
            transport_diagnostics = (
                self.runtime.bybit_spot_v2_transport.get_transport_diagnostics()
                if self.runtime.bybit_spot_v2_transport is not None
                else {}
            )
            recovery_diagnostics = (
                self.runtime.bybit_spot_v2_recovery.get_recovery_diagnostics()
                if self.runtime.bybit_spot_v2_recovery is not None
                else {}
            )
            current_transport_symbols = _runtime_scope_symbols(
                self.runtime.bybit_spot_v2_transport,
                transport_diagnostics,
                diagnostics_attr="symbols",
            )
            current_recovery_symbols = _runtime_scope_symbols(
                self.runtime.bybit_spot_v2_recovery,
                recovery_diagnostics,
                diagnostics_attr="target_symbols",
            )
            transport_running = (
                self.runtime.bybit_spot_v2_transport_task is not None
                and not self.runtime.bybit_spot_v2_transport_task.done()
            )
            recovery_running = (
                self.runtime.bybit_spot_v2_recovery_task is not None
                and not self.runtime.bybit_spot_v2_recovery_task.done()
            )
            restart_transport = bool(monitoring_symbols) and (
                not transport_running
                or current_transport_symbols != monitoring_symbols
            )
            restart_recovery = bool(monitoring_symbols) and (
                not recovery_running
                or current_recovery_symbols != monitoring_symbols
            )
            if restart_transport or restart_recovery:
                get_logger(__name__).info(
                    "Bybit spot v2 finalized startup restarting transport/recovery",
                    restart_transport=restart_transport,
                    restart_recovery=restart_recovery,
                )
                if restart_transport:
                    await self.start_v2_transport(resolved_scope=resolved_scope)
                if restart_recovery or restart_transport:
                    await self.start_v2_recovery()
            else:
                get_logger(__name__).info(
                    "Bybit spot v2 finalized startup updated published scope without runtime restart",
                    monitoring_symbols=len(monitoring_symbols),
                )
            self.mark_product_snapshot_stale()
        except Exception as exc:
            self._state.finalized_startup_retry_after = datetime.now(tz=UTC) + timedelta(
                seconds=_BYBIT_SPOT_FINALIZED_STARTUP_RETRY_BACKOFF_SECONDS
            )
            get_logger(__name__).error(
                "Bybit spot v2 finalized startup failed",
                failure_type=type(exc).__name__,
                failure_message=str(exc),
            )
        finally:
            self._state.finalized_startup_task = None

    def schedule_finalized_startup(self) -> None:
        if not bool(getattr(self.runtime.settings, "bybit_spot_market_data_connector_enabled", False)):
            return
        retry_after = self._state.finalized_startup_retry_after
        if isinstance(retry_after, datetime) and retry_after > datetime.now(tz=UTC):
            return
        startup_task = self._state.finalized_startup_task
        if startup_task is not None and not startup_task.done():
            return
        self._state.finalized_startup_task = asyncio.create_task(
            self.run_finalized_startup(),
            name="production_bybit_spot_v2_finalized_startup",
        )

    async def await_finalized_startup(self) -> None:
        if not bool(getattr(self.runtime.settings, "bybit_spot_market_data_connector_enabled", False)):
            return
        startup_task = self._state.finalized_startup_task
        if startup_task is None or startup_task.done():
            startup_task = asyncio.create_task(
                self.run_finalized_startup(),
                name="production_bybit_spot_v2_finalized_startup",
            )
            self._state.finalized_startup_task = startup_task
        await asyncio.shield(startup_task)

    def is_final_scope_refresh_due(
        self,
        *,
        now: datetime,
        runtime_status: dict[str, object] | None = None,
    ) -> bool:
        last_resolved_at = self._state.finalized_scope_resolved_at
        if not isinstance(last_resolved_at, datetime):
            return True
        refresh_seconds = int(self._state.final_scope_refresh_seconds)
        scope_truth = self.runtime.bybit_spot_market_data_scope_summary
        current_runtime_status = runtime_status or self.get_runtime_status()
        if (
            scope_truth is not None
            and str(current_runtime_status.get("lifecycle_state", "starting")) == "connected_live"
            and _spot_scope_truth_is_final_for_settings(
                settings=self.runtime.settings,
                truth=scope_truth,
            )
            and not self.is_trade_truth_coverage_incomplete()
        ):
            refresh_seconds = int(self._state.stable_final_scope_refresh_seconds)
        return (now - last_resolved_at).total_seconds() >= refresh_seconds

    def tick_final_scope_refresh(self) -> None:
        if not bool(getattr(self.runtime.settings, "bybit_spot_market_data_connector_enabled", False)):
            return
        runtime_status = self.get_runtime_status()
        if self.is_trade_truth_coverage_incomplete():
            return
        if str(runtime_status.get("lifecycle_state", "starting")) != "connected_live":
            return
        scope_truth = self.runtime.bybit_spot_market_data_scope_summary
        if scope_truth is not None and not _spot_scope_truth_is_final_for_settings(
            settings=self.runtime.settings,
            truth=scope_truth,
        ):
            self.schedule_finalized_startup()
            return
        if self.is_final_scope_refresh_due(now=datetime.now(tz=UTC), runtime_status=runtime_status):
            self.schedule_finalized_startup()

    async def run_scope_refresh_loop(self) -> None:
        try:
            refresh_seconds = int(self._state.final_scope_refresh_seconds)
            while self.runtime._started and bool(
                getattr(self.runtime.settings, "bybit_spot_market_data_connector_enabled", False)
            ):
                await asyncio.sleep(refresh_seconds)
                self.tick_final_scope_refresh()
        finally:
            self._state.scope_refresh_task = None

    def ensure_scope_refresh_loop(self) -> None:
        if not self.runtime._started:
            return
        if not bool(getattr(self.runtime.settings, "bybit_spot_market_data_connector_enabled", False)):
            return
        task = self._state.scope_refresh_task
        if task is not None and not task.done():
            return
        self._state.scope_refresh_task = asyncio.create_task(
            self.run_scope_refresh_loop(),
            name="production_bybit_spot_v2_scope_refresh",
        )

    async def run_retention_maintenance_once(self) -> None:
        recovery = self.runtime.bybit_spot_v2_recovery
        prepare_storage = getattr(recovery, "prepare_storage", None)
        if callable(prepare_storage):
            await prepare_storage()

    async def run_retention_maintenance_loop(self) -> None:
        try:
            retention_seconds = max(0.01, float(self._state.retention_maintenance_seconds))
            while self.runtime._started and bool(
                getattr(self.runtime.settings, "bybit_spot_market_data_connector_enabled", False)
            ):
                await asyncio.sleep(retention_seconds)
                await self.run_retention_maintenance_once()
        finally:
            self._state.retention_maintenance_task = None

    def ensure_retention_maintenance_loop(self) -> None:
        if not self.runtime._started:
            return
        if not bool(getattr(self.runtime.settings, "bybit_spot_market_data_connector_enabled", False)):
            return
        task = self._state.retention_maintenance_task
        if task is not None and not task.done():
            return
        self._state.retention_maintenance_task = asyncio.create_task(
            self.run_retention_maintenance_loop(),
            name="production_bybit_spot_v2_retention_maintenance",
        )

    def ensure_finalized_startup_if_needed(self) -> None:
        if not bool(getattr(self.runtime.settings, "bybit_spot_market_data_connector_enabled", False)):
            return
        scope_truth = self.runtime.bybit_spot_market_data_scope_summary
        if scope_truth is not None and _spot_scope_truth_is_final_for_settings(
            settings=self.runtime.settings,
            truth=scope_truth,
        ):
            return
        self.schedule_finalized_startup()

    def get_runtime_status(self) -> dict[str, object]:
        generation = self.deps.resolve_runtime_generation(contour="spot")
        desired_running = bool(getattr(self.runtime.settings, "bybit_spot_market_data_connector_enabled", False))
        scope_truth = self.runtime.bybit_spot_market_data_scope_summary
        resolved_symbols = (
            tuple(str(symbol) for symbol in scope_truth.selected_symbols)
            if scope_truth is not None
            else ()
        )
        if generation != "v2":
            legacy_projection = self.runtime.get_bybit_spot_connector_screen_projection()
            legacy_symbols = legacy_projection.get("symbols")
            return {
                "generation": "legacy",
                "desired_running": desired_running,
                "transport_status": str(legacy_projection.get("transport_status", "disabled")),
                "subscription_alive": bool(legacy_projection.get("subscription_alive", False)),
                "transport_rtt_ms": legacy_projection.get("transport_rtt_ms")
                if isinstance(legacy_projection.get("transport_rtt_ms"), int)
                else None,
                "last_message_at": legacy_projection.get("last_message_at")
                if isinstance(legacy_projection.get("last_message_at"), str)
                else None,
                "messages_received_count": 0,
                "retry_count": 0,
                "trade_ingest_count": 0,
                "orderbook_ingest_count": 0,
                "trade_seen": False,
                "orderbook_seen": False,
                "best_bid": None,
                "best_ask": None,
                "persisted_trade_count": 0,
                "last_persisted_trade_at": None,
                "last_persisted_trade_symbol": None,
                "recovery_status": legacy_projection.get("recovery_status")
                if isinstance(legacy_projection.get("recovery_status"), str)
                else None,
                "recovery_stage": None,
                "recovery_reason": legacy_projection.get("historical_recovery_reason")
                if isinstance(legacy_projection.get("historical_recovery_reason"), str)
                else None,
                "scope_mode": str(legacy_projection.get("scope_mode", "universe")),
                "total_instruments_discovered": (
                    legacy_projection.get("total_instruments_discovered")
                    if isinstance(legacy_projection.get("total_instruments_discovered"), int)
                    else None
                ),
                "volume_filtered_symbols_count": (
                    legacy_projection.get("instruments_passed_coarse_filter")
                    if isinstance(legacy_projection.get("instruments_passed_coarse_filter"), int)
                    else None
                ),
                "filtered_symbols_count": (
                    legacy_projection.get("instruments_passed_coarse_filter")
                    if isinstance(legacy_projection.get("instruments_passed_coarse_filter"), int)
                    else None
                ),
                "selected_symbols_count": (
                    len(tuple(symbol for symbol in legacy_symbols if isinstance(symbol, str)))
                    if isinstance(legacy_symbols, (list, tuple))
                    else 0
                ),
                "scope_limit_applied": False,
                "lifecycle_state": (
                    "stopped"
                    if not desired_running
                    else "connected_live"
                    if bool(legacy_projection.get("trade_seen", False))
                    and bool(legacy_projection.get("orderbook_seen", False))
                    else "starting"
                ),
                "symbols": (
                    tuple(symbol for symbol in legacy_symbols if isinstance(symbol, str))
                    if isinstance(legacy_symbols, (list, tuple))
                    else ()
                ),
            }

        transport = self.runtime.get_bybit_spot_v2_transport_diagnostics()
        recovery = self.runtime.get_bybit_spot_v2_recovery_diagnostics()
        transport_symbols = transport.get("symbols")
        coarse_symbols = (
            tuple(str(symbol) for symbol in transport_symbols if isinstance(symbol, str))
            if isinstance(transport_symbols, (list, tuple))
            else ()
        )
        if not resolved_symbols and scope_truth is not None:
            resolved_symbols = tuple(str(symbol) for symbol in scope_truth.coarse_selected_symbols)
        strict_published_symbols = (
            tuple(str(symbol) for symbol in scope_truth.selected_symbols)
            if scope_truth is not None
            else resolved_symbols
        )
        screen_symbols = strict_published_symbols
        trade_truth_incomplete = self.is_trade_truth_coverage_incomplete()
        if not screen_symbols and trade_truth_incomplete:
            screen_symbols = resolved_symbols or coarse_symbols
        trade_ingest_count = int(transport.get("trade_ingest_count", 0))
        orderbook_ingest_count = int(transport.get("orderbook_ingest_count", 0))
        trade_seen = bool(transport.get("trade_seen", False))
        orderbook_seen = bool(transport.get("orderbook_seen", False))
        transport_status = str(transport.get("transport_status", "disabled"))
        filtered_symbols_count = (
            int(scope_truth.instruments_passed_final_filter)
            if scope_truth is not None and isinstance(scope_truth.instruments_passed_final_filter, int)
            else int(scope_truth.instruments_passed_coarse_filter)
            if scope_truth is not None and isinstance(scope_truth.instruments_passed_coarse_filter, int)
            else len(strict_published_symbols)
        )
        if not strict_published_symbols and screen_symbols and self.is_trade_truth_coverage_incomplete():
            filtered_symbols_count = (
                int(scope_truth.instruments_passed_coarse_filter)
                if scope_truth is not None and isinstance(scope_truth.instruments_passed_coarse_filter, int)
                else len(screen_symbols)
            )
        volume_filtered_symbols_count = (
            int(scope_truth.instruments_passed_coarse_filter)
            if scope_truth is not None and isinstance(scope_truth.instruments_passed_coarse_filter, int)
            else filtered_symbols_count
        )
        lifecycle_state = self.deps.resolve_spot_primary_lifecycle_state(
            desired_running=desired_running,
            transport_status=transport_status,
            trade_seen=trade_seen,
            orderbook_seen=orderbook_seen,
            trade_ingest_count=trade_ingest_count,
            orderbook_ingest_count=orderbook_ingest_count,
        )
        screen_scope_reason = _resolve_runtime_screen_scope_reason(
            strict_published_symbols=strict_published_symbols,
            resolved_symbols=resolved_symbols,
            coarse_symbols=coarse_symbols,
            screen_symbols=screen_symbols,
            trade_truth_incomplete=trade_truth_incomplete,
        )
        return {
            "generation": "v2",
            "desired_running": desired_running,
            "transport_status": transport_status,
            "subscription_alive": bool(transport.get("subscription_alive", False)),
            "transport_rtt_ms": _resolve_operator_transport_rtt_ms(transport),
            "last_message_at": transport.get("last_message_at")
            if isinstance(transport.get("last_message_at"), str)
            else None,
            "messages_received_count": int(transport.get("messages_received_count", 0)),
            "retry_count": int(transport.get("retry_count")) if isinstance(transport.get("retry_count"), int) else 0,
            "trade_ingest_count": trade_ingest_count,
            "orderbook_ingest_count": orderbook_ingest_count,
            "trade_seen": trade_seen,
            "orderbook_seen": orderbook_seen,
            "best_bid": transport.get("best_bid") if isinstance(transport.get("best_bid"), str) else None,
            "best_ask": transport.get("best_ask") if isinstance(transport.get("best_ask"), str) else None,
            "persisted_trade_count": int(transport.get("persisted_trade_count", 0)),
            "last_persisted_trade_at": transport.get("last_persisted_trade_at")
            if isinstance(transport.get("last_persisted_trade_at"), str)
            else None,
            "last_persisted_trade_symbol": transport.get("last_persisted_trade_symbol")
            if isinstance(transport.get("last_persisted_trade_symbol"), str)
            else None,
            "recovery_status": recovery.get("status") if isinstance(recovery.get("status"), str) else None,
            "recovery_stage": recovery.get("stage") if isinstance(recovery.get("stage"), str) else None,
            "recovery_reason": recovery.get("reason") if isinstance(recovery.get("reason"), str) else None,
            "scope_mode": scope_truth.scope_mode if scope_truth is not None else "universe",
            "total_instruments_discovered": (
                int(scope_truth.total_instruments_discovered)
                if scope_truth is not None and isinstance(scope_truth.total_instruments_discovered, int)
                else None
            ),
            "volume_filtered_symbols_count": volume_filtered_symbols_count,
            "filtered_symbols_count": filtered_symbols_count,
            "selected_symbols_count": len(screen_symbols),
            "scope_limit_applied": False,
            "lifecycle_state": lifecycle_state,
            "symbols": screen_symbols,
            "monitoring_symbols_count": len(coarse_symbols),
            "screen_scope_reason": screen_scope_reason,
            "contract_flags": _build_runtime_contract_flags(
                strict_published_symbols=strict_published_symbols,
                coarse_symbols=coarse_symbols,
                screen_symbols=screen_symbols,
                trade_truth_incomplete=trade_truth_incomplete,
            ),
        }

    async def get_cached_exact_trade_counts_by_symbol(
        self,
        *,
        symbols: tuple[str, ...],
        observed_at: datetime,
        window_hours: int = 24,
        ttl_seconds: int = 10,
    ) -> dict[str, Any]:
        cache_expires_at = self._state.exact_trade_cache_expires_at
        cached_symbols = self._state.exact_trade_cache_symbols
        cached_by_symbol = self._state.exact_trade_cache_by_symbol
        cached_result = _exact_cache_access_get_cached_exact_trade_counts_if_usable(
            symbols=symbols,
            observed_at=observed_at,
            cache_expires_at=cache_expires_at,
            cached_symbols=cached_symbols,
            cached_by_symbol=cached_by_symbol,
        )
        if cached_result is not None:
            return cached_result
        chunk_size, batch_concurrency = _resolve_exact_query_profile(symbol_count=len(symbols))
        exact_trade_by_symbol = await self.deps.query_exact_trade_count_snapshots_uncached(
            db_manager=self.runtime.db_manager,
            symbols=symbols,
            observed_at=observed_at,
            window_hours=window_hours,
            chunk_size=chunk_size,
            batch_concurrency=batch_concurrency,
        )
        self._state.exact_trade_cache_by_symbol = exact_trade_by_symbol
        self._state.exact_trade_cache_symbols = symbols
        self._state.exact_trade_cache_observed_at = observed_at
        self._state.exact_trade_cache_expires_at = observed_at + timedelta(
            seconds=ttl_seconds
        )
        return exact_trade_by_symbol

    def _store_exact_trade_cache(
        self,
        *,
        symbols: tuple[str, ...],
        observed_at: datetime,
        exact_trade_by_symbol: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        self._state.exact_trade_cache_by_symbol = exact_trade_by_symbol
        self._state.exact_trade_cache_symbols = symbols
        self._state.exact_trade_cache_observed_at = observed_at
        self._state.exact_trade_cache_expires_at = observed_at + timedelta(seconds=ttl_seconds)

    async def get_fresh_exact_trade_counts_by_symbol(
        self,
        *,
        symbols: tuple[str, ...],
        observed_at: datetime,
        window_hours: int = 24,
        ttl_seconds: int = 10,
    ) -> dict[str, Any]:
        if not symbols:
            return {}
        chunk_size, batch_concurrency = _resolve_exact_query_profile(symbol_count=len(symbols))
        exact_trade_by_symbol = await self.deps.query_exact_trade_count_snapshots_uncached(
            db_manager=self.runtime.db_manager,
            symbols=symbols,
            observed_at=observed_at,
            window_hours=window_hours,
            chunk_size=chunk_size,
            batch_concurrency=batch_concurrency,
        )
        self._store_exact_trade_cache(
            symbols=symbols,
            observed_at=observed_at,
            exact_trade_by_symbol=exact_trade_by_symbol,
            ttl_seconds=ttl_seconds,
        )
        return exact_trade_by_symbol

    def resolve_snapshot_symbols(
        self,
        *,
        runtime_status: dict[str, object],
    ) -> tuple[str, ...]:
        scope_truth = self.runtime.bybit_spot_market_data_scope_summary
        resolved_symbols = _resolve_snapshot_symbols_from_truth(
            truth=scope_truth,
            settings=self.runtime.settings,
        )
        if resolved_symbols:
            return resolved_symbols
        return tuple(
            str(symbol)
            for symbol in runtime_status.get("symbols", ())
            if isinstance(symbol, str)
        )

    def resolve_fallback_snapshot_symbols(
        self,
        *,
        runtime_status: dict[str, object],
    ) -> tuple[str, ...]:
        scope_truth = self.runtime.bybit_spot_market_data_scope_summary
        resolved_symbols = _resolve_fallback_snapshot_symbols_from_truth(
            truth=scope_truth,
        )
        if resolved_symbols:
            return resolved_symbols
        return tuple(
            str(symbol)
            for symbol in runtime_status.get("symbols", ())
            if isinstance(symbol, str)
        )

    async def refresh_exact_trade_cache(
        self,
        *,
        symbols: tuple[str, ...],
    ) -> None:
        try:
            if not symbols:
                return
            try:
                await self.get_fresh_exact_trade_counts_by_symbol(
                    symbols=symbols,
                    observed_at=datetime.now(tz=UTC),
                    window_hours=24,
                    ttl_seconds=max(30, int(self._state.stable_final_scope_refresh_seconds)),
                )
                self._state.exact_trade_cache_retry_after = None
                self.mark_product_snapshot_stale()
                self.schedule_product_snapshot_refresh()
                scope_truth = self.runtime.bybit_spot_market_data_scope_summary
                if (
                    scope_truth is not None
                    and not _spot_scope_truth_is_final_for_settings(
                        settings=self.runtime.settings,
                        truth=scope_truth,
                    )
                    and not self.is_trade_truth_coverage_incomplete()
                ):
                    self._state.finalized_startup_retry_after = None
                    self.schedule_finalized_startup()
            except TimeoutError:
                self._state.exact_trade_cache_expires_at = None
                self._state.exact_trade_cache_retry_after = datetime.now(tz=UTC) + timedelta(
                    seconds=_BYBIT_SPOT_EXACT_CACHE_RETRY_BACKOFF_SECONDS
                )
                get_logger(__name__).warning(
                    "Bybit spot exact trade cache refresh timed out",
                    symbols=len(symbols),
                )
        finally:
            self._state.exact_trade_cache_refresh_task = None

    def schedule_exact_trade_cache_refresh(
        self,
        *,
        symbols: tuple[str, ...],
    ) -> None:
        if not symbols:
            return
        retry_after = self._state.exact_trade_cache_retry_after
        if isinstance(retry_after, datetime) and retry_after > datetime.now(tz=UTC):
            return
        refresh_task = self._state.exact_trade_cache_refresh_task
        if refresh_task is not None and not refresh_task.done():
            return
        self._state.exact_trade_cache_refresh_task = asyncio.create_task(
            self.refresh_exact_trade_cache(symbols=symbols),
            name="production_bybit_spot_exact_trade_cache_refresh",
        )

    async def build_product_snapshot_payload(
        self,
        *,
        now: datetime,
        runtime_status: dict[str, object],
    ) -> dict[str, object]:
        scope_truth = self.runtime.bybit_spot_market_data_scope_summary
        min_trade_count_24h = self.deps.resolve_min_trade_count_24h(
            settings=self.runtime.settings,
            contour="spot",
        )
        selected_symbols = self.resolve_snapshot_symbols(runtime_status=runtime_status)
        fallback_symbols = self.resolve_fallback_snapshot_symbols(runtime_status=runtime_status)
        transport_diagnostics = self.runtime.get_bybit_spot_v2_transport_diagnostics()
        transport_volume_by_symbol = transport_diagnostics.get("quote_turnover_24h_by_symbol")
        volume_by_symbol = (
            dict(
                scope_truth.selected_quote_volume_24h_usd_by_symbol
                or scope_truth.coarse_selected_quote_volume_24h_usd_by_symbol
            )
            if scope_truth is not None
            else {}
        )
        if isinstance(transport_volume_by_symbol, dict):
            for symbol, volume in transport_volume_by_symbol.items():
                if isinstance(symbol, str) and isinstance(volume, str):
                    volume_by_symbol[symbol] = volume
        exact_trade_by_symbol = await self.get_cached_exact_trade_counts_by_symbol(
            symbols=selected_symbols,
            observed_at=now,
            window_hours=24,
        )
        confirmed_final_symbols, instrument_rows, persistence_24h = _build_published_snapshot_contract(
            candidate_symbols=selected_symbols,
            exact_trade_by_symbol=exact_trade_by_symbol,
            volume_by_symbol=volume_by_symbol,
            min_trade_count_24h=min_trade_count_24h,
            module=self,
            observed_at=now,
        )
        if _should_publish_fallback_snapshot_contract(
            candidate_symbols=selected_symbols,
            fallback_symbols=fallback_symbols,
            published_symbols=confirmed_final_symbols,
            exact_trade_by_symbol=exact_trade_by_symbol,
            module=self,
        ):
            confirmed_final_symbols, instrument_rows, persistence_24h = _build_fallback_snapshot_contract(
                provisional_symbols=fallback_symbols,
                volume_by_symbol=volume_by_symbol,
                module=self,
            )
            if not _fallback_snapshot_contract_is_consistent(
                provisional_symbols=confirmed_final_symbols,
                instrument_rows=instrument_rows,
            ):
                raise RuntimeError("bybit_spot fallback snapshot contract invariant violated")
            return {
                **runtime_status,
                "filtered_symbols_count": len(confirmed_final_symbols),
                "selected_symbols_count": len(confirmed_final_symbols),
                "symbols": confirmed_final_symbols,
                "observed_at": now.isoformat(),
                "persistence_24h": persistence_24h,
                "instrument_rows": instrument_rows,
                "screen_scope_reason": _resolve_product_snapshot_reason(
                    symbols=confirmed_final_symbols,
                    instrument_rows=instrument_rows,
                    persistence_24h=persistence_24h,
                    runtime_status=runtime_status,
                ),
                "contract_flags": _build_product_snapshot_contract_flags(
                    symbols=confirmed_final_symbols,
                    instrument_rows=instrument_rows,
                    persistence_24h=persistence_24h,
                    runtime_status=runtime_status,
                    min_trade_count_24h=min_trade_count_24h,
                ),
            }
        if not _published_snapshot_contract_is_consistent(
            published_symbols=confirmed_final_symbols,
            instrument_rows=instrument_rows,
            min_trade_count_24h=min_trade_count_24h,
            coverage_status=str(persistence_24h.get("coverage_status", "empty")),
        ):
            raise RuntimeError("bybit_spot published snapshot contract invariant violated")
        return {
            **runtime_status,
            "filtered_symbols_count": len(confirmed_final_symbols),
            "selected_symbols_count": len(confirmed_final_symbols),
            "symbols": confirmed_final_symbols,
            "observed_at": now.isoformat(),
            "persistence_24h": persistence_24h,
            "instrument_rows": instrument_rows,
            "screen_scope_reason": _resolve_product_snapshot_reason(
                symbols=confirmed_final_symbols,
                instrument_rows=instrument_rows,
                persistence_24h=persistence_24h,
                runtime_status=runtime_status,
            ),
            "contract_flags": _build_product_snapshot_contract_flags(
                symbols=confirmed_final_symbols,
                instrument_rows=instrument_rows,
                persistence_24h=persistence_24h,
                runtime_status=runtime_status,
                min_trade_count_24h=min_trade_count_24h,
            ),
        }

    async def build_product_snapshot_fast_payload(
        self,
        *,
        now: datetime,
        runtime_status: dict[str, object],
    ) -> dict[str, object]:
        scope_truth = self.runtime.bybit_spot_market_data_scope_summary
        min_trade_count_24h = self.deps.resolve_min_trade_count_24h(
            settings=self.runtime.settings,
            contour="spot",
        )
        selected_symbols = self.resolve_snapshot_symbols(runtime_status=runtime_status)
        fallback_symbols = self.resolve_fallback_snapshot_symbols(runtime_status=runtime_status)
        transport_diagnostics = self.runtime.get_bybit_spot_v2_transport_diagnostics()
        transport_volume_by_symbol = transport_diagnostics.get("quote_turnover_24h_by_symbol")
        volume_by_symbol = (
            dict(
                scope_truth.selected_quote_volume_24h_usd_by_symbol
                or scope_truth.coarse_selected_quote_volume_24h_usd_by_symbol
            )
            if scope_truth is not None
            else {}
        )
        if isinstance(transport_volume_by_symbol, dict):
            for symbol, volume in transport_volume_by_symbol.items():
                if isinstance(symbol, str) and isinstance(volume, str):
                    volume_by_symbol[symbol] = volume
        exact_trade_by_symbol = self._get_publishable_exact_snapshots(symbols=selected_symbols)
        can_reuse_exact_cache = exact_trade_by_symbol is not None
        confirmed_final_symbols: tuple[str, ...] = ()
        instrument_rows: list[dict[str, object]] = []
        persistence_24h = {
            "live_trade_count_24h": 0,
            "archive_trade_count_24h": 0,
            "persisted_trade_count_24h": 0,
            "first_persisted_trade_at": None,
            "last_persisted_trade_at": None,
            "coverage_status": "pending_exact:empty",
        }
        if can_reuse_exact_cache:
            assert exact_trade_by_symbol is not None
            confirmed_final_symbols, instrument_rows, persistence_24h = _build_published_snapshot_contract(
                candidate_symbols=selected_symbols,
                exact_trade_by_symbol=exact_trade_by_symbol,
                volume_by_symbol=volume_by_symbol,
                min_trade_count_24h=min_trade_count_24h,
                module=self,
                observed_at=now,
            )
            if _should_publish_fallback_snapshot_contract(
                candidate_symbols=selected_symbols,
                fallback_symbols=fallback_symbols,
                published_symbols=confirmed_final_symbols,
                exact_trade_by_symbol=exact_trade_by_symbol,
                module=self,
            ):
                confirmed_final_symbols, instrument_rows, persistence_24h = _build_fallback_snapshot_contract(
                    provisional_symbols=fallback_symbols,
                    volume_by_symbol=volume_by_symbol,
                    module=self,
                )
                if not _fallback_snapshot_contract_is_consistent(
                    provisional_symbols=confirmed_final_symbols,
                    instrument_rows=instrument_rows,
                ):
                    raise RuntimeError("bybit_spot fallback snapshot contract invariant violated")
            elif not _published_snapshot_contract_is_consistent(
                published_symbols=confirmed_final_symbols,
                instrument_rows=instrument_rows,
                min_trade_count_24h=min_trade_count_24h,
                coverage_status=str(persistence_24h.get("coverage_status", "empty")),
            ):
                raise RuntimeError("bybit_spot published fast snapshot contract invariant violated")
        elif fallback_symbols:
            confirmed_final_symbols, instrument_rows, persistence_24h = _build_fallback_snapshot_contract(
                provisional_symbols=fallback_symbols,
                volume_by_symbol=volume_by_symbol,
                module=self,
            )
            if not _fallback_snapshot_contract_is_consistent(
                provisional_symbols=confirmed_final_symbols,
                instrument_rows=instrument_rows,
            ):
                raise RuntimeError("bybit_spot fallback snapshot contract invariant violated")
        return {
            **runtime_status,
            "filtered_symbols_count": len(confirmed_final_symbols),
            "selected_symbols_count": len(confirmed_final_symbols),
            "symbols": confirmed_final_symbols if can_reuse_exact_cache else fallback_symbols,
            "observed_at": now.isoformat(),
            "persistence_24h": persistence_24h,
            "instrument_rows": instrument_rows,
            "screen_scope_reason": _resolve_product_snapshot_reason(
                symbols=confirmed_final_symbols if can_reuse_exact_cache else fallback_symbols,
                instrument_rows=instrument_rows,
                persistence_24h=persistence_24h,
                runtime_status=runtime_status,
            ),
            "contract_flags": _build_product_snapshot_contract_flags(
                symbols=confirmed_final_symbols if can_reuse_exact_cache else fallback_symbols,
                instrument_rows=instrument_rows,
                persistence_24h=persistence_24h,
                runtime_status=runtime_status,
                min_trade_count_24h=min_trade_count_24h,
            ),
        }

    def is_product_snapshot_cache_usable(
        self,
        *,
        cache_payload: dict[str, object],
        runtime_status: dict[str, object],
    ) -> bool:
        return _cache_contracts_is_product_snapshot_cache_usable(
            cache_payload=cache_payload,
            runtime_status=runtime_status,
        )

    async def refresh_product_snapshot_cache(self) -> None:
        try:
            now = datetime.now(tz=UTC)
            runtime_status = self.get_runtime_status()
            publishable = _is_product_snapshot_publishable(runtime_status)
            selected_symbols_count = (
                int(runtime_status.get("selected_symbols_count", 0))
                if isinstance(runtime_status.get("selected_symbols_count"), int)
                else 0
            )
            if (
                self.runtime._started
                and not publishable
                and selected_symbols_count > 0
            ):
                payload = await self.build_product_snapshot_fast_payload(
                    now=now,
                    runtime_status=runtime_status,
                )
                persistence_24h = payload.get("persistence_24h")
                instrument_rows = payload.get("instrument_rows")
                has_exact_rows = isinstance(instrument_rows, list) and any(
                    isinstance(row, dict) and row.get("trade_count_24h") is not None
                    for row in instrument_rows
                )
                if isinstance(persistence_24h, dict) and not has_exact_rows:
                    lifecycle_state = (
                        str(runtime_status.get("lifecycle_state"))
                        if isinstance(runtime_status.get("lifecycle_state"), str)
                        else "starting"
                    )
                    persistence_24h["coverage_status"] = (
                        "pending_startup"
                        if lifecycle_state == "starting"
                        else "pending_live"
                    )
                snapshot_cache_ttl_seconds = 2
            elif self.runtime._started and not publishable:
                payload = {
                    **runtime_status,
                    "filtered_symbols_count": int(runtime_status.get("filtered_symbols_count", 0))
                    if isinstance(runtime_status.get("filtered_symbols_count"), int)
                    else 0,
                    "selected_symbols_count": int(runtime_status.get("selected_symbols_count", 0))
                    if isinstance(runtime_status.get("selected_symbols_count"), int)
                    else 0,
                    "observed_at": now.isoformat(),
                    "persistence_24h": {
                        "live_trade_count_24h": 0,
                        "archive_trade_count_24h": 0,
                        "persisted_trade_count_24h": 0,
                        "first_persisted_trade_at": None,
                        "last_persisted_trade_at": None,
                        "coverage_status": "pending_live",
                    },
                    "instrument_rows": [],
                }
                snapshot_cache_ttl_seconds = 2
            else:
                try:
                    payload = await self.build_product_snapshot_payload(now=now, runtime_status=runtime_status)
                except TimeoutError:
                    payload = await self.build_product_snapshot_fast_payload(
                        now=now,
                        runtime_status=runtime_status,
                    )
                snapshot_cache_ttl_seconds = 5 if bool(runtime_status.get("desired_running", False)) else 10
            self._state.product_snapshot_cache_payload = payload
            self._state.product_snapshot_cache_expires_at = now + timedelta(seconds=snapshot_cache_ttl_seconds)
        finally:
            self._state.product_snapshot_refresh_task = None

    def schedule_product_snapshot_refresh(self) -> None:
        if not self.runtime._started:
            return
        runtime_status = self.get_runtime_status()
        if str(runtime_status.get("lifecycle_state", "starting")) != "connected_live":
            return
        if self._state.product_snapshot_cache_payload is None:
            return
        refresh_task = self._state.product_snapshot_refresh_task
        if refresh_task is not None and not refresh_task.done():
            return
        self._state.product_snapshot_refresh_task = asyncio.create_task(
            self.refresh_product_snapshot_cache(),
            name="production_bybit_spot_product_snapshot_refresh",
        )

    def mark_product_snapshot_stale(self) -> None:
        if self._state.product_snapshot_cache_payload is None:
            self._state.product_snapshot_cache_expires_at = None
            return
        self._state.product_snapshot_cache_expires_at = datetime.now(tz=UTC)

    def reset_product_snapshot_cache(self) -> None:
        self._state.product_snapshot_cache_payload = None
        self._state.product_snapshot_cache_expires_at = None

    async def get_product_snapshot(self) -> dict[str, object]:
        runtime_status = self.get_runtime_status()
        generation = str(runtime_status.get("generation", "legacy"))
        if generation != "v2":
            return {
                **runtime_status,
                "observed_at": datetime.now(tz=UTC).isoformat(),
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
        now = datetime.now(tz=UTC)
        scope_truth = self.runtime.bybit_spot_market_data_scope_summary
        if (
            bool(runtime_status.get("desired_running", False))
            and scope_truth is not None
            and not _spot_scope_truth_is_final_for_settings(
                settings=self.runtime.settings,
                truth=scope_truth,
            )
            and not self.is_trade_truth_coverage_incomplete()
        ):
            self.schedule_finalized_startup()
        if (
            bool(runtime_status.get("desired_running", False))
            and str(runtime_status.get("transport_status", "idle")) == "idle"
        ):
            transport_task_active = (
                self.runtime.bybit_spot_v2_transport_task is not None
                and not self.runtime.bybit_spot_v2_transport_task.done()
            )
            if not transport_task_active and str(
                runtime_status.get("lifecycle_state", "starting")
            ) not in {"starting", "connected_no_flow"}:
                self.schedule_finalized_startup()
        if (
            bool(runtime_status.get("desired_running", False))
            and str(runtime_status.get("lifecycle_state", "starting")) == "connected_live"
            and not self.is_trade_truth_coverage_incomplete()
            and self.is_final_scope_refresh_due(now=now)
        ):
            self.schedule_finalized_startup()
        selected_symbols = self.resolve_snapshot_symbols(runtime_status=runtime_status)
        exact_snapshots = self._get_publishable_exact_snapshots(symbols=selected_symbols)
        exact_cache_is_ready = exact_snapshots is not None
        selected_symbols_count = (
            int(runtime_status.get("selected_symbols_count", 0))
            if isinstance(runtime_status.get("selected_symbols_count"), int)
            else 0
        )
        cache_payload = self._state.product_snapshot_cache_payload
        cache_expires_at = self._state.product_snapshot_cache_expires_at
        if (
            isinstance(cache_payload, dict)
            and isinstance(cache_expires_at, datetime)
            and cache_expires_at > now
            and self.is_product_snapshot_cache_usable(
                cache_payload=cache_payload,
                runtime_status=runtime_status,
            )
        ):
            return cache_payload
        lifecycle_state = (
            str(runtime_status.get("lifecycle_state"))
            if isinstance(runtime_status.get("lifecycle_state"), str)
            else None
        )
        publishable = _is_product_snapshot_publishable(runtime_status)
        if selected_symbols_count > 0 and not exact_cache_is_ready:
            awaited_exact = False
            exact_wait_timeout = (
                _BYBIT_SPOT_BROWSER_STARTUP_EXACT_WAIT_SECONDS
                if lifecycle_state == "starting"
                else _BYBIT_SPOT_BROWSER_EXACT_WAIT_SECONDS
            )
            for task in (
                self._state.finalized_startup_task,
                self._state.exact_trade_cache_refresh_task,
            ):
                if task is None or task.done():
                    continue
                try:
                    await asyncio.wait_for(
                        asyncio.shield(task),
                        timeout=exact_wait_timeout,
                    )
                except (TimeoutError, asyncio.TimeoutError):
                    break
                awaited_exact = True
            if awaited_exact:
                now = datetime.now(tz=UTC)
                runtime_status = self.get_runtime_status()
                lifecycle_state = (
                    str(runtime_status.get("lifecycle_state"))
                    if isinstance(runtime_status.get("lifecycle_state"), str)
                    else None
                )
                publishable = _is_product_snapshot_publishable(runtime_status)
                selected_symbols = self.resolve_snapshot_symbols(runtime_status=runtime_status)
                exact_snapshots = self._get_publishable_exact_snapshots(symbols=selected_symbols)
                exact_cache_is_ready = exact_snapshots is not None
                selected_symbols_count = (
                    int(runtime_status.get("selected_symbols_count", 0))
                    if isinstance(runtime_status.get("selected_symbols_count"), int)
                    else 0
                )
        if (
            lifecycle_state is not None
            and not publishable
            and selected_symbols_count > 0
        ):
            payload = await self.build_product_snapshot_fast_payload(
                now=now,
                runtime_status=runtime_status,
            )
            persistence_24h = payload.get("persistence_24h")
            instrument_rows = payload.get("instrument_rows")
            has_exact_rows = isinstance(instrument_rows, list) and any(
                isinstance(row, dict) and row.get("trade_count_24h") is not None
                for row in instrument_rows
            )
            if isinstance(persistence_24h, dict) and not has_exact_rows:
                persistence_24h["coverage_status"] = (
                    "pending_startup"
                    if lifecycle_state == "starting"
                    else "pending_live"
                )
            self._state.product_snapshot_cache_payload = payload
            self._state.product_snapshot_cache_expires_at = now + timedelta(
                seconds=2 if has_exact_rows else 0.25
            )
            persistence_24h = payload.get("persistence_24h")
            if isinstance(persistence_24h, dict):
                self.ensure_archive_recovery_if_needed(
                    coverage_status=str(persistence_24h.get("coverage_status", "empty"))
                )
            return payload
        if lifecycle_state is not None and not publishable:
            return {
                **runtime_status,
                "filtered_symbols_count": int(runtime_status.get("filtered_symbols_count", 0))
                if isinstance(runtime_status.get("filtered_symbols_count"), int)
                else 0,
                "selected_symbols_count": int(runtime_status.get("selected_symbols_count", 0))
                if isinstance(runtime_status.get("selected_symbols_count"), int)
                else 0,
                "observed_at": now.isoformat(),
                "persistence_24h": {
                    "live_trade_count_24h": 0,
                    "archive_trade_count_24h": 0,
                    "persisted_trade_count_24h": 0,
                    "first_persisted_trade_at": None,
                    "last_persisted_trade_at": None,
                    "coverage_status": "pending_live" if self.runtime._started else "pending_startup",
                },
                "instrument_rows": [],
            }
        if publishable:
            self.schedule_exact_trade_cache_refresh(
                symbols=selected_symbols
            )
            payload = await self.build_product_snapshot_fast_payload(
                now=now,
                runtime_status=runtime_status,
            )
            instrument_rows = payload.get("instrument_rows")
            has_exact_rows = isinstance(instrument_rows, list) and any(
                isinstance(row, dict) and row.get("trade_count_24h") is not None
                for row in instrument_rows
            )
            self._state.product_snapshot_cache_payload = payload
            self._state.product_snapshot_cache_expires_at = now + timedelta(
                seconds=2 if has_exact_rows else 0.25
            )
            persistence_24h = payload.get("persistence_24h")
            if isinstance(persistence_24h, dict):
                self.ensure_archive_recovery_if_needed(
                    coverage_status=str(persistence_24h.get("coverage_status", "empty"))
                )
            if exact_cache_is_ready:
                self.schedule_product_snapshot_refresh()
            return payload
        payload = await self.build_product_snapshot_payload(
            now=now,
            runtime_status=runtime_status,
        )
        snapshot_cache_ttl_seconds = 5 if self.runtime._started else 10
        self._state.product_snapshot_cache_payload = payload
        self._state.product_snapshot_cache_expires_at = now + timedelta(
            seconds=snapshot_cache_ttl_seconds
        )
        return payload

    async def start_runtime(self) -> None:
        await self.start_market_data_connector()
        self.ensure_scope_refresh_loop()
        self.ensure_retention_maintenance_loop()
        scope_truth = self.runtime.bybit_spot_market_data_scope_summary
        if scope_truth is not None and _spot_scope_truth_is_final_for_settings(
            settings=self.runtime.settings,
            truth=scope_truth,
        ):
            await self.start_v2_transport()
            await self.start_v2_recovery()
            return
        await self.await_finalized_startup()

    async def stop_runtime(self) -> None:
        if self._state.scope_refresh_task is not None:
            self._state.scope_refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._state.scope_refresh_task
            self._state.scope_refresh_task = None
        if self._state.retention_maintenance_task is not None:
            self._state.retention_maintenance_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._state.retention_maintenance_task
            self._state.retention_maintenance_task = None
        await self.stop_market_data_connector()
        await self.stop_v2_recovery()
        await self.stop_v2_transport()

    async def start_market_data_connector(self) -> None:
        if (
            self.runtime.bybit_spot_market_data_connector_task is not None
            and self.runtime.bybit_spot_market_data_connector_task.done()
        ):
            self.runtime.bybit_spot_market_data_connector_task = None
        if (
            self.runtime.bybit_spot_market_data_connector is not None
            and self.runtime.bybit_spot_market_data_connector_task is None
        ):
            get_logger(__name__).info(
                "Bybit spot connector task scheduling",
                exchange="bybit_spot",
            )
            self.runtime.bybit_spot_market_data_connector.set_ledger_trade_count_query_service(
                self.deps.build_trade_ledger_query_service(db_manager=self.runtime.db_manager)
            )
            self.runtime.bybit_spot_market_data_connector_task = asyncio.create_task(
                self.runtime.bybit_spot_market_data_connector.run(),
                name="production_bybit_spot_market_data_connector",
            )

    async def start_v2_transport(self, *, resolved_scope: Any | None = None) -> None:
        if (
            self.runtime.bybit_spot_v2_transport_task is not None
            and self.runtime.bybit_spot_v2_transport is not None
        ):
            current_transport_diagnostics = self.runtime.bybit_spot_v2_transport.get_transport_diagnostics()
            current_transport_started = bool(current_transport_diagnostics.get("started", False))
            current_transport_status = str(current_transport_diagnostics.get("transport_status", "idle"))
            if not current_transport_started and current_transport_status in {"idle", "disabled", "stopped"}:
                await self.stop_v2_transport()
                self.runtime.bybit_spot_v2_transport = None
        if (
            self.runtime.bybit_spot_v2_recovery_task is not None
            and self.runtime.bybit_spot_v2_recovery is not None
        ):
            current_recovery_diagnostics = self.runtime.bybit_spot_v2_recovery.get_recovery_diagnostics()
            current_recovery_started = bool(current_recovery_diagnostics.get("started", False))
            current_recovery_status = str(current_recovery_diagnostics.get("status", "idle"))
            if not current_recovery_started and current_recovery_status in {"idle", "stopped", "waiting_for_scope"}:
                await self.stop_v2_recovery()
                self.runtime.bybit_spot_v2_recovery = None
        if (
            self.runtime.bybit_spot_v2_transport_task is not None
            and self.runtime.bybit_spot_v2_transport_task.done()
        ):
            self.runtime.bybit_spot_v2_transport_task = None
        existing_transport_stop_requested = (
            getattr(self.runtime.bybit_spot_v2_transport, "_stop_requested", None)
            if self.runtime.bybit_spot_v2_transport is not None
            else None
        )
        existing_recovery_stop_requested = (
            getattr(self.runtime.bybit_spot_v2_recovery, "_stop_requested", None)
            if self.runtime.bybit_spot_v2_recovery is not None
            else None
        )
        if (
            existing_transport_stop_requested is not None
            and existing_transport_stop_requested.is_set()
        ) or (
            existing_recovery_stop_requested is not None
            and existing_recovery_stop_requested.is_set()
        ):
            self.runtime.bybit_spot_v2_transport = None
            self.runtime.bybit_spot_v2_recovery = None
        if (
            self.runtime.bybit_spot_v2_transport_task is None
            and self.deps.resolve_runtime_generation(contour="spot") == "v2"
        ):
            if resolved_scope is None:
                existing_truth = self.runtime.bybit_spot_market_data_scope_summary
                if (
                    existing_truth is not None
                    and _spot_scope_truth_is_final_for_settings(
                        settings=self.runtime.settings,
                        truth=existing_truth,
                    )
                ):
                    resolved_symbols = (
                        existing_truth.coarse_selected_symbols
                        if int(existing_truth.trade_count_filter_minimum) <= 0
                        and existing_truth.coarse_selected_symbols
                        else existing_truth.selected_symbols
                    )
                    resolved_scope = type("ResolvedScope", (), {})()
                    resolved_scope.symbols = tuple(str(symbol) for symbol in resolved_symbols)
                    resolved_scope.truth = existing_truth
                else:
                    resolved_scope = self.deps.reuse_scope_if_possible(
                        settings=self.runtime.settings,
                        contour="spot",
                        existing_truth=existing_truth,
                    ) or await self.deps.resolve_canonical_scope_async(
                        settings=self.runtime.settings,
                        capture_discovery_errors=True,
                    )
            transport_diagnostics = (
                self.runtime.bybit_spot_v2_transport.get_transport_diagnostics()
                if self.runtime.bybit_spot_v2_transport is not None
                else {}
            )
            recovery_diagnostics = (
                self.runtime.bybit_spot_v2_recovery.get_recovery_diagnostics()
                if self.runtime.bybit_spot_v2_recovery is not None
                else {}
            )
            transport_symbols = (
                tuple(str(symbol) for symbol in self.runtime.bybit_spot_v2_transport.symbols)
                if self.runtime.bybit_spot_v2_transport is not None
                and hasattr(self.runtime.bybit_spot_v2_transport, "symbols")
                else tuple(str(symbol) for symbol in transport_diagnostics.get("symbols", ()) if isinstance(symbol, str))
            )
            recovery_symbols = (
                tuple(str(symbol) for symbol in self.runtime.bybit_spot_v2_recovery.symbols)
                if self.runtime.bybit_spot_v2_recovery is not None
                and hasattr(self.runtime.bybit_spot_v2_recovery, "symbols")
                else ()
            )
            if not recovery_symbols:
                recovery_symbols = tuple(
                    str(symbol)
                    for symbol in recovery_diagnostics.get("target_symbols", ())
                    if isinstance(symbol, str)
                )
            monitoring_symbols = self.deps.resolve_monitoring_symbols(
                resolved_scope=resolved_scope,
            )
            monitoring_scope = _resolve_monitoring_scope(
                resolved_scope=resolved_scope,
                monitoring_symbols=monitoring_symbols,
            )
            if (
                transport_symbols != monitoring_symbols
                or recovery_symbols != monitoring_symbols
                or self.runtime.bybit_spot_market_data_scope_summary != resolved_scope.truth
            ):
                self.runtime.bybit_spot_v2_transport = self.deps.build_transport_connector(
                    settings=self.runtime.settings,
                    db_manager=self.runtime.db_manager,
                    market_data_runtime=self.runtime.market_data_runtime,
                    resolved_scope=monitoring_scope,
                )
                self.runtime.bybit_spot_v2_recovery = self.deps.build_recovery_orchestrator(
                    settings=self.runtime.settings,
                    db_manager=self.runtime.db_manager,
                    resolved_scope=monitoring_scope,
                )
                self.runtime.bybit_spot_market_data_scope_summary = resolved_scope.truth
                self.runtime.bybit_spot_market_data_apply_truth = self.deps.build_runtime_apply_truth(
                    settings=self.runtime.settings,
                    contour="spot",
                    resolved_scope=resolved_scope,
                    connector=self.runtime.bybit_spot_market_data_connector,
                )
        if self.runtime.bybit_spot_v2_transport is not None and self.runtime.bybit_spot_v2_transport_task is None:
            if not self.runtime.market_data_runtime.is_started:
                await self.runtime.market_data_runtime.start()
            prepare_storage = getattr(self.runtime.bybit_spot_v2_transport, "prepare_storage", None)
            if callable(prepare_storage):
                await prepare_storage()
            get_logger(__name__).info(
                "Bybit spot v2 transport task scheduling",
                exchange="bybit_spot_v2",
            )
            self.runtime.bybit_spot_v2_transport_task = asyncio.create_task(
                self.runtime.bybit_spot_v2_transport.run(),
                name="production_bybit_spot_v2_transport",
            )

    async def start_v2_recovery(self) -> None:
        if self.runtime.bybit_spot_v2_transport is None:
            return
        self._state.recovery_retry_after = None
        if (
            self.runtime.bybit_spot_v2_recovery_task is not None
            and self.runtime.bybit_spot_v2_recovery_task.done()
        ):
            self.runtime.bybit_spot_v2_recovery_task = None
        if (
            self.runtime.bybit_spot_v2_recovery is not None
            and self.runtime.bybit_spot_v2_recovery_task is None
        ):
            prepare_storage = getattr(self.runtime.bybit_spot_v2_recovery, "prepare_storage", None)
            if callable(prepare_storage):
                await prepare_storage()
            get_logger(__name__).info(
                "Bybit spot v2 recovery task scheduling",
                exchange="bybit_spot_v2",
            )
            self.runtime.bybit_spot_v2_recovery_task = asyncio.create_task(
                self.runtime.bybit_spot_v2_recovery.run(),
                name="production_bybit_spot_v2_recovery",
            )
        self.ensure_retention_maintenance_loop()

    async def stop_market_data_connector(self) -> None:
        if self.runtime.bybit_spot_market_data_connector is not None:
            with contextlib.suppress(Exception):
                await self.runtime.bybit_spot_market_data_connector.stop()
        if self.runtime.bybit_spot_market_data_connector_task is not None:
            task = self.runtime.bybit_spot_market_data_connector_task
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception, TimeoutError):
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=self.deps.join_timeout_seconds,
                )
            if task.done():
                self.runtime.bybit_spot_market_data_connector_task = None
            else:
                self.runtime._track_background_connector_shutdown(
                    task=task,
                    attr_name="bybit_spot_market_data_connector_task",
                )

    async def stop_v2_transport(self) -> None:
        if self.runtime.bybit_spot_v2_transport is not None:
            with contextlib.suppress(Exception):
                await self.runtime.bybit_spot_v2_transport.stop()
        if self.runtime.bybit_spot_v2_transport_task is not None:
            task = self.runtime.bybit_spot_v2_transport_task
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception, TimeoutError):
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=self.deps.join_timeout_seconds,
                )
            if task.done():
                self.runtime.bybit_spot_v2_transport_task = None
            else:
                self.runtime._track_background_connector_shutdown(
                    task=task,
                    attr_name="bybit_spot_v2_transport_task",
                )
        self.runtime.bybit_spot_v2_transport = None

    async def stop_v2_recovery(self) -> None:
        if self.runtime.bybit_spot_v2_recovery is not None:
            with contextlib.suppress(Exception):
                await self.runtime.bybit_spot_v2_recovery.stop()
        if self.runtime.bybit_spot_v2_recovery_task is not None:
            task = self.runtime.bybit_spot_v2_recovery_task
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception, TimeoutError):
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=self.deps.join_timeout_seconds,
                )
            if task.done():
                self.runtime.bybit_spot_v2_recovery_task = None
            else:
                self.runtime._track_background_connector_shutdown(
                    task=task,
                    attr_name="bybit_spot_v2_recovery_task",
                )
        self.runtime.bybit_spot_v2_recovery = None

    async def apply_runtime_plan(
        self,
        *,
        settings: Settings,
        resolved_scope: Any,
        restart_required: bool,
    ) -> None:
        generation = self.deps.resolve_runtime_generation(contour="spot")
        scope_truth_is_final = _spot_scope_truth_is_final_for_settings(
            settings=settings,
            truth=resolved_scope.truth,
        )
        if generation == "v2" and not scope_truth_is_final:
            try:
                resolved_scope = await self.resolve_final_scope(
                    settings=settings,
                    resolved_scope=resolved_scope,
                )
                scope_truth_is_final = _spot_scope_truth_is_final_for_settings(
                    settings=settings,
                    truth=resolved_scope.truth,
                )
            except TimeoutError:
                self._state.finalized_startup_retry_after = datetime.now(tz=UTC) + timedelta(
                    seconds=_BYBIT_SPOT_FINALIZED_STARTUP_RETRY_BACKOFF_SECONDS
                )
                get_logger(__name__).warning(
                    "Bybit spot v2 apply deferred strict finalization until exact cache warmup",
                    coarse_symbols=len(getattr(resolved_scope.truth, "coarse_selected_symbols", ()) or ()),
                    selected_symbols=len(getattr(resolved_scope.truth, "selected_symbols", ()) or ()),
                    restart_required=restart_required,
                )
        if restart_required:
            self.reset_product_snapshot_cache()
        if generation == "v2" and not scope_truth_is_final:
            self._state.exact_trade_cache_by_symbol = None
            self._state.exact_trade_cache_symbols = None
            self._state.exact_trade_cache_observed_at = None
            self._state.exact_trade_cache_expires_at = None
        candidate_connector = self.deps.build_selected_connector(
            settings=settings,
            db_manager=self.runtime.db_manager,
            market_data_runtime=self.runtime.market_data_runtime,
            resolved_scope=resolved_scope,
        )
        monitoring_symbols = self.deps.resolve_monitoring_symbols(
            resolved_scope=resolved_scope,
        )
        monitoring_scope = _resolve_monitoring_scope(
            resolved_scope=resolved_scope,
            monitoring_symbols=monitoring_symbols,
        )
        candidate_transport = self.deps.build_transport_connector(
            settings=settings,
            db_manager=self.runtime.db_manager,
            market_data_runtime=self.runtime.market_data_runtime,
            resolved_scope=monitoring_scope,
        )
        candidate_recovery = self.deps.build_recovery_orchestrator(
            settings=settings,
            db_manager=self.runtime.db_manager,
            resolved_scope=monitoring_scope,
        )
        if restart_required:
            await self.stop_v2_recovery()
            await self.stop_v2_transport()
            await self.stop_market_data_connector()
            self.runtime.bybit_spot_market_data_connector = candidate_connector
            self.runtime.bybit_spot_v2_transport = candidate_transport if generation == "v2" else None
            self.runtime.bybit_spot_v2_recovery = candidate_recovery if generation == "v2" else None
            self.runtime.bybit_spot_market_data_scope_summary = resolved_scope.truth
            self.runtime.bybit_spot_market_data_apply_truth = self.deps.build_runtime_apply_truth(
                settings=settings,
                contour="spot",
                resolved_scope=resolved_scope,
                connector=candidate_connector,
            )
            if self.runtime._started:
                if generation == "legacy" and self.runtime.bybit_spot_market_data_connector is not None:
                    await self.start_market_data_connector()
                if generation == "v2":
                    await self.start_v2_transport(resolved_scope=resolved_scope)
                    await self.start_v2_recovery()
                    if scope_truth_is_final:
                        self._seed_exact_trade_cache_from_final_scope(resolved_scope=resolved_scope)
                    else:
                        self.ensure_finalized_startup_if_needed()
            return
        apply_status = "applied"
        apply_reason: str | None = None
        if generation == "legacy" and self.runtime.bybit_spot_market_data_connector is not None:
            apply_status = await self.runtime.bybit_spot_market_data_connector.update_universe_trade_count_threshold(
                resolved_scope.truth.trade_count_filter_minimum
            )
            if not isinstance(apply_status, str) or not apply_status:
                apply_status = "applied"
            if apply_status == "deferred":
                apply_reason = "transport_reconnect_pending"
        self.runtime.bybit_spot_market_data_scope_summary = resolved_scope.truth
        self.runtime.bybit_spot_market_data_apply_truth = self.deps.build_runtime_apply_truth(
            settings=settings,
            contour="spot",
            resolved_scope=resolved_scope,
            connector=self.runtime.bybit_spot_market_data_connector,
            apply_status=apply_status,
            apply_reason=apply_reason,
        )
        if generation == "v2" and not scope_truth_is_final:
            self.schedule_exact_trade_cache_refresh(
                symbols=_resolve_snapshot_symbols_from_truth(
                    truth=resolved_scope.truth,
                    settings=settings,
                )
            )
            self.ensure_finalized_startup_if_needed()

    async def resolve_final_scope(
        self,
        *,
        settings: Settings,
        resolved_scope: Any,
    ) -> Any:
        coarse_symbols = resolved_scope.truth.coarse_selected_symbols or resolved_scope.symbols
        if coarse_symbols == ():
            if getattr(resolved_scope.truth, "selected_trade_count_24h_is_final", None) is True:
                return resolved_scope
            return type(resolved_scope)(
                symbols=resolved_scope.symbols,
                truth=_replace_truth(
                    resolved_scope.truth,
                    selected_trade_count_24h_is_final=True,
                    selected_trade_count_24h_empty_scope_confirmed=True,
                ),
            )
        min_trade_count_24h = max(
            0,
            int(self.deps.resolve_min_trade_count_24h(settings=settings, contour="spot")),
        )
        if min_trade_count_24h <= 0:
            return type(resolved_scope)(
                symbols=coarse_symbols,
                truth=_replace_truth(
                    resolved_scope.truth,
                    trade_count_filter_minimum=min_trade_count_24h,
                    selected_symbols=coarse_symbols,
                    instruments_passed_final_filter=len(coarse_symbols),
                    selected_quote_volume_24h_usd_by_symbol=(
                        resolved_scope.truth.coarse_selected_quote_volume_24h_usd_by_symbol
                        or resolved_scope.truth.selected_quote_volume_24h_usd_by_symbol
                    ),
                    selected_trade_count_24h_is_final=True,
                    selected_trade_count_24h_empty_scope_confirmed=False,
                ),
            )
        observed_at = datetime.now(tz=UTC)
        get_logger(__name__).info(
            "Bybit spot v2 final scope exact snapshot fetch started",
            coarse_symbols=len(coarse_symbols),
            min_trade_count_24h=min_trade_count_24h,
        )
        current_truth = self.runtime.bybit_spot_market_data_scope_summary
        should_bypass_cache = not bool(
            tuple(str(symbol) for symbol in getattr(current_truth, "selected_symbols", ()) or ())
        )
        if should_bypass_cache:
            persisted_trade_snapshot_by_symbol = await self.get_fresh_exact_trade_counts_by_symbol(
                symbols=coarse_symbols,
                observed_at=observed_at,
                window_hours=24,
                ttl_seconds=10,
            )
        else:
            persisted_trade_snapshot_by_symbol = await self.get_cached_exact_trade_counts_by_symbol(
                symbols=coarse_symbols,
                observed_at=observed_at,
                window_hours=24,
                ttl_seconds=max(10, int(self._state.final_scope_refresh_seconds)),
            )
        get_logger(__name__).info(
            "Bybit spot v2 final scope exact snapshot fetch resolved",
            coarse_symbols=len(coarse_symbols),
            exact_symbols=len(persisted_trade_snapshot_by_symbol),
        )
        self._state.latest_final_scope_exact_snapshots = dict(persisted_trade_snapshot_by_symbol)
        self._state.latest_final_scope_exact_symbols = tuple(str(symbol) for symbol in coarse_symbols)
        self._state.latest_final_scope_exact_observed_at = observed_at
        previously_selected_symbols = set(
            resolved_scope.truth.selected_symbols or self.get_runtime_status().get("symbols", ())
        )
        monitoring_symbols = tuple(
            symbol
            for symbol in coarse_symbols
            if (
                self.is_snapshot_coverage_incomplete(
                    coverage_status=str(
                        getattr(
                            persisted_trade_snapshot_by_symbol.get(symbol),
                            "coverage_status",
                            "empty",
                        )
                    )
                )
            )
            or (
                int(
                    getattr(
                        persisted_trade_snapshot_by_symbol.get(symbol),
                        "persisted_trade_count_24h",
                        0,
                    )
                ) >= min_trade_count_24h
            )
            or (
                symbol in previously_selected_symbols
                and self.should_retain_symbol_during_incomplete_coverage(
                    symbol=symbol,
                    coverage_status=str(
                        getattr(
                            persisted_trade_snapshot_by_symbol.get(symbol),
                            "coverage_status",
                            "empty",
                        )
                    ),
                )
            )
        )
        selected_symbols = tuple(
            symbol
            for symbol in monitoring_symbols
            if (
                (symbol_snapshot := persisted_trade_snapshot_by_symbol.get(symbol)) is not None
                and _snapshot_passes_final_trade_filter_for_publication(
                    exact_snapshot=symbol_snapshot,
                    min_trade_count_24h=min_trade_count_24h,
                    module=self,
                )
            )
        )
        selected_trade_counts = tuple(
            (
                symbol,
                int(
                    getattr(
                        persisted_trade_snapshot_by_symbol.get(symbol),
                        "persisted_trade_count_24h",
                        0,
                    )
                ),
            )
            for symbol in selected_symbols
        )
        selected_trade_count_24h_is_final = all(
            not self.is_snapshot_coverage_incomplete(
                coverage_status=str(
                    getattr(
                        persisted_trade_snapshot_by_symbol.get(symbol),
                        "coverage_status",
                        "empty",
                    )
                )
            )
            for symbol in monitoring_symbols
        )
        if (
            not monitoring_symbols
            and self.is_trade_truth_coverage_incomplete()
            and current_truth is not None
            and (current_truth.coarse_selected_symbols or current_truth.selected_symbols)
        ):
            retained_monitoring_symbols = tuple(
                str(symbol)
                for symbol in (
                    current_truth.coarse_selected_symbols or current_truth.selected_symbols
                )
            )
            retained_monitoring_symbol_set = set(retained_monitoring_symbols)
            coarse_quote_volume = (
                resolved_scope.truth.coarse_selected_quote_volume_24h_usd_by_symbol
                or resolved_scope.truth.selected_quote_volume_24h_usd_by_symbol
            )
            retained_quote_volume = tuple(
                (symbol, volume)
                for symbol, volume in coarse_quote_volume
                if symbol in retained_monitoring_symbol_set
            )
            return type(resolved_scope)(
                symbols=retained_monitoring_symbols,
                truth=_replace_truth(
                    resolved_scope.truth,
                    trade_count_filter_minimum=min_trade_count_24h,
                    selected_symbols=(),
                    instruments_passed_final_filter=0,
                    selected_quote_volume_24h_usd_by_symbol=retained_quote_volume,
                    selected_trade_count_24h_by_symbol=(),
                    selected_trade_count_24h_is_final=False,
                    selected_trade_count_24h_empty_scope_confirmed=False,
                ),
            )
        if (
            monitoring_symbols == resolved_scope.symbols
            and resolved_scope.truth.selected_symbols == selected_symbols
            and resolved_scope.truth.selected_trade_count_24h_by_symbol == selected_trade_counts
            and getattr(resolved_scope.truth, "selected_trade_count_24h_is_final", None)
            is selected_trade_count_24h_is_final
        ):
            return resolved_scope
        selected_symbol_set = set(selected_symbols)
        coarse_quote_volume = (
            resolved_scope.truth.coarse_selected_quote_volume_24h_usd_by_symbol
            or resolved_scope.truth.selected_quote_volume_24h_usd_by_symbol
        )
        filtered_quote_volume = tuple(
            (symbol, volume)
            for symbol, volume in coarse_quote_volume
            if symbol in selected_symbol_set
        )
        empty_scope_confirmed = (
            not selected_symbols
            and bool(coarse_symbols)
            and all(
                not self.is_snapshot_coverage_incomplete(
                    coverage_status=str(
                        getattr(
                            persisted_trade_snapshot_by_symbol.get(symbol),
                            "coverage_status",
                            "empty",
                        )
                    )
                )
                for symbol in coarse_symbols
            )
        )
        return type(resolved_scope)(
            symbols=monitoring_symbols,
            truth=_replace_truth(
                resolved_scope.truth,
                trade_count_filter_minimum=min_trade_count_24h,
                selected_symbols=selected_symbols,
                instruments_passed_final_filter=len(selected_symbols),
                selected_quote_volume_24h_usd_by_symbol=filtered_quote_volume,
                selected_trade_count_24h_by_symbol=selected_trade_counts,
                selected_trade_count_24h_is_final=selected_trade_count_24h_is_final,
                selected_trade_count_24h_empty_scope_confirmed=empty_scope_confirmed,
            ),
        )

    def _seed_exact_trade_cache_from_final_scope(self, *, resolved_scope: Any) -> None:
        snapshots = self._state.latest_final_scope_exact_snapshots
        observed_at = self._state.latest_final_scope_exact_observed_at
        if not snapshots or observed_at is None:
            return
        current_symbols = _resolve_snapshot_symbols_from_truth(
            truth=resolved_scope.truth,
            settings=self.runtime.settings,
        )
        if not current_symbols:
            return
        filtered_snapshots = {
            symbol: snapshot for symbol, snapshot in snapshots.items() if symbol in set(current_symbols)
        }
        if len(filtered_snapshots) != len(current_symbols):
            return
        self._state.exact_trade_cache_by_symbol = filtered_snapshots
        self._state.exact_trade_cache_symbols = tuple(current_symbols)
        self._state.exact_trade_cache_observed_at = observed_at
        self._state.exact_trade_cache_expires_at = observed_at + timedelta(
            seconds=max(30, int(self._state.stable_final_scope_refresh_seconds))
        )
        self._state.exact_trade_cache_retry_after = None

    async def set_enabled(self, enabled: bool) -> dict[str, Any]:
        candidate_payload = self.runtime.settings.model_dump(mode="python")
        candidate_payload["bybit_spot_market_data_connector_enabled"] = enabled
        candidate_settings = Settings.model_validate(candidate_payload)
        generation = self.deps.resolve_runtime_generation(contour="spot")
        previous_signature = self.deps.build_runtime_signature(
            settings=self.runtime.settings,
            contour="spot",
        )
        candidate_signature = self.deps.build_runtime_signature(
            settings=candidate_settings,
            contour="spot",
        )
        if enabled:
            resolved_scope = self.deps.reuse_scope_if_possible(
                settings=candidate_settings,
                contour="spot",
                existing_truth=self.runtime.bybit_spot_market_data_scope_summary,
            ) or await self.deps.resolve_canonical_scope_async(
                settings=candidate_settings,
                capture_discovery_errors=True,
            )
        else:
            resolved_scope = self.deps.resolve_disabled_toggle_scope(
                settings=candidate_settings,
                contour="spot",
                existing_truth=self.runtime.bybit_spot_market_data_scope_summary,
            )
        await self.apply_runtime_plan(
            settings=candidate_settings,
            resolved_scope=resolved_scope,
            restart_required=previous_signature != candidate_signature,
        )
        updated_settings = self.deps.update_settings(
            {"bybit_spot_market_data_connector_enabled": enabled}
        )
        self.runtime.settings = updated_settings
        self.mark_product_snapshot_stale()
        self.schedule_product_snapshot_refresh()
        if self.runtime._started and generation == "v2":
            if enabled:
                if self.runtime.bybit_spot_v2_transport is None or self.runtime.bybit_spot_v2_recovery is None:
                    await self.apply_runtime_plan(
                        settings=candidate_settings,
                        resolved_scope=resolved_scope,
                        restart_required=True,
                    )
                await self.start_v2_transport(resolved_scope=resolved_scope)
                await self.start_v2_recovery()
                self.ensure_retention_maintenance_loop()
            else:
                if self._state.retention_maintenance_task is not None:
                    self._state.retention_maintenance_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await self._state.retention_maintenance_task
                    self._state.retention_maintenance_task = None
                await self.stop_v2_recovery()
                await self.stop_v2_transport()
        await self.runtime._refresh_runtime_health_after_bybit_toggle()
        return self.runtime.get_runtime_diagnostics()

    async def set_runtime_desired_running(self, desired_running: bool) -> dict[str, object]:
        await self.set_enabled(desired_running)
        return self.get_runtime_status()
