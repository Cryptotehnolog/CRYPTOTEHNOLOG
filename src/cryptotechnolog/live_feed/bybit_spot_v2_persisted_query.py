"""Minimal rolling 24h persisted query/diagnostics slice for Bybit spot v2."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from cryptotechnolog.core.database import DatabaseManager

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(slots=True, frozen=True)
class BybitSpotV2PersistedSymbolSnapshot:
    normalized_symbol: str
    live_trade_count_24h: int
    archive_trade_count_24h: int
    persisted_trade_count_24h: int
    earliest_trade_at: datetime | None
    latest_trade_at: datetime | None
    coverage_status: str


@dataclass(slots=True, frozen=True)
class BybitSpotV2PersistedWindowSnapshot:
    observed_at: datetime
    window_started_at: datetime
    live_trade_count_24h: int
    archive_trade_count_24h: int
    persisted_trade_count_24h: int
    earliest_trade_at: datetime | None
    latest_trade_at: datetime | None
    symbols_covered: tuple[str, ...]
    coverage_status: str
    symbols: tuple[BybitSpotV2PersistedSymbolSnapshot, ...]

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["observed_at"] = self.observed_at.isoformat()
        payload["window_started_at"] = self.window_started_at.isoformat()
        payload["earliest_trade_at"] = (
            self.earliest_trade_at.isoformat() if self.earliest_trade_at is not None else None
        )
        payload["latest_trade_at"] = (
            self.latest_trade_at.isoformat() if self.latest_trade_at is not None else None
        )
        payload["symbols"] = [
            {
                **asdict(symbol),
                "earliest_trade_at": (
                    symbol.earliest_trade_at.isoformat()
                    if symbol.earliest_trade_at is not None
                    else None
                ),
                "latest_trade_at": (
                    symbol.latest_trade_at.isoformat()
                    if symbol.latest_trade_at is not None
                    else None
                ),
            }
            for symbol in self.symbols
        ]
        return payload


@dataclass(slots=True, frozen=True)
class BybitSpotV2RollingTradeCountSnapshot:
    normalized_symbol: str
    live_trade_count_24h: int
    archive_trade_count_24h: int
    persisted_trade_count_24h: int
    coverage_status: str


@dataclass(slots=True, frozen=True)
class _WindowStats:
    trade_count: int
    earliest_trade_at: datetime | None
    latest_trade_at: datetime | None


_ARCHIVE_WINDOW_ALLOWED_GAP = timedelta(minutes=10)


class BybitSpotV2PersistedQueryService:
    """Read rolling-window persisted state from separate spot v2 live+archive ledgers."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self._db_manager = db_manager
        self._query_indexes_ready = False

    async def _ensure_query_indexes(self) -> None:
        if self._query_indexes_ready:
            return
        # Query service must stay read-only on hot-path. Schema/index creation belongs
        # to the ledger repositories and startup initialization, not to live queries.
        self._query_indexes_ready = True

    async def query_rolling_window(
        self,
        *,
        symbols: Sequence[str],
        observed_at: datetime,
        window_hours: int = 24,
    ) -> BybitSpotV2PersistedWindowSnapshot:
        await self._ensure_query_indexes()
        normalized_symbols = tuple(str(symbol) for symbol in symbols)
        normalized_observed_at = observed_at.astimezone(UTC)
        window_started_at = normalized_observed_at - timedelta(hours=window_hours)
        archive_stats = await self._load_archive_stats(
            symbols=normalized_symbols,
            window_started_at=window_started_at,
            observed_at=normalized_observed_at,
        )
        live_stats = await self._load_live_window_stats_after_archive_boundary(
            symbols=normalized_symbols,
            window_started_at=window_started_at,
            observed_at=normalized_observed_at,
        )
        symbol_snapshots: list[BybitSpotV2PersistedSymbolSnapshot] = []
        live_total = 0
        archive_total = 0
        overall_earliest: datetime | None = None
        overall_latest: datetime | None = None
        symbols_covered: list[str] = []
        for symbol in normalized_symbols:
            live = live_stats.get(symbol, _WindowStats(0, None, None))
            archive = archive_stats.get(symbol, _WindowStats(0, None, None))
            persisted_total = live.trade_count + archive.trade_count
            earliest = _min_datetime(live.earliest_trade_at, archive.earliest_trade_at)
            latest = _max_datetime(live.latest_trade_at, archive.latest_trade_at)
            coverage_status = _resolve_symbol_coverage_status(
                observed_at=normalized_observed_at,
                window_started_at=window_started_at,
                live_trade_count=live.trade_count,
                archive_trade_count=archive.trade_count,
                archive_latest_trade_at=archive.latest_trade_at,
            )
            if persisted_total > 0:
                symbols_covered.append(symbol)
                overall_earliest = _min_datetime(overall_earliest, earliest)
                overall_latest = _max_datetime(overall_latest, latest)
            live_total += live.trade_count
            archive_total += archive.trade_count
            symbol_snapshots.append(
                BybitSpotV2PersistedSymbolSnapshot(
                    normalized_symbol=symbol,
                    live_trade_count_24h=live.trade_count,
                    archive_trade_count_24h=archive.trade_count,
                    persisted_trade_count_24h=persisted_total,
                    earliest_trade_at=earliest,
                    latest_trade_at=latest,
                    coverage_status=coverage_status,
                )
            )
        return BybitSpotV2PersistedWindowSnapshot(
            observed_at=normalized_observed_at,
            window_started_at=window_started_at,
            live_trade_count_24h=live_total,
            archive_trade_count_24h=archive_total,
            persisted_trade_count_24h=archive_total + live_total,
            earliest_trade_at=overall_earliest,
            latest_trade_at=overall_latest,
            symbols_covered=tuple(symbols_covered),
            coverage_status=_resolve_window_coverage_status(
                requested_symbols=normalized_symbols,
                symbols_covered=tuple(symbols_covered),
                symbol_coverage_statuses=tuple(
                    snapshot.coverage_status for snapshot in symbol_snapshots
                ),
                live_trade_count_24h=live_total,
                archive_trade_count_24h=archive_total,
            ),
            symbols=tuple(symbol_snapshots),
        )

    async def query_rolling_trade_counts(
        self,
        *,
        symbols: Sequence[str],
        observed_at: datetime,
        window_hours: int = 24,
    ) -> dict[str, int]:
        snapshots = await self.query_rolling_trade_count_snapshots(
            symbols=symbols,
            observed_at=observed_at,
            window_hours=window_hours,
        )
        return {
            symbol: int(snapshot.persisted_trade_count_24h)
            for symbol, snapshot in snapshots.items()
        }

    async def query_rolling_trade_count_snapshots(
        self,
        *,
        symbols: Sequence[str],
        observed_at: datetime,
        window_hours: int = 24,
    ) -> dict[str, BybitSpotV2RollingTradeCountSnapshot]:
        await self._ensure_query_indexes()
        normalized_symbols = tuple(str(symbol) for symbol in symbols)
        normalized_observed_at = observed_at.astimezone(UTC)
        window_started_at = normalized_observed_at - timedelta(hours=window_hours)
        if not normalized_symbols:
            return {}
        archive_stats = await self._load_archive_stats(
            symbols=normalized_symbols,
            window_started_at=window_started_at,
            observed_at=normalized_observed_at,
        )
        live_stats = await self._load_live_window_stats_after_archive_boundary(
            symbols=normalized_symbols,
            window_started_at=window_started_at,
            observed_at=normalized_observed_at,
        )
        snapshots_by_symbol = {
            symbol: BybitSpotV2RollingTradeCountSnapshot(
                normalized_symbol=symbol,
                live_trade_count_24h=int(
                    live_stats.get(symbol, _WindowStats(0, None, None)).trade_count
                ),
                archive_trade_count_24h=int(
                    archive_stats.get(symbol, _WindowStats(0, None, None)).trade_count
                ),
                persisted_trade_count_24h=(
                    int(archive_stats.get(symbol, _WindowStats(0, None, None)).trade_count)
                    + int(live_stats.get(symbol, _WindowStats(0, None, None)).trade_count)
                ),
                coverage_status=_resolve_trade_snapshot_split_status(
                    live_trade_count=int(
                        live_stats.get(symbol, _WindowStats(0, None, None)).trade_count
                    ),
                    archive_trade_count=int(
                        archive_stats.get(symbol, _WindowStats(0, None, None)).trade_count
                    ),
                ),
            )
            for symbol in normalized_symbols
        }
        return {
            symbol: snapshots_by_symbol.get(
                symbol,
                BybitSpotV2RollingTradeCountSnapshot(
                    normalized_symbol=symbol,
                    live_trade_count_24h=0,
                    archive_trade_count_24h=0,
                    persisted_trade_count_24h=0,
                    coverage_status="empty",
                ),
            )
            for symbol in normalized_symbols
        }

    async def query_product_summary_window(
        self,
        *,
        symbols: Sequence[str],
        observed_at: datetime,
        window_hours: int = 24,
    ) -> BybitSpotV2PersistedWindowSnapshot:
        """
        Build a lightweight product-facing 24h snapshot for the primary spot screen.

        Unlike the exact rolling-window query, this path avoids the expensive live/archive
        anti-join and instead counts live rows only after the latest archive boundary per
        symbol. This keeps the primary operator screen fast while preserving the same
        high-level product contract for the current 24h window.
        """
        normalized_symbols = tuple(str(symbol) for symbol in symbols)
        normalized_observed_at = observed_at.astimezone(UTC)
        window_started_at = normalized_observed_at - timedelta(hours=window_hours)
        archive_stats = await self._load_archive_stats(
            symbols=normalized_symbols,
            window_started_at=window_started_at,
            observed_at=normalized_observed_at,
        )
        live_stats = await self._load_live_product_summary_stats(
            symbols=normalized_symbols,
            window_started_at=window_started_at,
            observed_at=normalized_observed_at,
        )
        symbol_snapshots: list[BybitSpotV2PersistedSymbolSnapshot] = []
        live_total = 0
        archive_total = 0
        overall_earliest: datetime | None = None
        overall_latest: datetime | None = None
        symbols_covered: list[str] = []
        for symbol in normalized_symbols:
            live = live_stats.get(symbol, _WindowStats(0, None, None))
            archive = archive_stats.get(symbol, _WindowStats(0, None, None))
            persisted_total = live.trade_count + archive.trade_count
            earliest = _min_datetime(live.earliest_trade_at, archive.earliest_trade_at)
            latest = _max_datetime(live.latest_trade_at, archive.latest_trade_at)
            coverage_status = _resolve_symbol_coverage_status(
                observed_at=normalized_observed_at,
                window_started_at=window_started_at,
                live_trade_count=live.trade_count,
                archive_trade_count=archive.trade_count,
                archive_latest_trade_at=archive.latest_trade_at,
            )
            if persisted_total > 0:
                symbols_covered.append(symbol)
                overall_earliest = _min_datetime(overall_earliest, earliest)
                overall_latest = _max_datetime(overall_latest, latest)
            live_total += live.trade_count
            archive_total += archive.trade_count
            symbol_snapshots.append(
                BybitSpotV2PersistedSymbolSnapshot(
                    normalized_symbol=symbol,
                    live_trade_count_24h=live.trade_count,
                    archive_trade_count_24h=archive.trade_count,
                    persisted_trade_count_24h=persisted_total,
                    earliest_trade_at=earliest,
                    latest_trade_at=latest,
                    coverage_status=coverage_status,
                )
            )
        return BybitSpotV2PersistedWindowSnapshot(
            observed_at=normalized_observed_at,
            window_started_at=window_started_at,
            live_trade_count_24h=live_total,
            archive_trade_count_24h=archive_total,
            persisted_trade_count_24h=archive_total + live_total,
            earliest_trade_at=overall_earliest,
            latest_trade_at=overall_latest,
            symbols_covered=tuple(symbols_covered),
            coverage_status=_resolve_window_coverage_status(
                requested_symbols=normalized_symbols,
                symbols_covered=tuple(symbols_covered),
                symbol_coverage_statuses=tuple(
                    snapshot.coverage_status for snapshot in symbol_snapshots
                ),
                live_trade_count_24h=live_total,
                archive_trade_count_24h=archive_total,
            ),
            symbols=tuple(symbol_snapshots),
        )

    async def _load_live_stats(
        self,
        *,
        symbols: tuple[str, ...],
        window_started_at: datetime,
        observed_at: datetime,
    ) -> dict[str, _WindowStats]:
        return await self._load_live_window_stats_after_archive_boundary(
            symbols=symbols,
            window_started_at=window_started_at,
            observed_at=observed_at,
        )

    async def _load_archive_stats(
        self,
        *,
        symbols: tuple[str, ...],
        window_started_at: datetime,
        observed_at: datetime,
    ) -> dict[str, _WindowStats]:
        return await self._load_window_stats(
            table_name="bybit_spot_v2_archive_trade_ledger",
            symbols=symbols,
            window_started_at=window_started_at,
            observed_at=observed_at,
        )

    async def _load_window_stats(
        self,
        *,
        table_name: str,
        symbols: tuple[str, ...],
        window_started_at: datetime,
        observed_at: datetime,
    ) -> dict[str, _WindowStats]:
        if not symbols:
            return {}
        async with self._db_manager.connection() as conn:
            rows = await conn.fetch(
                f"""
                SELECT
                    normalized_symbol,
                    COUNT(*) AS trade_count,
                    MIN(exchange_trade_at) AS earliest_trade_at,
                    MAX(exchange_trade_at) AS latest_trade_at
                FROM {table_name}
                WHERE normalized_symbol = ANY($1::text[])
                  AND exchange_trade_at >= $2
                  AND exchange_trade_at < $3
                GROUP BY normalized_symbol
                """,
                list(symbols),
                window_started_at,
                observed_at,
            )
        return {
            str(row["normalized_symbol"]): _WindowStats(
                trade_count=int(row["trade_count"] or 0),
                earliest_trade_at=row["earliest_trade_at"],
                latest_trade_at=row["latest_trade_at"],
            )
            for row in rows
        }

    async def _load_window_trade_counts(
        self,
        *,
        table_name: str,
        symbols: tuple[str, ...],
        window_started_at: datetime,
        observed_at: datetime,
    ) -> dict[str, int]:
        if not symbols:
            return {}
        async with self._db_manager.connection() as conn:
            rows = await conn.fetch(
                f"""
                SELECT normalized_symbol, COUNT(*) AS trade_count
                FROM {table_name}
                WHERE normalized_symbol = ANY($1::text[])
                  AND exchange_trade_at >= $2
                  AND exchange_trade_at < $3
                GROUP BY normalized_symbol
                """,
                list(symbols),
                window_started_at,
                observed_at,
            )
        return {
            str(row["normalized_symbol"]): int(row["trade_count"] or 0)
            for row in rows
        }

    async def _load_live_window_stats_excluding_archive_overlap(
        self,
        *,
        symbols: tuple[str, ...],
        window_started_at: datetime,
        observed_at: datetime,
    ) -> dict[str, _WindowStats]:
        if not symbols:
            return {}
        async with self._db_manager.connection() as conn:
            rows = await conn.fetch(
                """
                WITH archive_window AS (
                    SELECT
                        normalized_symbol,
                        canonical_dedup_identity
                    FROM bybit_spot_v2_archive_trade_ledger
                    WHERE normalized_symbol = ANY($1::text[])
                      AND exchange_trade_at >= $2
                      AND exchange_trade_at < $3
                )
                SELECT
                    live.normalized_symbol,
                    COUNT(*) AS trade_count,
                    MIN(live.exchange_trade_at) AS earliest_trade_at,
                    MAX(live.exchange_trade_at) AS latest_trade_at
                FROM bybit_spot_v2_live_trade_ledger live
                LEFT JOIN archive_window archive
                  ON archive.normalized_symbol = live.normalized_symbol
                 AND archive.canonical_dedup_identity = live.canonical_dedup_identity
                WHERE live.normalized_symbol = ANY($1::text[])
                  AND live.exchange_trade_at >= $2
                  AND live.exchange_trade_at < $3
                  AND archive.canonical_dedup_identity IS NULL
                GROUP BY live.normalized_symbol
                """,
                list(symbols),
                window_started_at,
                observed_at,
            )
        return {
            str(row["normalized_symbol"]): _WindowStats(
                trade_count=int(row["trade_count"] or 0),
                earliest_trade_at=row["earliest_trade_at"],
                latest_trade_at=row["latest_trade_at"],
            )
            for row in rows
        }

    async def _load_live_window_trade_counts_excluding_archive_overlap(
        self,
        *,
        symbols: tuple[str, ...],
        window_started_at: datetime,
        observed_at: datetime,
    ) -> dict[str, int]:
        if not symbols:
            return {}
        async with self._db_manager.connection() as conn:
            rows = await conn.fetch(
                """
                WITH archive_window AS (
                    SELECT
                        normalized_symbol,
                        canonical_dedup_identity
                    FROM bybit_spot_v2_archive_trade_ledger
                    WHERE normalized_symbol = ANY($1::text[])
                      AND exchange_trade_at >= $2
                      AND exchange_trade_at < $3
                )
                SELECT
                    live.normalized_symbol,
                    COUNT(*) AS trade_count
                FROM bybit_spot_v2_live_trade_ledger live
                LEFT JOIN archive_window archive
                  ON archive.normalized_symbol = live.normalized_symbol
                 AND archive.canonical_dedup_identity = live.canonical_dedup_identity
                WHERE live.normalized_symbol = ANY($1::text[])
                  AND live.exchange_trade_at >= $2
                  AND live.exchange_trade_at < $3
                  AND archive.canonical_dedup_identity IS NULL
                GROUP BY live.normalized_symbol
                """,
                list(symbols),
                window_started_at,
                observed_at,
            )
        return {
            str(row["normalized_symbol"]): int(row["trade_count"] or 0)
            for row in rows
        }

    async def _load_live_window_stats_after_archive_boundary(
        self,
        *,
        symbols: tuple[str, ...],
        window_started_at: datetime,
        observed_at: datetime,
    ) -> dict[str, _WindowStats]:
        if not symbols:
            return {}
        async with self._db_manager.connection() as conn:
            rows = await conn.fetch(
                """
                WITH requested_symbols AS (
                    SELECT UNNEST($1::text[]) AS normalized_symbol
                ),
                archive_boundaries AS (
                    SELECT
                        requested.normalized_symbol,
                        COALESCE(
                            MAX(archive.exchange_trade_at),
                            $2::timestamptz - INTERVAL '1 microsecond'
                        ) AS live_started_at
                    FROM requested_symbols requested
                    LEFT JOIN bybit_spot_v2_archive_trade_ledger archive
                      ON archive.normalized_symbol = requested.normalized_symbol
                     AND archive.exchange_trade_at >= $2
                     AND archive.exchange_trade_at < $3
                    GROUP BY requested.normalized_symbol
                )
                SELECT
                    live.normalized_symbol,
                    COUNT(*) AS trade_count,
                    MIN(live.exchange_trade_at) AS earliest_trade_at,
                    MAX(live.exchange_trade_at) AS latest_trade_at
                FROM bybit_spot_v2_live_trade_ledger live
                JOIN archive_boundaries boundary
                  ON boundary.normalized_symbol = live.normalized_symbol
                WHERE live.exchange_trade_at > boundary.live_started_at
                  AND live.exchange_trade_at < $3
                GROUP BY live.normalized_symbol
                """,
                list(symbols),
                window_started_at,
                observed_at,
            )
        return {
            str(row["normalized_symbol"]): _WindowStats(
                trade_count=int(row["trade_count"] or 0),
                earliest_trade_at=row["earliest_trade_at"],
                latest_trade_at=row["latest_trade_at"],
            )
            for row in rows
        }

    async def _load_live_window_trade_counts_after_archive_boundary(
        self,
        *,
        symbols: tuple[str, ...],
        window_started_at: datetime,
        observed_at: datetime,
    ) -> dict[str, int]:
        if not symbols:
            return {}
        async with self._db_manager.connection() as conn:
            rows = await conn.fetch(
                """
                WITH requested_symbols AS (
                    SELECT UNNEST($1::text[]) AS normalized_symbol
                ),
                archive_boundaries AS (
                    SELECT
                        requested.normalized_symbol,
                        COALESCE(
                            MAX(archive.exchange_trade_at),
                            $2::timestamptz - INTERVAL '1 microsecond'
                        ) AS live_started_at
                    FROM requested_symbols requested
                    LEFT JOIN bybit_spot_v2_archive_trade_ledger archive
                      ON archive.normalized_symbol = requested.normalized_symbol
                     AND archive.exchange_trade_at >= $2
                     AND archive.exchange_trade_at < $3
                    GROUP BY requested.normalized_symbol
                )
                SELECT
                    live.normalized_symbol,
                    COUNT(*) AS trade_count
                FROM bybit_spot_v2_live_trade_ledger live
                JOIN archive_boundaries boundary
                  ON boundary.normalized_symbol = live.normalized_symbol
                WHERE live.exchange_trade_at > boundary.live_started_at
                  AND live.exchange_trade_at < $3
                GROUP BY live.normalized_symbol
                """,
                list(symbols),
                window_started_at,
                observed_at,
            )
        return {
            str(row["normalized_symbol"]): int(row["trade_count"] or 0)
            for row in rows
        }

    async def _load_live_product_summary_stats(
        self,
        *,
        symbols: tuple[str, ...],
        window_started_at: datetime,
        observed_at: datetime,
    ) -> dict[str, _WindowStats]:
        return await self._load_live_window_stats_after_archive_boundary(
            symbols=symbols,
            window_started_at=window_started_at,
            observed_at=observed_at,
        )


def _min_datetime(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return left if left <= right else right


def _max_datetime(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return left if left >= right else right


def _resolve_symbol_coverage_status(
    *,
    observed_at: datetime,
    window_started_at: datetime,
    live_trade_count: int,
    archive_trade_count: int,
    archive_latest_trade_at: datetime | None,
) -> str:
    archive_needed_until_at = observed_at.astimezone(UTC).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    archive_slice_required = window_started_at.astimezone(UTC) < archive_needed_until_at
    archive_slice_ready = (
        archive_latest_trade_at is not None
        and archive_latest_trade_at >= archive_needed_until_at - _ARCHIVE_WINDOW_ALLOWED_GAP
    )
    if archive_slice_required and not archive_slice_ready:
        if live_trade_count > 0 or archive_trade_count > 0:
            return "pending_archive"
        return "empty"
    if live_trade_count > 0 and archive_trade_count > 0:
        return "hybrid"
    if live_trade_count > 0:
        return "live_only"
    if archive_trade_count > 0:
        return "archive_only"
    return "empty"


def _resolve_trade_snapshot_split_status(
    *,
    live_trade_count: int,
    archive_trade_count: int,
) -> str:
    if live_trade_count > 0 and archive_trade_count > 0:
        return "hybrid"
    if live_trade_count > 0:
        return "live_only"
    if archive_trade_count > 0:
        return "archive_only"
    return "empty"


def _resolve_window_coverage_status(
    *,
    requested_symbols: tuple[str, ...],
    symbols_covered: tuple[str, ...],
    symbol_coverage_statuses: tuple[str, ...],
    live_trade_count_24h: int,
    archive_trade_count_24h: int,
) -> str:
    if not symbols_covered:
        return "empty"
    if any(status == "pending_archive" for status in symbol_coverage_statuses):
        return "pending_archive"
    if len(symbols_covered) < len(requested_symbols):
        return "partial"
    if live_trade_count_24h > 0 and archive_trade_count_24h > 0:
        return "hybrid"
    if live_trade_count_24h > 0:
        return "live_only"
    return "archive_only"


def _align_window_started_at_to_derived_count_contract(
    window_started_at: datetime,
) -> datetime:
    normalized_window_started_at = window_started_at.astimezone(UTC)
    if (
        normalized_window_started_at.second == 0
        and normalized_window_started_at.microsecond == 0
    ):
        return normalized_window_started_at
    return (
        normalized_window_started_at.replace(second=0, microsecond=0)
        + timedelta(minutes=1)
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query rolling 24h persisted state from spot v2 live+archive ledgers.",
    )
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--window-hours", type=int, default=24)
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    db_manager = DatabaseManager()
    try:
        service = BybitSpotV2PersistedQueryService(db_manager)
        snapshot = await service.query_rolling_window(
            symbols=tuple(args.symbols),
            observed_at=datetime.fromisoformat(args.observed_at),
            window_hours=args.window_hours,
        )
        import json

        print(json.dumps(snapshot.as_dict()))
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(_main())


__all__ = [
    "BybitSpotV2PersistedQueryService",
    "BybitSpotV2PersistedSymbolSnapshot",
    "BybitSpotV2PersistedWindowSnapshot",
]
