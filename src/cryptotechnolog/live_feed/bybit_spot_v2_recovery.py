"""Separate non-blocking recovery orchestration for Bybit spot v2."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
import inspect
import json
import time
from typing import TYPE_CHECKING, Any

from cryptotechnolog.config import get_logger
from cryptotechnolog.core.database import DatabaseManager
from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.market_data import create_market_data_runtime

from .bybit_spot_v2_archive_ledger import BybitSpotV2ArchiveTradeLedgerRepository
from .bybit_spot_v2_archive_loader import (
    BybitSpotV2ArchiveLoadReport,
    BybitSpotV2ArchiveLoadRequest,
    run_bybit_spot_v2_archive_loader,
)
from .bybit_spot_v2_live_trade_ledger import (
    BybitSpotV2LiveTradeLedgerRecord,
    BybitSpotV2LiveTradeLedgerRepository,
)
from .bybit_spot_v2_persisted_query import BybitSpotV2PersistedQueryService
from .bybit_spot_v2_transport import (
    BybitSpotV2TransportConfig,
    create_bybit_spot_v2_transport,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

    from .bybit_spot_v2_transport import BybitSpotV2Transport

logger = get_logger(__name__)
_LIVE_TAIL_WRITE_BATCH_SIZE = 5_000
_LIVE_TAIL_FETCH_PAGE_SIZE = 5_000
_RECOVERY_COLD_START_DELAY_SECONDS = 5.0
_LEDGER_RETENTION_HOURS = 48


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(slots=True, frozen=True)
class BybitSpotV2RecoverySnapshot:
    status: str
    stage: str
    target_symbols: tuple[str, ...]
    observed_at: datetime | None
    window_started_at: datetime | None
    window_hours: int
    started_at: datetime | None
    finished_at: datetime | None
    last_error: str | None = None
    reason: str | None = None
    processed_archives: int = 0
    written_archive_records: int = 0
    skipped_archive_records: int = 0
    archive_dates: tuple[str, ...] = ()
    last_progress_checkpoint: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for field_name in (
            "observed_at",
            "window_started_at",
            "started_at",
            "finished_at",
        ):
            value = getattr(self, field_name)
            payload[field_name] = value.isoformat() if value is not None else None
        return payload


@dataclass(slots=True, frozen=True)
class BybitSpotV2RecoveryProbeSnapshot:
    transport: dict[str, object]
    recovery: dict[str, object]
    transport_connected_while_recovery_running: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "transport": self.transport,
            "recovery": self.recovery,
            "transport_connected_while_recovery_running": (
                self.transport_connected_while_recovery_running
            ),
        }


class BybitSpotV2RecoveryCoordinator:
    """Run archive/backfill beside spot v2 transport without blocking transport startup."""

    def __init__(
        self,
        *,
        symbols: Sequence[str],
        persisted_query_service: BybitSpotV2PersistedQueryService,
        archive_loader_runner: Callable[..., Awaitable[BybitSpotV2ArchiveLoadReport]],
        db_manager: DatabaseManager | None = None,
        archive_trade_repository: BybitSpotV2ArchiveTradeLedgerRepository | None = None,
        live_trade_repository: BybitSpotV2LiveTradeLedgerRepository | None = None,
        window_hours: int = 24,
        observed_at_factory: Callable[[], datetime] = _utcnow,
    ) -> None:
        normalized_symbols = tuple(str(symbol) for symbol in symbols if str(symbol))
        if not normalized_symbols:
            raise ValueError("symbols не может быть пустым")
        self.symbols = normalized_symbols
        self.window_hours = int(window_hours)
        self._db_manager = db_manager
        self._persisted_query_service = persisted_query_service
        self._archive_loader_runner = archive_loader_runner
        self._archive_trade_repository = archive_trade_repository
        if self._archive_trade_repository is None and db_manager is not None:
            self._archive_trade_repository = BybitSpotV2ArchiveTradeLedgerRepository(db_manager)
        self._live_trade_repository = live_trade_repository
        if self._live_trade_repository is None and db_manager is not None:
            self._live_trade_repository = BybitSpotV2LiveTradeLedgerRepository(db_manager)
        self._observed_at_factory = observed_at_factory
        self._stop_requested = asyncio.Event()
        self.run_started = asyncio.Event()
        self._snapshot = BybitSpotV2RecoverySnapshot(
            status="idle",
            stage="idle",
            target_symbols=self.symbols,
            observed_at=None,
            window_started_at=None,
            window_hours=self.window_hours,
            started_at=None,
            finished_at=None,
        )

    async def prepare_storage(self) -> None:
        if self._archive_trade_repository is not None:
            await self._archive_trade_repository.cleanup_retention(
                retention_hours=_LEDGER_RETENTION_HOURS
            )
        if self._live_trade_repository is not None:
            await self._live_trade_repository.cleanup_retention(
                retention_hours=_LEDGER_RETENTION_HOURS
            )

    async def run(self) -> None:
        if self._stop_requested.is_set():
            self._snapshot = BybitSpotV2RecoverySnapshot(
                status="skipped",
                stage="stopped",
                target_symbols=self.symbols,
                observed_at=None,
                window_started_at=None,
                window_hours=self.window_hours,
                started_at=None,
                finished_at=_utcnow(),
                reason="stop_requested_before_run",
            )
            self.run_started.set()
            return
        observed_at = self._observed_at_factory().astimezone(UTC)
        window_started_at = observed_at - timedelta(hours=self.window_hours)
        self._snapshot = BybitSpotV2RecoverySnapshot(
            status="planned",
            stage="planning",
            target_symbols=self.symbols,
            observed_at=observed_at,
            window_started_at=window_started_at,
            window_hours=self.window_hours,
            started_at=_utcnow(),
            finished_at=None,
        )
        self.run_started.set()
        try:
            if _RECOVERY_COLD_START_DELAY_SECONDS > 0:
                await asyncio.sleep(_RECOVERY_COLD_START_DELAY_SECONDS)
            if await self._coverage_already_closed_async(
                symbols=self.symbols,
                observed_at=observed_at,
                window_started_at=window_started_at,
            ):
                skipped_stage = (
                    "skipped_archive_present"
                    if self._db_manager is None or self._live_trade_repository is None
                    else "skipped_coverage_present"
                )
                skipped_reason = (
                    "archive_window_already_present"
                    if self._db_manager is None or self._live_trade_repository is None
                    else "persisted_window_already_present"
                )
                self._snapshot = BybitSpotV2RecoverySnapshot(
                    status="skipped",
                    stage=skipped_stage,
                    target_symbols=self.symbols,
                    observed_at=observed_at,
                    window_started_at=window_started_at,
                    window_hours=self.window_hours,
                    started_at=self._snapshot.started_at,
                    finished_at=_utcnow(),
                    reason=skipped_reason,
                )
                return
            report = BybitSpotV2ArchiveLoadReport(
                status="skipped",
                observed_at=observed_at,
                symbols=self.symbols,
                archive_dates=(),
                processed_archives=0,
                total_archives=0,
                written_archive_records=0,
                skipped_archive_records=0,
                restored_window_started_at=None,
                covered_until_at=None,
                reason="archive_load_not_required",
            )
            archive_covered = await self._coverage_already_closed_async(
                symbols=self.symbols,
                observed_at=observed_at,
                window_started_at=window_started_at,
            )
            if not archive_covered:
                self._snapshot = BybitSpotV2RecoverySnapshot(
                    status="running",
                    stage="archive_load_started",
                    target_symbols=self.symbols,
                    observed_at=observed_at,
                    window_started_at=window_started_at,
                    window_hours=self.window_hours,
                    started_at=self._snapshot.started_at,
                    finished_at=None,
                )
                report = await self._archive_loader_runner(
                    request=BybitSpotV2ArchiveLoadRequest(
                        symbols=self.symbols,
                        observed_at=observed_at,
                        covered_until_at=observed_at,
                    ),
                    progress_sink=self._on_progress,
                )
            self._snapshot = BybitSpotV2RecoverySnapshot(
                status="running",
                stage="live_tail_recovery_started",
                target_symbols=self.symbols,
                observed_at=observed_at,
                window_started_at=window_started_at,
                window_hours=self.window_hours,
                started_at=self._snapshot.started_at,
                finished_at=None,
                processed_archives=report.processed_archives,
                written_archive_records=report.written_archive_records,
                skipped_archive_records=report.skipped_archive_records,
                archive_dates=report.archive_dates,
                last_progress_checkpoint=self._snapshot.last_progress_checkpoint,
            )
            recovered_live_tail_rows = await self._recover_persisted_live_tail(
                observed_at=observed_at,
                window_started_at=window_started_at,
            )
        except Exception as exc:
            self._snapshot = BybitSpotV2RecoverySnapshot(
                status="failed",
                stage="failed",
                target_symbols=self.symbols,
                observed_at=observed_at,
                window_started_at=window_started_at,
                window_hours=self.window_hours,
                started_at=self._snapshot.started_at,
                finished_at=_utcnow(),
                last_error=f"{type(exc).__name__}: {exc}",
                reason="recovery_exception",
                last_progress_checkpoint=self._snapshot.last_progress_checkpoint,
            )
            logger.exception(
                "Bybit spot v2 recovery failed",
                symbols=self.symbols,
            )
            return
        final_status = "completed"
        if report.status == "skipped" and report.written_archive_records == 0:
            final_status = "skipped"
        if report.status == "timed_out":
            final_status = "failed"
        if (
            final_status == "skipped"
            and recovered_live_tail_rows > 0
        ):
            final_status = "completed"
        coverage_incomplete = (
            self._db_manager is not None
            and self._archive_trade_repository is not None
            and self._live_trade_repository is not None
            and not await self._coverage_already_closed_async(
                symbols=self.symbols,
                observed_at=observed_at,
                window_started_at=window_started_at,
            )
        )
        if coverage_incomplete and final_status != "failed":
            final_status = "retry_scheduled"
        self._snapshot = BybitSpotV2RecoverySnapshot(
            status=final_status,
            stage=(
                "completed"
                if final_status == "completed"
                else (
                    "coverage_incomplete"
                    if final_status in {"failed", "retry_scheduled"}
                    else report.status
                )
            ),
            target_symbols=self.symbols,
            observed_at=observed_at,
            window_started_at=window_started_at,
            window_hours=self.window_hours,
            started_at=self._snapshot.started_at,
            finished_at=_utcnow(),
            last_error=(
                None
                if final_status not in {"failed", "retry_scheduled"}
                else (report.reason or "persisted_live_tail_incomplete")
            ),
            reason=(
                report.reason
                if final_status not in {"failed", "retry_scheduled"}
                else "persisted_live_tail_incomplete"
            ),
            processed_archives=report.processed_archives,
            written_archive_records=report.written_archive_records,
            skipped_archive_records=report.skipped_archive_records,
            archive_dates=report.archive_dates,
            last_progress_checkpoint=self._snapshot.last_progress_checkpoint,
        )

    async def stop(self) -> None:
        self._stop_requested.set()

    def get_recovery_diagnostics(self) -> dict[str, object]:
        payload = self._snapshot.as_dict()
        payload["generation"] = "v2"
        payload["component"] = "bybit_spot_v2_recovery"
        payload["ready"] = self._snapshot.status in {"completed", "skipped"}
        return payload

    async def get_recovery_diagnostics_async(self) -> dict[str, object]:
        await self._refresh_snapshot_if_coverage_closed()
        return self.get_recovery_diagnostics()

    async def _refresh_snapshot_if_coverage_closed(self) -> None:
        if self._snapshot.status not in {"failed", "retry_scheduled"}:
            return
        if self._snapshot.reason != "persisted_live_tail_incomplete":
            return
        observed_at = self._observed_at_factory().astimezone(UTC)
        window_started_at = observed_at - timedelta(hours=self.window_hours)
        if not await self._coverage_already_closed_async(
            symbols=self.symbols,
            observed_at=observed_at,
            window_started_at=window_started_at,
        ):
            return
        self._snapshot = BybitSpotV2RecoverySnapshot(
            status="skipped",
            stage="skipped_coverage_present",
            target_symbols=self.symbols,
            observed_at=observed_at,
            window_started_at=window_started_at,
            window_hours=self.window_hours,
            started_at=self._snapshot.started_at,
            finished_at=_utcnow(),
            last_error=None,
            reason="persisted_window_already_present",
            processed_archives=self._snapshot.processed_archives,
            written_archive_records=self._snapshot.written_archive_records,
            skipped_archive_records=self._snapshot.skipped_archive_records,
            archive_dates=self._snapshot.archive_dates,
            last_progress_checkpoint=self._snapshot.last_progress_checkpoint,
        )

    def _archive_window_already_covered(self, symbol_snapshots: Sequence[object]) -> bool:
        if not symbol_snapshots:
            return False
        return all(
            getattr(snapshot, "archive_trade_count_24h", 0) > 0
            for snapshot in symbol_snapshots
        )

    async def _coverage_already_closed_async(
        self,
        *,
        symbols: Sequence[str],
        observed_at: datetime,
        window_started_at: datetime,
    ) -> bool:
        if not symbols:
            return False
        if (
            self._db_manager is None
            or self._archive_trade_repository is None
            or self._live_trade_repository is None
        ):
            persisted_window = await self._persisted_query_service.query_rolling_window(
                symbols=tuple(symbols),
                observed_at=observed_at,
                window_hours=self.window_hours,
            )
            return self._archive_window_already_covered(persisted_window.symbols)
        latest_allowed_gap = timedelta(minutes=10)
        normalized_observed_at = observed_at.astimezone(UTC)
        normalized_window_started_at = window_started_at.astimezone(UTC)
        for symbol in symbols:
            archive_latest = await self._archive_trade_repository.fetch_latest_trade_before(
                normalized_symbol=symbol,
                observed_at=normalized_observed_at,
            )
            live_latest = await self._live_trade_repository.fetch_latest_trade_before(
                normalized_symbol=symbol,
                observed_at=normalized_observed_at,
            )
            if archive_latest is None:
                return False
            archive_boundary = max(normalized_window_started_at, archive_latest.exchange_trade_at)
            live_earliest = await self._live_trade_repository.fetch_earliest_trade_after(
                normalized_symbol=symbol,
                trade_at=archive_boundary,
                observed_at=normalized_observed_at,
            )
            if live_earliest is None or live_latest is None:
                return False
            start_gap = live_earliest.exchange_trade_at - archive_boundary
            end_gap = normalized_observed_at - live_latest.exchange_trade_at
            if start_gap > latest_allowed_gap or end_gap > latest_allowed_gap:
                return False
        return True

    async def _recover_persisted_live_tail(
        self,
        *,
        observed_at: datetime,
        window_started_at: datetime,
    ) -> int:
        normalized_observed_at = observed_at.astimezone(UTC)
        if self._db_manager is None or self._live_trade_repository is None:
            return 0
        archive_boundary = normalized_observed_at.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        recovery_started_at = max(window_started_at.astimezone(UTC), archive_boundary)
        total_written = 0
        for symbol in self.symbols:
            fetched_rows = 0
            batch_records: list[Any] = []
            rows_or_pages = self._load_legacy_live_tail_rows(
                symbol=symbol,
                resume_after_trade_at=recovery_started_at,
                observed_at=normalized_observed_at,
            )
            if hasattr(rows_or_pages, "__aiter__"):
                page_iterator = rows_or_pages
            else:
                legacy_rows = await rows_or_pages if inspect.isawaitable(rows_or_pages) else rows_or_pages

                async def _single_page_iterator(
                    rows: tuple[dict[str, object], ...] = tuple(legacy_rows),
                ) -> AsyncIterator[list[dict[str, object]]]:
                    if rows:
                        yield list(rows)

                page_iterator = _single_page_iterator()
            async for page in page_iterator:
                page_fetch_started = time.perf_counter()
                fetched_rows += len(page)
                page_fetch_ms = (time.perf_counter() - page_fetch_started) * 1000.0
                page_map_started = time.perf_counter()
                for row in page:
                    record = _build_spot_v2_live_trade_record_from_legacy_row(row)
                    if record is None:
                        continue
                    batch_records.append(record)
                    if len(batch_records) >= _LIVE_TAIL_WRITE_BATCH_SIZE:
                        page_write_started = time.perf_counter()
                        await self._live_trade_repository.upsert_live_trades(batch_records)
                        page_write_ms = (time.perf_counter() - page_write_started) * 1000.0
                        total_written += len(batch_records)
                        latest_flushed_trade_at = batch_records[-1].exchange_trade_at.isoformat()
                        self._on_progress(
                            "[spot-v2-live-tail-recovery] "
                            f"checkpoint=live_tail_page_flushed symbol={symbol} "
                            f"rows_per_page={len(page)} flushed_rows={len(batch_records)} "
                            f"fetch_page_ms={page_fetch_ms:.3f} "
                            f"map_page_ms={(time.perf_counter() - page_map_started) * 1000.0:.3f} "
                            f"write_page_ms={page_write_ms:.3f} "
                            f"latest_persisted_trade_at_after_flush={latest_flushed_trade_at}"
                        )
                        batch_records = []
            if batch_records:
                page_write_started = time.perf_counter()
                await self._live_trade_repository.upsert_live_trades(batch_records)
                page_write_ms = (time.perf_counter() - page_write_started) * 1000.0
                total_written += len(batch_records)
                latest_flushed_trade_at = batch_records[-1].exchange_trade_at.isoformat()
                self._on_progress(
                    "[spot-v2-live-tail-recovery] "
                    f"checkpoint=live_tail_page_flushed symbol={symbol} "
                    f"rows_per_page={len(batch_records)} flushed_rows={len(batch_records)} "
                    f"fetch_page_ms=0.000 map_page_ms=0.000 write_page_ms={page_write_ms:.3f} "
                    f"latest_persisted_trade_at_after_flush={latest_flushed_trade_at}"
                )
            self._on_progress(
                "[spot-v2-live-tail-recovery] "
                f"checkpoint=live_tail_rows_loaded symbol={symbol} rows={fetched_rows} "
                f"resume_after_trade_at={recovery_started_at.isoformat()}"
            )
        return total_written

    async def _load_legacy_live_tail_rows(
        self,
        *,
        symbol: str,
        resume_after_trade_at: datetime,
        observed_at: datetime,
    ) -> AsyncIterator[list[dict[str, object]]]:
        cursor_trade_at = resume_after_trade_at
        cursor_updated_at = datetime.min.replace(tzinfo=UTC)
        cursor_identity = ""
        async with self._db_manager.connection() as conn:
            while True:
                fetch_started = time.perf_counter()
                rows = await conn.fetch(
                    """
                    SELECT
                        normalized_symbol,
                        source_trade_identity,
                        canonical_dedup_identity,
                        identity_contract_version,
                        exchange_trade_at,
                        side,
                        normalized_price,
                        normalized_size,
                        source_metadata,
                        created_at,
                        updated_at
                    FROM bybit_trade_ledger
                    WHERE contour = 'spot'
                      AND source = 'live_public_trade'
                      AND normalized_symbol = $1
                      AND exchange_trade_at < $2
                      AND (
                          exchange_trade_at > $3
                          OR (
                              exchange_trade_at = $3
                              AND (
                                  updated_at > $4
                                  OR (
                                      updated_at = $4
                                      AND canonical_dedup_identity > $5
                                  )
                              )
                          )
                      )
                    ORDER BY exchange_trade_at ASC, updated_at ASC, canonical_dedup_identity ASC
                    LIMIT $6
                    """,
                    symbol,
                    observed_at,
                    cursor_trade_at,
                    cursor_updated_at,
                    cursor_identity,
                    _LIVE_TAIL_FETCH_PAGE_SIZE,
                )
                fetch_page_ms = (time.perf_counter() - fetch_started) * 1000.0
                if not rows:
                    return
                map_started = time.perf_counter()
                payload_rows: list[dict[str, object]] = []
                for row in rows:
                    payload = dict(row)
                    payload["source_metadata"] = _normalize_live_tail_source_metadata(
                        payload.get("source_metadata")
                    )
                    payload_rows.append(payload)
                map_page_ms = (time.perf_counter() - map_started) * 1000.0
                last_row = rows[-1]
                cursor_trade_at = last_row["exchange_trade_at"]
                cursor_updated_at = last_row["updated_at"]
                cursor_identity = str(last_row["canonical_dedup_identity"])
                self._on_progress(
                    "[spot-v2-live-tail-recovery] "
                    f"checkpoint=live_tail_page_fetched symbol={symbol} rows_per_page={len(payload_rows)} "
                    f"fetch_page_ms={fetch_page_ms:.3f} map_page_ms={map_page_ms:.3f} "
                    f"latest_page_trade_at={cursor_trade_at.isoformat()}"
                )
                yield payload_rows

    def _on_progress(self, message: str) -> None:
        checkpoint = _extract_checkpoint(message)
        if checkpoint is None:
            return
        self._snapshot = BybitSpotV2RecoverySnapshot(
            status=self._snapshot.status,
            stage=checkpoint,
            target_symbols=self._snapshot.target_symbols,
            observed_at=self._snapshot.observed_at,
            window_started_at=self._snapshot.window_started_at,
            window_hours=self._snapshot.window_hours,
            started_at=self._snapshot.started_at,
            finished_at=self._snapshot.finished_at,
            last_error=self._snapshot.last_error,
            reason=self._snapshot.reason,
            processed_archives=self._snapshot.processed_archives,
            written_archive_records=self._snapshot.written_archive_records,
            skipped_archive_records=self._snapshot.skipped_archive_records,
            archive_dates=self._snapshot.archive_dates,
            last_progress_checkpoint=checkpoint,
        )


def _extract_checkpoint(message: str) -> str | None:
    marker = "checkpoint="
    if marker not in message:
        return None
    start = message.index(marker) + len(marker)
    tail = message[start:]
    return tail.split(" ", 1)[0].strip() or None


async def run_bybit_spot_v2_recovery_probe(
    *,
    db_manager: DatabaseManager,
    symbols: Sequence[str],
    window_hours: int = 24,
    timeout_seconds: int = 20,
) -> BybitSpotV2RecoveryProbeSnapshot:
    event_bus = EnhancedEventBus(enable_persistence=False)
    market_data_runtime = create_market_data_runtime(event_bus=event_bus)
    await market_data_runtime.start()
    transport: BybitSpotV2Transport | None = None
    transport_task: asyncio.Task[None] | None = None
    recovery_task: asyncio.Task[None] | None = None
    try:
        transport = create_bybit_spot_v2_transport(
            symbols=tuple(symbols),
            config=BybitSpotV2TransportConfig(),
            market_data_runtime=market_data_runtime,
            live_trade_ledger_repository=BybitSpotV2LiveTradeLedgerRepository(db_manager),
        )
        recovery = BybitSpotV2RecoveryCoordinator(
            symbols=tuple(symbols),
            window_hours=window_hours,
            db_manager=db_manager,
            persisted_query_service=BybitSpotV2PersistedQueryService(db_manager),
            archive_loader_runner=lambda **kwargs: run_bybit_spot_v2_archive_loader(
                db_manager=db_manager,
                **kwargs,
            ),
        )
        transport_task = asyncio.create_task(transport.run(), name="spot_v2_probe_transport")
        await asyncio.wait_for(transport.run_started.wait(), timeout=timeout_seconds)
        await asyncio.wait_for(
            _wait_for_transport_activity(transport=transport),
            timeout=timeout_seconds,
        )
        recovery_task = asyncio.create_task(recovery.run(), name="spot_v2_probe_recovery")
        await asyncio.wait_for(recovery.run_started.wait(), timeout=timeout_seconds)
        await asyncio.wait_for(
            _wait_for_recovery_terminal_state(recovery=recovery),
            timeout=timeout_seconds,
        )
        recovery_diagnostics = recovery.get_recovery_diagnostics()
        transport_diagnostics = transport.get_transport_diagnostics()
        return BybitSpotV2RecoveryProbeSnapshot(
            transport=transport_diagnostics,
            recovery=recovery_diagnostics,
            transport_connected_while_recovery_running=bool(
                transport_diagnostics.get("subscription_alive") is True
                and transport_diagnostics.get("messages_received_count", 0) >= 1
            ),
        )
    finally:
        if recovery_task is not None:
            recovery_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await recovery_task
        if transport is not None:
            with contextlib.suppress(Exception):
                await transport.stop()
        if transport_task is not None:
            transport_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await transport_task
        await market_data_runtime.stop()


async def _wait_for_transport_activity(*, transport) -> None:
    while True:
        diagnostics = transport.get_transport_diagnostics()
        if diagnostics["subscription_alive"] is True and diagnostics["messages_received_count"] >= 1:
            return
        await asyncio.sleep(0.1)


async def _wait_for_recovery_terminal_state(*, recovery: BybitSpotV2RecoveryCoordinator) -> None:
    while True:
        diagnostics = recovery.get_recovery_diagnostics()
        if diagnostics["status"] in {"completed", "skipped", "failed"}:
            return
        await asyncio.sleep(0.1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Controlled Bybit spot v2 recovery probe.",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="Normalized symbols, e.g. BTC/USDT ETH/USDT",
    )
    parser.add_argument(
        "--window-hours",
        type=int,
        default=24,
        help="Rolling window size for recovery planning",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=20,
        help="Hard timeout for probe run",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    db_manager = DatabaseManager()
    try:
        try:
            snapshot = await asyncio.wait_for(
                run_bybit_spot_v2_recovery_probe(
                    db_manager=db_manager,
                    symbols=tuple(args.symbols),
                    window_hours=args.window_hours,
                    timeout_seconds=args.timeout_seconds,
                ),
                timeout=args.timeout_seconds + 2,
            )
        except TimeoutError:
            print(
                "{"
                f"\"status\":\"timed_out\",\"reason\":\"probe_timeout_{args.timeout_seconds}s\""
                "}"
            )
            return
        print(snapshot.as_dict())
    finally:
        await db_manager.close()


def _normalize_live_tail_source_metadata(value: object) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items()}
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, dict):
            return {str(key): str(item) for key, item in decoded.items()}
    return {}


def _build_spot_v2_live_trade_record_from_legacy_row(
    row: dict[str, object],
) -> BybitSpotV2LiveTradeLedgerRecord | None:
    source_metadata = _normalize_live_tail_source_metadata(row.get("source_metadata"))
    live_trade_id = source_metadata.get("live_trade_id") or source_metadata.get("trade_id")
    if not live_trade_id:
        source_identity = str(row.get("source_trade_identity") or "")
        if ":" in source_identity:
            live_trade_id = source_identity.rsplit(":", 1)[-1]
    if not live_trade_id:
        return None
    is_buyer_maker = source_metadata.get("is_buyer_maker", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    return BybitSpotV2LiveTradeLedgerRecord(
        exchange="bybit_spot_v2",
        normalized_symbol=str(row["normalized_symbol"]),
        live_trade_id=str(live_trade_id),
        source_trade_identity=str(row["source_trade_identity"]),
        canonical_dedup_identity=str(row["canonical_dedup_identity"]),
        identity_contract_version=int(row["identity_contract_version"]),
        exchange_trade_at=row["exchange_trade_at"],
        side=str(row["side"]),
        normalized_price=row["normalized_price"],
        normalized_size=row["normalized_size"],
        is_buyer_maker=is_buyer_maker,
        source_metadata=source_metadata,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


if __name__ == "__main__":
    asyncio.run(_main())
