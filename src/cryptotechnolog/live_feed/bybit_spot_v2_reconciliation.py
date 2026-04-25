"""Read-only reconciliation slice between legacy derived counts and spot v2 persisted counts."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

from cryptotechnolog.config.settings import get_settings

from .bybit_spot_v2_persisted_query import (
    BybitSpotV2PersistedQueryService,
    BybitSpotV2PersistedWindowSnapshot,
)
from .bybit_trade_count import (
    BybitDerivedTradeCountPersistenceStore,
    BybitDerivedTradeCountTracker,
)


@dataclass(slots=True, frozen=True)
class BybitSpotV2DerivedSymbolSnapshot:
    normalized_symbol: str
    derived_trade_count_24h: int | None
    derived_state: str
    derived_ready: bool
    derived_reason: str | None = None


@dataclass(slots=True, frozen=True)
class BybitSpotV2ReconciliationSymbolSnapshot:
    normalized_symbol: str
    derived_trade_count_24h: int | None
    persisted_trade_count_24h: int
    absolute_diff: int | None
    reconciliation_verdict: str
    reconciliation_reason: str
    live_trade_count_24h: int
    archive_trade_count_24h: int
    earliest_trade_at: datetime | None
    latest_trade_at: datetime | None


@dataclass(slots=True, frozen=True)
class BybitSpotV2ReconciliationSnapshot:
    observed_at: datetime
    derived_persisted_at: datetime | None
    scope_verdict: str
    scope_reason: str
    symbols_covered: tuple[str, ...]
    derived_trade_count_24h: int | None
    persisted_trade_count_24h: int
    absolute_diff: int | None
    symbol_snapshots: tuple[BybitSpotV2ReconciliationSymbolSnapshot, ...]

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["observed_at"] = self.observed_at.isoformat()
        payload["derived_persisted_at"] = (
            self.derived_persisted_at.isoformat()
            if self.derived_persisted_at is not None
            else None
        )
        payload["symbol_snapshots"] = [
            {
                **asdict(snapshot),
                "earliest_trade_at": (
                    snapshot.earliest_trade_at.isoformat()
                    if snapshot.earliest_trade_at is not None
                    else None
                ),
                "latest_trade_at": (
                    snapshot.latest_trade_at.isoformat()
                    if snapshot.latest_trade_at is not None
                    else None
                ),
            }
            for snapshot in self.symbol_snapshots
        ]
        return payload


class BybitSpotV2DerivedTradeCountQueryService:
    """Read-only loader for the current persisted bybit_spot derived trade-count snapshot."""

    def __init__(self, *, store_path: Path | None = None) -> None:
        settings = get_settings()
        self._store_path = store_path or (
            settings.data_dir / "live_feed" / "bybit_spot_derived_trade_count.json"
        )

    def query_snapshot(
        self,
        *,
        symbols: tuple[str, ...],
        observed_at: datetime | None = None,
    ) -> tuple[datetime | None, tuple[BybitSpotV2DerivedSymbolSnapshot, ...]]:
        store = BybitDerivedTradeCountPersistenceStore(path=self._store_path)
        persisted_state = store.load()
        if persisted_state is None:
            normalized_observed_at = (observed_at or datetime.now(UTC)).astimezone(UTC)
            return None, tuple(
                BybitSpotV2DerivedSymbolSnapshot(
                    normalized_symbol=symbol,
                    derived_trade_count_24h=None,
                    derived_state="store_missing",
                    derived_ready=False,
                    derived_reason="legacy_derived_store_missing",
                )
                for symbol in symbols
            )
        effective_observed_at = (observed_at or persisted_state.persisted_at).astimezone(UTC)
        stale_restore = (
            effective_observed_at - persisted_state.persisted_at.astimezone(UTC)
            > timedelta(minutes=15)
        )
        if stale_restore:
            return persisted_state.persisted_at, tuple(
                BybitSpotV2DerivedSymbolSnapshot(
                    normalized_symbol=symbol,
                    derived_trade_count_24h=None,
                    derived_state="stale_persisted_snapshot",
                    derived_ready=False,
                    derived_reason="legacy_derived_snapshot_stale_after_primary_switch",
                )
                for symbol in symbols
            )
        tracker = BybitDerivedTradeCountTracker(symbols=symbols)
        tracker.restore_from_persisted_state(
            persisted_state,
            restored_at=effective_observed_at,
        )
        diagnostics = tracker.get_diagnostics(observed_at=effective_observed_at)
        snapshots = tuple(
            BybitSpotV2DerivedSymbolSnapshot(
                normalized_symbol=snapshot.symbol,
                derived_trade_count_24h=(
                    snapshot.trade_count_24h
                    if snapshot.trade_count_24h is not None
                    else _restore_derived_trade_count_from_persisted_buckets(
                        state=persisted_state,
                        symbol=snapshot.symbol,
                        observed_at=effective_observed_at,
                        derived_state=diagnostics.state,
                    )
                ),
                derived_state=diagnostics.state,
                derived_ready=diagnostics.ready,
                derived_reason=(
                    "legacy_derived_live_tail_pending"
                    if diagnostics.state == "live_tail_pending_after_gap"
                    else None
                ),
            )
            for snapshot in diagnostics.symbol_snapshots
        )
        return persisted_state.persisted_at, snapshots


def _restore_derived_trade_count_from_persisted_buckets(
    *,
    state: BybitDerivedTradeCountPersistedState,
    symbol: str,
    observed_at: datetime,
    derived_state: str,
) -> int | None:
    if derived_state != "live_tail_pending_after_gap":
        return None
    if not state.historical_window_restored:
        return None
    symbol_buckets = state.trade_count_buckets.get(symbol)
    if not symbol_buckets:
        return 0
    threshold = observed_at.astimezone(UTC) - timedelta(hours=24)
    return sum(
        int(count)
        for bucket_start, count in symbol_buckets.items()
        if threshold <= bucket_start.astimezone(UTC) <= observed_at.astimezone(UTC)
    )


class BybitSpotV2ReconciliationService:
    """Minimal read-only comparison between legacy derived and spot v2 persisted counts."""

    def __init__(
        self,
        *,
        persisted_query_service: BybitSpotV2PersistedQueryService,
        derived_query_service: BybitSpotV2DerivedTradeCountQueryService | None = None,
    ) -> None:
        self._persisted_query_service = persisted_query_service
        self._derived_query_service = derived_query_service or BybitSpotV2DerivedTradeCountQueryService()

    async def build_snapshot(
        self,
        *,
        symbols: tuple[str, ...],
        observed_at: datetime | None = None,
        window_hours: int = 24,
    ) -> BybitSpotV2ReconciliationSnapshot:
        derived_persisted_at, derived_snapshots = self._derived_query_service.query_snapshot(
            symbols=symbols,
            observed_at=observed_at,
        )
        effective_observed_at = (observed_at or derived_persisted_at or datetime.now(UTC)).astimezone(UTC)
        persisted_snapshot = await self._persisted_query_service.query_rolling_window(
            symbols=symbols,
            observed_at=effective_observed_at,
            window_hours=window_hours,
        )
        return _build_reconciliation_snapshot(
            observed_at=effective_observed_at,
            derived_persisted_at=derived_persisted_at,
            derived_snapshots=derived_snapshots,
            persisted_snapshot=persisted_snapshot,
        )


def _build_reconciliation_snapshot(
    *,
    observed_at: datetime,
    derived_persisted_at: datetime | None,
    derived_snapshots: tuple[BybitSpotV2DerivedSymbolSnapshot, ...],
    persisted_snapshot: BybitSpotV2PersistedWindowSnapshot,
) -> BybitSpotV2ReconciliationSnapshot:
    derived_by_symbol = {
        snapshot.normalized_symbol: snapshot
        for snapshot in derived_snapshots
    }
    symbol_snapshots: list[BybitSpotV2ReconciliationSymbolSnapshot] = []
    derived_total = 0
    derived_total_available = True
    mismatched = False
    unavailable = False
    retired_baseline = False
    for persisted_symbol in persisted_snapshot.symbols:
        derived_symbol = derived_by_symbol.get(persisted_symbol.normalized_symbol)
        derived_trade_count_24h = (
            derived_symbol.derived_trade_count_24h
            if derived_symbol is not None
            else None
        )
        absolute_diff = (
            abs(derived_trade_count_24h - persisted_symbol.persisted_trade_count_24h)
            if derived_trade_count_24h is not None
            else None
        )
        verdict, reason = _resolve_symbol_reconciliation_verdict(
            derived_trade_count_24h=derived_trade_count_24h,
            persisted_trade_count_24h=persisted_symbol.persisted_trade_count_24h,
            derived_state=(derived_symbol.derived_state if derived_symbol is not None else None),
            derived_reason=(derived_symbol.derived_reason if derived_symbol is not None else None),
        )
        if verdict == "mismatch":
            mismatched = True
        if verdict == "unavailable":
            unavailable = True
            derived_total_available = False
        if verdict == "retired_baseline":
            retired_baseline = True
            derived_total_available = False
        if derived_trade_count_24h is not None:
            derived_total += derived_trade_count_24h
        symbol_snapshots.append(
            BybitSpotV2ReconciliationSymbolSnapshot(
                normalized_symbol=persisted_symbol.normalized_symbol,
                derived_trade_count_24h=derived_trade_count_24h,
                persisted_trade_count_24h=persisted_symbol.persisted_trade_count_24h,
                absolute_diff=absolute_diff,
                reconciliation_verdict=verdict,
                reconciliation_reason=reason,
                live_trade_count_24h=persisted_symbol.live_trade_count_24h,
                archive_trade_count_24h=persisted_symbol.archive_trade_count_24h,
                earliest_trade_at=persisted_symbol.earliest_trade_at,
                latest_trade_at=persisted_symbol.latest_trade_at,
            )
        )
    if retired_baseline and not unavailable and not mismatched:
        scope_verdict = "retired_baseline"
        scope_reason = "legacy_baseline_frozen_after_primary_switch"
    elif unavailable:
        scope_reason = _resolve_scope_unavailable_reason(derived_snapshots=derived_snapshots)
        if scope_reason == "legacy_derived_snapshot_stale_after_primary_switch":
            scope_verdict = "retired_baseline"
            scope_reason = "legacy_baseline_frozen_after_primary_switch"
        else:
            scope_verdict = "unavailable"
    elif mismatched:
        scope_verdict = "mismatch"
        scope_reason = "symbol_mismatch_present"
    else:
        scope_verdict = "matched"
        scope_reason = "all_symbols_match"
    return BybitSpotV2ReconciliationSnapshot(
        observed_at=observed_at,
        derived_persisted_at=derived_persisted_at,
        scope_verdict=scope_verdict,
        scope_reason=scope_reason,
        symbols_covered=persisted_snapshot.symbols_covered,
        derived_trade_count_24h=(derived_total if derived_total_available else None),
        persisted_trade_count_24h=persisted_snapshot.persisted_trade_count_24h,
        absolute_diff=(
            abs(derived_total - persisted_snapshot.persisted_trade_count_24h)
            if derived_total_available
            else None
        ),
        symbol_snapshots=tuple(symbol_snapshots),
    )


def _resolve_symbol_reconciliation_verdict(
    *,
    derived_trade_count_24h: int | None,
    persisted_trade_count_24h: int,
    derived_state: str | None = None,
    derived_reason: str | None = None,
) -> tuple[str, str]:
    if derived_trade_count_24h is None:
        if derived_reason == "legacy_derived_snapshot_stale_after_primary_switch":
            return "retired_baseline", "legacy_baseline_frozen_after_primary_switch"
        return "unavailable", (
            derived_reason
            or derived_state
            or "derived_trade_count_unavailable"
        )
    if derived_trade_count_24h == persisted_trade_count_24h:
        return "matched", "exact_count_match"
    if persisted_trade_count_24h > derived_trade_count_24h:
        return "mismatch", "persisted_exceeds_derived"
    return "mismatch", "derived_exceeds_persisted"


def _resolve_scope_unavailable_reason(
    *,
    derived_snapshots: tuple[BybitSpotV2DerivedSymbolSnapshot, ...],
) -> str:
    reasons = {
        snapshot.derived_reason or snapshot.derived_state
        for snapshot in derived_snapshots
        if snapshot.derived_trade_count_24h is None
    }
    if len(reasons) == 1:
        return next(iter(reasons))
    return "derived_trade_count_unavailable"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only reconciliation snapshot between bybit_spot derived and spot v2 persisted counts.",
    )
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--observed-at", required=False)
    parser.add_argument("--window-hours", type=int, default=24)
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    from cryptotechnolog.core.database import DatabaseManager

    db_manager = DatabaseManager()
    try:
        service = BybitSpotV2ReconciliationService(
            persisted_query_service=BybitSpotV2PersistedQueryService(db_manager),
        )
        snapshot = await service.build_snapshot(
            symbols=tuple(args.symbols),
            observed_at=(
                datetime.fromisoformat(args.observed_at)
                if args.observed_at is not None
                else None
            ),
            window_hours=args.window_hours,
        )
        print(json.dumps(snapshot.as_dict()))
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(_main())


__all__ = [
    "BybitSpotV2DerivedTradeCountQueryService",
    "BybitSpotV2DerivedSymbolSnapshot",
    "BybitSpotV2ReconciliationService",
    "BybitSpotV2ReconciliationSnapshot",
    "BybitSpotV2ReconciliationSymbolSnapshot",
]
