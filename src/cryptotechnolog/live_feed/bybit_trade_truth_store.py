"""Explicit local operational trade-truth layer for Bybit connector."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from .bybit_trade_count import (
    BybitDerivedTradeCountDiagnostics,
    BybitDerivedTradeCountPersistenceStore,
    BybitDerivedTradeCountTracker,
)

if TYPE_CHECKING:
    from .bybit import (
        BybitLedgerTradeCountScopeStatus,
        BybitLedgerTradeCountSymbolSnapshot,
        BybitLedgerTradeCountSymbolStatus,
    )
    from .bybit_trade_backfill import BybitHistoricalTradeBackfillResult
    from .bybit_trade_ledger_query import BybitTradeLedgerTradeCountQueryService


@dataclass(slots=True)
class BybitTradeTruthStore:
    """Operational/local trade truth for live, restored, and persisted state.

    This store is connector-owned runtime truth only. It may cache ledger snapshots for
    reconciliation, but it is not the canonical owner of product trade truth.
    """

    symbols: tuple[str, ...]
    admission_enabled: bool
    derived_trade_count_store: BybitDerivedTradeCountPersistenceStore | None = None
    ledger_trade_count_query_service: BybitTradeLedgerTradeCountQueryService | None = None
    _derived_trade_count: BybitDerivedTradeCountTracker = field(init=False, repr=False)
    _ledger_trade_count_snapshot_by_symbol: dict[str, BybitLedgerTradeCountSymbolSnapshot] = field(
        init=False,
        repr=False,
    )
    _ledger_trade_count_24h_by_symbol: dict[str, int | None] = field(init=False, repr=False)
    _ledger_trade_count_scope_status: BybitLedgerTradeCountScopeStatus = field(
        init=False,
        repr=False,
    )
    _ledger_trade_count_available: bool = field(init=False, repr=False)
    _ledger_trade_count_last_error: str | None = field(init=False, repr=False)
    _ledger_trade_count_last_synced_at: datetime | None = field(init=False, repr=False)
    _persisted_state_loaded: bool = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._derived_trade_count = BybitDerivedTradeCountTracker(symbols=self.symbols)
        initial_ledger_status: BybitLedgerTradeCountSymbolStatus = (
            "missing" if self.ledger_trade_count_query_service is not None else "not_configured"
        )
        self._ledger_trade_count_snapshot_by_symbol: dict[
            str, BybitLedgerTradeCountSymbolSnapshot
        ] = {
            symbol: self._make_ledger_snapshot(
                trade_count_24h=None,
                status=initial_ledger_status,
                last_error=(
                    None
                    if self.ledger_trade_count_query_service is not None
                    else "not_configured"
                ),
                last_synced_at=None,
            )
            for symbol in self.symbols
        }
        self._ledger_trade_count_24h_by_symbol: dict[str, int | None] = {}
        self._ledger_trade_count_scope_status: BybitLedgerTradeCountScopeStatus = (
            "ready" if self.ledger_trade_count_query_service is not None else "not_configured"
        )
        self._ledger_trade_count_available = self.ledger_trade_count_query_service is not None
        self._ledger_trade_count_last_error: str | None = (
            None if self.ledger_trade_count_query_service is not None else "not_configured"
        )
        self._ledger_trade_count_last_synced_at: datetime | None = None
        self._persisted_state_loaded = False
        self._sync_ledger_trade_count_compatibility_view()

    @property
    def derived_trade_count(self) -> BybitDerivedTradeCountTracker:
        return self._derived_trade_count

    @property
    def has_restored_historical_window(self) -> bool:
        return self._derived_trade_count.has_restored_historical_window

    @property
    def ready(self) -> bool:
        return self._derived_trade_count.ready

    @property
    def ledger_trade_count_snapshot_by_symbol(self) -> dict[str, BybitLedgerTradeCountSymbolSnapshot]:
        return self._ledger_trade_count_snapshot_by_symbol

    @ledger_trade_count_snapshot_by_symbol.setter
    def ledger_trade_count_snapshot_by_symbol(
        self,
        value: dict[str, BybitLedgerTradeCountSymbolSnapshot],
    ) -> None:
        self._ledger_trade_count_snapshot_by_symbol = dict(value)
        self._sync_ledger_trade_count_compatibility_view()

    @property
    def ledger_trade_count_24h_by_symbol(self) -> dict[str, int | None]:
        return self._ledger_trade_count_24h_by_symbol

    @property
    def ledger_trade_count_scope_status(self) -> BybitLedgerTradeCountScopeStatus:
        return self._ledger_trade_count_scope_status

    @ledger_trade_count_scope_status.setter
    def ledger_trade_count_scope_status(self, value: BybitLedgerTradeCountScopeStatus) -> None:
        self._ledger_trade_count_scope_status = value

    @property
    def ledger_trade_count_available(self) -> bool:
        return self._ledger_trade_count_available

    @ledger_trade_count_available.setter
    def ledger_trade_count_available(self, value: bool) -> None:
        self._ledger_trade_count_available = bool(value)

    @property
    def ledger_trade_count_last_error(self) -> str | None:
        return self._ledger_trade_count_last_error

    @ledger_trade_count_last_error.setter
    def ledger_trade_count_last_error(self, value: str | None) -> None:
        self._ledger_trade_count_last_error = value

    @property
    def ledger_trade_count_last_synced_at(self) -> datetime | None:
        return self._ledger_trade_count_last_synced_at

    @ledger_trade_count_last_synced_at.setter
    def ledger_trade_count_last_synced_at(self, value: datetime | None) -> None:
        self._ledger_trade_count_last_synced_at = value

    def restore_persisted_state(self, *, restored_at: datetime) -> None:
        if self.derived_trade_count_store is None:
            return
        persisted_state = self.derived_trade_count_store.load()
        if persisted_state is None:
            return
        self._persisted_state_loaded = True
        self._derived_trade_count.restore_from_persisted_state(
            persisted_state,
            restored_at=restored_at,
        )

    async def bootstrap_from_local_ledger(
        self,
        *,
        observed_at: datetime,
        exchange: str,
        contour: str,
    ) -> bool:
        service = self.ledger_trade_count_query_service
        if (
            not self.admission_enabled
            or service is None
            or not self._persisted_state_loaded
        ):
            return False
        normalized_observed_at = observed_at.astimezone(UTC)
        trade_buckets_by_symbol: dict[str, dict[datetime, int]] = {}
        exact_trade_timestamps_by_symbol: dict[str, tuple[datetime, ...]] = {}
        latest_trade_at_by_symbol: dict[str, datetime | None] = {}
        snapshots: dict[str, BybitLedgerTradeCountSymbolSnapshot] = {}
        window_started_at: datetime | None = None
        for symbol in self.symbols:
            result = await service.get_trade_count_24h(
                exchange=exchange,
                contour=contour,
                normalized_symbol=symbol,
                window_ended_at=normalized_observed_at,
            )
            symbol_buckets: dict[datetime, int] = {}
            for row in result.matched_rows:
                bucket_start = row.exchange_trade_at.astimezone(UTC).replace(second=0, microsecond=0)
                symbol_buckets[bucket_start] = symbol_buckets.get(bucket_start, 0) + 1
            exact_trade_timestamps_by_symbol[symbol] = tuple(
                row.exchange_trade_at.astimezone(UTC) for row in result.matched_rows
            )
            trade_buckets_by_symbol[symbol] = symbol_buckets
            latest_trade_at_by_symbol[symbol] = (
                result.matched_rows[-1].exchange_trade_at if result.matched_rows else None
            )
            snapshots[symbol] = self._make_ledger_snapshot(
                trade_count_24h=result.trade_count_24h,
                status="fresh",
                last_error=None,
                last_synced_at=normalized_observed_at,
                window_started_at=result.window_started_at,
                first_trade_at=result.first_trade_at,
                sources=result.sources,
            )
            if window_started_at is None:
                window_started_at = result.window_started_at
        if window_started_at is None:
            return False
        self._derived_trade_count.restore_exact_window(
            trade_buckets_by_symbol=trade_buckets_by_symbol,
            exact_trade_timestamps_by_symbol=exact_trade_timestamps_by_symbol,
            latest_trade_at_by_symbol=latest_trade_at_by_symbol,
            window_started_at=window_started_at,
            observed_at=normalized_observed_at,
        )
        self._ledger_trade_count_snapshot_by_symbol.update(snapshots)
        self._ledger_trade_count_scope_status = "ready"
        self._ledger_trade_count_available = True
        self._ledger_trade_count_last_error = None
        self._ledger_trade_count_last_synced_at = normalized_observed_at
        self._sync_ledger_trade_count_compatibility_view()
        return True

    def initialize_backfill_state(self, *, backfill_pending: bool) -> None:
        if not self.admission_enabled:
            self._derived_trade_count.mark_backfill_not_needed()
        elif backfill_pending:
            self._derived_trade_count.mark_backfill_pending()
        else:
            self._derived_trade_count.mark_backfill_not_needed()

    def get_trade_count_diagnostics(self, *, observed_at: datetime) -> BybitDerivedTradeCountDiagnostics:
        return self._derived_trade_count.get_diagnostics(observed_at=observed_at)

    def note_live_trade(self, *, symbol: str, observed_at: datetime) -> None:
        self._derived_trade_count.note_trade(symbol=symbol, observed_at=observed_at)

    def mark_gap(
        self,
        *,
        observed_at: datetime,
        reason: str,
        reuse_historical_window: bool,
    ) -> None:
        if reuse_historical_window:
            self._derived_trade_count.mark_gap_preserving_historical_window(
                observed_at=observed_at,
                reason=reason,
            )
            return
        self._derived_trade_count.mark_gap(observed_at=observed_at, reason=reason)

    def mark_backfill_pending(self, *, total_archives: int | None = None) -> None:
        self._derived_trade_count.mark_backfill_pending(total_archives=total_archives)

    def mark_backfill_running(self, *, processed_archives: int, total_archives: int) -> None:
        self._derived_trade_count.mark_backfill_running(
            processed_archives=processed_archives,
            total_archives=total_archives,
        )

    def mark_backfill_not_needed(self) -> None:
        self._derived_trade_count.mark_backfill_not_needed()

    def mark_backfill_skipped(
        self,
        *,
        observed_at: datetime,
        reason: str,
        source: str,
        processed_archives: int | None,
        total_archives: int | None,
    ) -> None:
        self._derived_trade_count.mark_backfill_skipped(
            observed_at=observed_at,
            reason=reason,
            source=source,
            processed_archives=processed_archives,
            total_archives=total_archives,
        )

    def mark_backfill_unavailable(
        self,
        *,
        observed_at: datetime,
        reason: str,
        source: str,
        processed_archives: int | None,
        total_archives: int | None,
    ) -> None:
        self._derived_trade_count.mark_backfill_unavailable(
            observed_at=observed_at,
            reason=reason,
            source=source,
            processed_archives=processed_archives,
            total_archives=total_archives,
        )

    def apply_historical_restore_result(
        self,
        *,
        result: BybitHistoricalTradeBackfillResult,
        observed_at: datetime,
        status: Literal["backfilled", "skipped"] | None = None,
    ) -> None:
        if result.restored_window_started_at is None or result.covered_until_at is None:
            return
        self._derived_trade_count.restore_historical_window(
            trades_by_symbol=result.trade_timestamps_by_symbol,
            trade_buckets_by_symbol=result.trade_buckets_by_symbol,
            latest_trade_at_by_symbol=result.latest_trade_at_by_symbol,
            window_started_at=result.restored_window_started_at,
            covered_until_at=result.covered_until_at,
            observed_at=observed_at,
            source=result.source,
            processed_archives=result.processed_archives,
            total_archives=result.total_archives,
            status=status or result.status,
            reason=result.reason,
        )

    def persist(self, *, observed_at: datetime, force: bool = False) -> None:
        if not self.admission_enabled:
            return
        normalized_observed_at = observed_at.astimezone(UTC)
        if not self._derived_trade_count.should_persist(
            observed_at=normalized_observed_at,
            force=force,
        ):
            return
        if self.derived_trade_count_store is None:
            return
        self.derived_trade_count_store.save(
            self._derived_trade_count.to_persisted_state(
                persisted_at=normalized_observed_at,
            )
        )
        self._derived_trade_count.mark_persisted(observed_at=normalized_observed_at)

    def set_ledger_trade_count_query_service(
        self,
        service: BybitTradeLedgerTradeCountQueryService | None,
    ) -> None:
        self.ledger_trade_count_query_service = service
        if service is None:
            self._ledger_trade_count_scope_status = "not_configured"
            self._ledger_trade_count_available = False
            self._ledger_trade_count_last_error = "not_configured"
            self._ledger_trade_count_last_synced_at = None
            self._ledger_trade_count_snapshot_by_symbol = {
                symbol: self._make_ledger_snapshot(
                    trade_count_24h=None,
                    status="not_configured",
                    last_error="not_configured",
                    last_synced_at=None,
                )
                for symbol in self.symbols
            }
            self._sync_ledger_trade_count_compatibility_view()
            return
        self._ledger_trade_count_scope_status = "ready"
        self._ledger_trade_count_available = True
        for symbol, snapshot in tuple(self._ledger_trade_count_snapshot_by_symbol.items()):
            if snapshot.status == "not_configured":
                self._ledger_trade_count_snapshot_by_symbol[symbol] = self._make_ledger_snapshot(
                    trade_count_24h=snapshot.trade_count_24h,
                    status="missing",
                    last_error=None,
                    last_synced_at=snapshot.last_synced_at,
                )
        if self._ledger_trade_count_last_error == "not_configured":
            self._ledger_trade_count_last_error = None
        self._sync_ledger_trade_count_compatibility_view()

    async def refresh_ledger_trade_count_snapshot(
        self,
        *,
        symbols: tuple[str, ...],
        observed_at: datetime,
        exchange: str,
        contour: str,
    ) -> None:
        service = self.ledger_trade_count_query_service
        if service is None:
            self._ledger_trade_count_scope_status = "not_configured"
            self._ledger_trade_count_available = False
            self._ledger_trade_count_last_error = "not_configured"
            for symbol in symbols:
                self._ledger_trade_count_snapshot_by_symbol[symbol] = self._make_ledger_snapshot(
                    trade_count_24h=None,
                    status="not_configured",
                    last_error="not_configured",
                    last_synced_at=None,
                )
            self._sync_ledger_trade_count_compatibility_view()
            return
        if not symbols:
            self._ledger_trade_count_snapshot_by_symbol = {}
            self._ledger_trade_count_scope_status = "ready"
            self._ledger_trade_count_available = True
            self._ledger_trade_count_last_error = None
            self._ledger_trade_count_last_synced_at = observed_at.astimezone(UTC)
            self._sync_ledger_trade_count_compatibility_view()
            return
        refreshed_any = False
        failed_symbols = 0
        scope_errors: list[str] = []
        for symbol in symbols:
            previous_snapshot = self._ledger_trade_count_snapshot_by_symbol.get(
                symbol,
                self._make_ledger_snapshot(
                    trade_count_24h=None,
                    status="missing",
                    last_error=None,
                    last_synced_at=None,
                ),
            )
            try:
                result = await service.get_trade_count_24h(
                    exchange=exchange,
                    contour=contour,
                    normalized_symbol=symbol,
                    window_ended_at=observed_at,
                )
                self._ledger_trade_count_snapshot_by_symbol[symbol] = self._make_ledger_snapshot(
                    trade_count_24h=result.trade_count_24h,
                    status="fresh",
                    last_error=None,
                    last_synced_at=observed_at.astimezone(UTC),
                    window_started_at=result.window_started_at,
                    first_trade_at=result.first_trade_at,
                    sources=result.sources,
                )
                refreshed_any = True
            except Exception as exc:
                failed_symbols += 1
                scope_errors.append(str(exc))
                if previous_snapshot.trade_count_24h is not None:
                    self._ledger_trade_count_snapshot_by_symbol[symbol] = self._make_ledger_snapshot(
                        trade_count_24h=previous_snapshot.trade_count_24h,
                        status="stale",
                        last_error=str(exc),
                        last_synced_at=previous_snapshot.last_synced_at,
                        window_started_at=previous_snapshot.window_started_at,
                        first_trade_at=previous_snapshot.first_trade_at,
                        sources=previous_snapshot.sources,
                    )
                else:
                    self._ledger_trade_count_snapshot_by_symbol[symbol] = self._make_ledger_snapshot(
                        trade_count_24h=None,
                        status="refresh_failed",
                        last_error=str(exc),
                        last_synced_at=None,
                    )
        if failed_symbols == 0:
            self._ledger_trade_count_scope_status = "ready"
            self._ledger_trade_count_last_error = None
        elif refreshed_any:
            self._ledger_trade_count_scope_status = "partial_refresh_failed"
            self._ledger_trade_count_last_error = scope_errors[0]
        else:
            self._ledger_trade_count_scope_status = "refresh_failed"
            self._ledger_trade_count_last_error = scope_errors[0] if scope_errors else None
        self._sync_ledger_trade_count_compatibility_view()

    def _sync_ledger_trade_count_compatibility_view(self) -> None:
        self._ledger_trade_count_24h_by_symbol = {
            symbol: snapshot.trade_count_24h
            for symbol, snapshot in self._ledger_trade_count_snapshot_by_symbol.items()
        }
        healthy_symbols = [
            snapshot
            for snapshot in self._ledger_trade_count_snapshot_by_symbol.values()
            if snapshot.status in {"fresh", "stale"}
        ]
        self._ledger_trade_count_available = bool(healthy_symbols)
        if healthy_symbols:
            latest_synced = [
                snapshot.last_synced_at
                for snapshot in healthy_symbols
                if snapshot.last_synced_at is not None
            ]
            self._ledger_trade_count_last_synced_at = max(latest_synced) if latest_synced else None

    def _make_ledger_snapshot(
        self,
        *,
        trade_count_24h: int | None,
        status: str,
        last_error: str | None,
        last_synced_at: datetime | None,
        window_started_at: datetime | None = None,
        first_trade_at: datetime | None = None,
        sources: tuple[str, ...] = (),
    ) -> BybitLedgerTradeCountSymbolSnapshot:
        from .bybit import BybitLedgerTradeCountSymbolSnapshot

        return BybitLedgerTradeCountSymbolSnapshot(
            trade_count_24h=trade_count_24h,
            status=status,
            last_error=last_error,
            last_synced_at=last_synced_at,
            window_started_at=window_started_at,
            first_trade_at=first_trade_at,
            sources=sources,
        )
