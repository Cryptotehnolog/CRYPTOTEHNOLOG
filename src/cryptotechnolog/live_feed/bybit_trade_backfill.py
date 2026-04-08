"""Historical Bybit trade backfill support for derived 24h trade-count recovery."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import contextlib
import csv
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
import gzip
import io
from io import BytesIO
from threading import Lock
from time import perf_counter
from typing import TYPE_CHECKING, Literal
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from cryptotechnolog.config.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

BybitTradeBackfillContour = Literal["linear", "spot"]

_BACKFILL_WINDOW = timedelta(hours=24)
_DEFAULT_PUBLIC_ARCHIVE_BASE_URL = "https://public.bybit.com"
_DEFAULT_REQUEST_TIMEOUT_SECONDS = 20
_DEFAULT_MAX_PARALLEL_SYMBOL_FETCHES = 4
_DEFAULT_ARCHIVE_CACHE_TTL = timedelta(days=3)
_TRADE_COUNT_BUCKET_WIDTH = timedelta(minutes=1)
_HTTP_NOT_FOUND = 404
_TIMESTAMP_FIELD_CANDIDATES = (
    "timestamp",
    "time",
    "trade_time_ms",
    "exec_time",
    "execTime",
    "ts",
    "T",
)


class _LatestClosedArchiveUnavailable(OSError):
    """Expected late-publication gap for the newest closed daily archive."""

    def __init__(
        self,
        message: str,
        *,
        bucket_counts: dict[datetime, int],
        latest_trade_at: datetime | None,
        trade_count: int,
        processed_archives: int,
        covered_until_at: datetime | None,
    ) -> None:
        super().__init__(message)
        self.bucket_counts = bucket_counts
        self.latest_trade_at = latest_trade_at
        self.trade_count = trade_count
        self.processed_archives = processed_archives
        self.covered_until_at = covered_until_at


@dataclass(slots=True, frozen=True)
class _LoadedSymbolWindow:
    bucket_counts: dict[datetime, int]
    latest_trade_at: datetime | None
    trade_count: int


@dataclass(slots=True)
class _MutableLoadedSymbolWindow:
    bucket_counts: dict[datetime, int] = field(default_factory=dict)
    latest_trade_at: datetime | None = None
    trade_count: int = 0


@dataclass(slots=True)
class _BackfillProgressTracker:
    total_archives: int
    callback: Callable[[int, int], None] | None
    _processed_archives: int = field(default=0, init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def start(self) -> None:
        if self.callback is not None:
            self.callback(0, self.total_archives)

    def advance(self) -> None:
        if self.callback is None:
            return
        with self._lock:
            self._processed_archives += 1
            processed_archives = self._processed_archives
        self.callback(processed_archives, self.total_archives)


@dataclass(slots=True, frozen=True)
class BybitHistoricalTradeBackfillResult:
    """Result of one historical backfill attempt for derived trade-count recovery."""

    status: str
    restored_window_started_at: datetime | None
    backfilled_trade_count: int
    hydrated_symbols: tuple[str, ...]
    source: str
    covered_until_at: datetime | None = None
    trade_timestamps_by_symbol: dict[str, tuple[datetime, ...]] = field(default_factory=dict)
    trade_buckets_by_symbol: dict[str, dict[datetime, int]] = field(default_factory=dict)
    latest_trade_at_by_symbol: dict[str, datetime | None] = field(default_factory=dict)
    reason: str | None = None
    processed_archives: int = 0
    total_archives: int = 0


@dataclass(slots=True, frozen=True)
class BybitHistoricalTradeBackfillConfig:
    """Config for archived Bybit trade-history backfill."""

    contour: BybitTradeBackfillContour
    archive_base_url: str = _DEFAULT_PUBLIC_ARCHIVE_BASE_URL
    request_timeout_seconds: int = _DEFAULT_REQUEST_TIMEOUT_SECONDS
    cache_dir: Path | None = None
    cache_ttl: timedelta = _DEFAULT_ARCHIVE_CACHE_TTL


@dataclass(slots=True, frozen=True)
class BybitHistoricalRecoveryPlan:
    """Явный plan historical recovery window до фактического archive fetch."""

    symbols: tuple[str, ...]
    window_started_at: datetime
    covered_until_at: datetime
    archive_dates: tuple[date, ...]
    total_archives: int


@dataclass(slots=True, frozen=True)
class BybitHistoricalTradeBackfillCacheDiagnostics:
    cache_enabled: bool
    memory_hits: int
    disk_hits: int
    misses: int
    writes: int
    last_hit_source: str | None
    last_archive_url: str | None
    last_cleanup_at: str | None
    last_pruned_files: int
    last_network_fetch_ms: int | None
    last_disk_read_ms: int | None
    last_gzip_decode_ms: int | None
    last_csv_parse_ms: int | None
    last_archive_total_ms: int | None
    last_symbol_total_ms: int | None
    last_symbol: str | None
    total_network_fetch_ms: int
    total_disk_read_ms: int
    total_gzip_decode_ms: int
    total_csv_parse_ms: int
    total_archive_total_ms: int
    total_symbol_total_ms: int


@dataclass(slots=True, frozen=True)
class BybitHistoricalTradeBackfillService:
    """Fetch and apply archived Bybit trades to restore derived 24h trade-count state."""

    config: BybitHistoricalTradeBackfillConfig
    fetch_bytes: Callable[[str, int], bytes] | None = None
    _payload_cache: dict[str, bytes] = field(default_factory=dict, init=False, repr=False)
    _payload_cache_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _disk_cache_state: dict[str, datetime] = field(default_factory=dict, init=False, repr=False)
    _memory_hits: int = field(default=0, init=False, repr=False)
    _disk_hits: int = field(default=0, init=False, repr=False)
    _cache_misses: int = field(default=0, init=False, repr=False)
    _cache_writes: int = field(default=0, init=False, repr=False)
    _last_cache_hit_source: str | None = field(default=None, init=False, repr=False)
    _last_archive_url: str | None = field(default=None, init=False, repr=False)
    _last_cleanup_at: datetime | None = field(default=None, init=False, repr=False)
    _last_pruned_files: int = field(default=0, init=False, repr=False)
    _last_network_fetch_ms: int | None = field(default=None, init=False, repr=False)
    _last_disk_read_ms: int | None = field(default=None, init=False, repr=False)
    _last_gzip_decode_ms: int | None = field(default=None, init=False, repr=False)
    _last_csv_parse_ms: int | None = field(default=None, init=False, repr=False)
    _last_archive_total_ms: int | None = field(default=None, init=False, repr=False)
    _last_symbol_total_ms: int | None = field(default=None, init=False, repr=False)
    _last_symbol: str | None = field(default=None, init=False, repr=False)
    _total_network_fetch_ms: int = field(default=0, init=False, repr=False)
    _total_disk_read_ms: int = field(default=0, init=False, repr=False)
    _total_gzip_decode_ms: int = field(default=0, init=False, repr=False)
    _total_csv_parse_ms: int = field(default=0, init=False, repr=False)
    _total_archive_total_ms: int = field(default=0, init=False, repr=False)
    _total_symbol_total_ms: int = field(default=0, init=False, repr=False)
    _metrics_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def load_window(
        self,
        *,
        symbols: tuple[str, ...],
        observed_at: datetime,
        covered_until_at: datetime | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> BybitHistoricalTradeBackfillResult:
        plan = self.build_recovery_plan(
            symbols=symbols,
            observed_at=observed_at,
            covered_until_at=covered_until_at,
        )
        return self.load_plan(plan=plan, progress_callback=progress_callback)

    def get_cache_diagnostics(self) -> BybitHistoricalTradeBackfillCacheDiagnostics:
        return BybitHistoricalTradeBackfillCacheDiagnostics(
            cache_enabled=self.config.cache_dir is not None,
            memory_hits=self._memory_hits,
            disk_hits=self._disk_hits,
            misses=self._cache_misses,
            writes=self._cache_writes,
            last_hit_source=self._last_cache_hit_source,
            last_archive_url=self._last_archive_url,
            last_cleanup_at=(
                self._last_cleanup_at.astimezone(UTC).isoformat()
                if self._last_cleanup_at is not None
                else None
            ),
            last_pruned_files=self._last_pruned_files,
            last_network_fetch_ms=self._last_network_fetch_ms,
            last_disk_read_ms=self._last_disk_read_ms,
            last_gzip_decode_ms=self._last_gzip_decode_ms,
            last_csv_parse_ms=self._last_csv_parse_ms,
            last_archive_total_ms=self._last_archive_total_ms,
            last_symbol_total_ms=self._last_symbol_total_ms,
            last_symbol=self._last_symbol,
            total_network_fetch_ms=self._total_network_fetch_ms,
            total_disk_read_ms=self._total_disk_read_ms,
            total_gzip_decode_ms=self._total_gzip_decode_ms,
            total_csv_parse_ms=self._total_csv_parse_ms,
            total_archive_total_ms=self._total_archive_total_ms,
            total_symbol_total_ms=self._total_symbol_total_ms,
        )

    def build_recovery_plan(
        self,
        *,
        symbols: tuple[str, ...],
        observed_at: datetime,
        covered_until_at: datetime | None = None,
    ) -> BybitHistoricalRecoveryPlan:
        if not symbols:
            return BybitHistoricalRecoveryPlan(
                symbols=(),
                window_started_at=observed_at.astimezone(UTC) - _BACKFILL_WINDOW,
                covered_until_at=observed_at.astimezone(UTC),
                archive_dates=(),
                total_archives=0,
            )
        normalized_observed_at = observed_at.astimezone(UTC)
        window_started_at = normalized_observed_at - _BACKFILL_WINDOW
        requested_covered_until_at = (
            covered_until_at.astimezone(UTC)
            if covered_until_at is not None
            else normalized_observed_at
        )
        normalized_covered_until_at = _resolve_closed_archive_boundary(
            window_started_at=window_started_at,
            covered_until_at=requested_covered_until_at,
        )
        archive_dates = _build_archive_dates(
            window_started_at=window_started_at,
            observed_at=normalized_covered_until_at,
        )
        normalized_symbols = tuple(_normalize_symbol(symbol) for symbol in symbols)
        return BybitHistoricalRecoveryPlan(
            symbols=normalized_symbols,
            window_started_at=window_started_at,
            covered_until_at=normalized_covered_until_at,
            archive_dates=archive_dates,
            total_archives=len(normalized_symbols) * len(archive_dates),
        )

    def load_plan(  # noqa: PLR0911, PLR0912, PLR0915
        self,
        *,
        plan: BybitHistoricalRecoveryPlan,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> BybitHistoricalTradeBackfillResult:
        if not plan.symbols:
            return BybitHistoricalTradeBackfillResult(
                status="skipped",
                restored_window_started_at=None,
                backfilled_trade_count=0,
                hydrated_symbols=(),
                source="bybit_public_archive",
                covered_until_at=None,
                reason="empty_scope",
                processed_archives=0,
                total_archives=0,
            )
        self._prune_disk_cache_if_needed(reference_at=plan.covered_until_at)

        window_started_at = plan.window_started_at
        normalized_covered_until_at = plan.covered_until_at
        archive_dates = plan.archive_dates
        total_archives = plan.total_archives
        trade_timestamps_by_symbol: dict[str, tuple[datetime, ...]] = {}
        trade_buckets_by_symbol: dict[str, dict[datetime, int]] = {}
        latest_trade_at_by_symbol: dict[str, datetime | None] = {}
        hydrated_symbols: list[str] = []
        backfilled_trade_count = 0
        processed_archives = 0
        progress_tracker = _BackfillProgressTracker(
            total_archives=total_archives,
            callback=progress_callback,
        )

        progress_tracker.start()

        if not archive_dates:
            return BybitHistoricalTradeBackfillResult(
                status="skipped",
                restored_window_started_at=window_started_at,
                backfilled_trade_count=0,
                hydrated_symbols=(),
                source="bybit_public_archive",
                covered_until_at=normalized_covered_until_at,
                reason="no_closed_archives_required",
                processed_archives=0,
                total_archives=0,
            )

        normalized_symbols = plan.symbols
        if len(normalized_symbols) == 1:
            normalized_symbol = normalized_symbols[0]
            try:
                symbol_results = [
                    (
                        normalized_symbol,
                        self._load_symbol_window(
                            symbol=normalized_symbol,
                            window_started_at=window_started_at,
                            observed_at=normalized_covered_until_at,
                            archive_dates=archive_dates,
                            progress_tracker=progress_tracker,
                        ),
                    )
                ]
            except _LatestClosedArchiveUnavailable as exc:
                if exc.processed_archives > 0 and exc.covered_until_at is not None:
                    return BybitHistoricalTradeBackfillResult(
                        status="skipped",
                        restored_window_started_at=window_started_at,
                        backfilled_trade_count=exc.trade_count,
                        hydrated_symbols=(normalized_symbol,),
                        source="bybit_public_archive",
                        covered_until_at=exc.covered_until_at,
                        trade_buckets_by_symbol={normalized_symbol: dict(exc.bucket_counts)},
                        latest_trade_at_by_symbol={normalized_symbol: exc.latest_trade_at},
                        reason=str(exc),
                        processed_archives=exc.processed_archives,
                        total_archives=total_archives,
                    )
                return BybitHistoricalTradeBackfillResult(
                    status="skipped",
                    restored_window_started_at=None,
                    backfilled_trade_count=0,
                    hydrated_symbols=(),
                    source="bybit_public_archive",
                    covered_until_at=normalized_covered_until_at,
                    reason=str(exc),
                    processed_archives=0,
                    total_archives=total_archives,
                )
            except OSError as exc:
                return BybitHistoricalTradeBackfillResult(
                    status="unavailable",
                    restored_window_started_at=None,
                    backfilled_trade_count=0,
                    hydrated_symbols=(),
                    source="bybit_public_archive",
                    covered_until_at=normalized_covered_until_at,
                    reason=str(exc),
                    processed_archives=0,
                    total_archives=total_archives,
                )
        else:
            completed_symbol_results: dict[str, _LoadedSymbolWindow] = {}
            try:
                with ThreadPoolExecutor(
                    max_workers=min(_DEFAULT_MAX_PARALLEL_SYMBOL_FETCHES, len(normalized_symbols))
                ) as executor:
                    future_to_symbol = {
                        executor.submit(
                            self._load_symbol_window,
                            symbol=normalized_symbol,
                            window_started_at=window_started_at,
                            observed_at=normalized_covered_until_at,
                            archive_dates=archive_dates,
                            progress_tracker=progress_tracker,
                        ): normalized_symbol
                        for normalized_symbol in normalized_symbols
                    }
                    for future in as_completed(future_to_symbol):
                        normalized_symbol = future_to_symbol[future]
                        completed_symbol_results[normalized_symbol] = future.result()
            except _LatestClosedArchiveUnavailable as exc:
                completed_symbols = tuple(
                    symbol for symbol in normalized_symbols if symbol in completed_symbol_results
                )
                partial_processed_archives = (
                    len(completed_symbols) * len(archive_dates) + exc.processed_archives
                )
                partial_trade_timestamps_by_symbol = dict.fromkeys(completed_symbols, ())
                partial_trade_buckets_by_symbol = {
                    symbol: dict(completed_symbol_results[symbol].bucket_counts)
                    for symbol in completed_symbols
                }
                partial_latest_trade_at_by_symbol = {
                    symbol: completed_symbol_results[symbol].latest_trade_at
                    for symbol in completed_symbols
                }
                missing_symbol = next(
                    (
                        symbol
                        for symbol in normalized_symbols
                        if symbol not in completed_symbol_results
                    ),
                    None,
                )
                if missing_symbol is not None:
                    partial_trade_timestamps_by_symbol[missing_symbol] = ()
                    partial_trade_buckets_by_symbol[missing_symbol] = dict(exc.bucket_counts)
                    partial_latest_trade_at_by_symbol[missing_symbol] = exc.latest_trade_at
                partial_hydrated_symbols = (
                    (*completed_symbols, missing_symbol)
                    if missing_symbol is not None
                    else completed_symbols
                )
                partial_backfilled_trade_count = sum(
                    completed_symbol_results[symbol].trade_count for symbol in completed_symbols
                ) + (exc.trade_count if missing_symbol is not None else 0)
                if partial_processed_archives > 0 and exc.covered_until_at is not None:
                    return BybitHistoricalTradeBackfillResult(
                        status="skipped",
                        restored_window_started_at=window_started_at,
                        backfilled_trade_count=partial_backfilled_trade_count,
                        hydrated_symbols=tuple(
                            symbol for symbol in partial_hydrated_symbols if symbol
                        ),
                        source="bybit_public_archive",
                        covered_until_at=exc.covered_until_at,
                        trade_timestamps_by_symbol=partial_trade_timestamps_by_symbol,
                        trade_buckets_by_symbol=partial_trade_buckets_by_symbol,
                        latest_trade_at_by_symbol=partial_latest_trade_at_by_symbol,
                        reason=str(exc),
                        processed_archives=partial_processed_archives,
                        total_archives=total_archives,
                    )
                return BybitHistoricalTradeBackfillResult(
                    status="skipped",
                    restored_window_started_at=None,
                    backfilled_trade_count=0,
                    hydrated_symbols=completed_symbols,
                    source="bybit_public_archive",
                    covered_until_at=normalized_covered_until_at,
                    reason=str(exc),
                    processed_archives=len(completed_symbols) * len(archive_dates),
                    total_archives=total_archives,
                )
            except OSError as exc:
                completed_symbols = tuple(
                    symbol for symbol in normalized_symbols if symbol in completed_symbol_results
                )
                return BybitHistoricalTradeBackfillResult(
                    status="unavailable",
                    restored_window_started_at=None,
                    backfilled_trade_count=0,
                    hydrated_symbols=completed_symbols,
                    source="bybit_public_archive",
                    covered_until_at=normalized_covered_until_at,
                    reason=str(exc),
                    processed_archives=len(completed_symbols) * len(archive_dates),
                    total_archives=total_archives,
                )
            symbol_results = [
                (normalized_symbol, completed_symbol_results[normalized_symbol])
                for normalized_symbol in normalized_symbols
            ]

        for normalized_symbol, loaded_window in symbol_results:
            trade_timestamps_by_symbol[normalized_symbol] = ()
            trade_buckets_by_symbol[normalized_symbol] = dict(loaded_window.bucket_counts)
            latest_trade_at_by_symbol[normalized_symbol] = loaded_window.latest_trade_at
            hydrated_symbols.append(normalized_symbol)
            backfilled_trade_count += loaded_window.trade_count
            processed_archives += len(archive_dates)

        return BybitHistoricalTradeBackfillResult(
            status="backfilled",
            restored_window_started_at=window_started_at,
            backfilled_trade_count=backfilled_trade_count,
            hydrated_symbols=tuple(hydrated_symbols),
            source="bybit_public_archive",
            covered_until_at=normalized_covered_until_at,
            trade_timestamps_by_symbol=trade_timestamps_by_symbol,
            trade_buckets_by_symbol=trade_buckets_by_symbol,
            latest_trade_at_by_symbol=latest_trade_at_by_symbol,
            processed_archives=processed_archives,
            total_archives=total_archives,
        )

    def _load_symbol_window(
        self,
        *,
        symbol: str,
        window_started_at: datetime,
        observed_at: datetime,
        archive_dates: tuple[date, ...],
        progress_tracker: _BackfillProgressTracker,
    ) -> _LoadedSymbolWindow:
        raw_symbol = symbol.replace("/", "").upper()
        aggregation = _MutableLoadedSymbolWindow()
        latest_archive_date = archive_dates[-1] if archive_dates else None
        symbol_started_at = perf_counter()
        for archive_index, current_date in enumerate(archive_dates, start=1):
            archive_started_at = perf_counter()
            try:
                self._append_symbol_archive_rows(
                    raw_symbol=raw_symbol,
                    archive_date=current_date,
                    window_started_at=window_started_at,
                    observed_at=observed_at,
                    aggregation=aggregation,
                )
            except OSError as exc:
                if (
                    latest_archive_date is not None
                    and current_date == latest_archive_date
                    and "historical trade archive not found" in str(exc)
                ):
                    raise _LatestClosedArchiveUnavailable(
                        str(exc),
                        bucket_counts=dict(aggregation.bucket_counts),
                        latest_trade_at=aggregation.latest_trade_at,
                        trade_count=aggregation.trade_count,
                        processed_archives=archive_index - 1,
                        covered_until_at=(
                            _archive_day_closed_at(archive_dates[archive_index - 2])
                            if archive_index > 1
                            else None
                        ),
                    ) from exc
                raise
            self._record_archive_total_ms(round((perf_counter() - archive_started_at) * 1000))
            progress_tracker.advance()
        self._record_symbol_total_ms(
            symbol=symbol,
            duration_ms=round((perf_counter() - symbol_started_at) * 1000),
        )
        return _LoadedSymbolWindow(
            bucket_counts=dict(aggregation.bucket_counts),
            latest_trade_at=aggregation.latest_trade_at,
            trade_count=aggregation.trade_count,
        )

    def _append_symbol_archive_rows(
        self,
        *,
        raw_symbol: str,
        archive_date: date,
        window_started_at: datetime,
        observed_at: datetime,
        aggregation: _MutableLoadedSymbolWindow,
    ) -> None:
        for url in self._candidate_urls(raw_symbol=raw_symbol, archive_date=archive_date):
            try:
                payload, payload_source, payload_elapsed_ms = self._fetch_bytes(
                    url, self.config.request_timeout_seconds
                )
            except HTTPError as exc:
                if exc.code == _HTTP_NOT_FOUND:
                    continue
                raise OSError(f"historical trade backfill request failed: {url}") from exc
            except OSError as exc:
                raise OSError(f"historical trade backfill request failed: {url}") from exc
            if payload_source == "network":
                self._record_network_fetch_ms(payload_elapsed_ms)
            elif payload_source == "disk":
                self._record_disk_read_ms(payload_elapsed_ms)
            self._append_trade_timestamps(
                payload=payload,
                window_started_at=window_started_at,
                observed_at=observed_at,
                aggregation=aggregation,
            )
            return
        raise OSError(
            f"historical trade archive not found for {self.config.contour}:{raw_symbol}:{archive_date}"
        )

    def _candidate_urls(self, *, raw_symbol: str, archive_date: date) -> tuple[str, ...]:
        base_url = self.config.archive_base_url.rstrip("/")
        iso_day = archive_date.isoformat()
        if self.config.contour == "spot":
            iso_month = archive_date.strftime("%Y-%m")
            return (
                f"{base_url}/spot/{raw_symbol}/{raw_symbol}_{iso_day}.csv.gz",
                f"{base_url}/spot/{raw_symbol}/{raw_symbol}-{iso_month}.csv.gz",
            )
        return (f"{base_url}/trading/{raw_symbol}/{raw_symbol}{iso_day}.csv.gz",)

    def _fetch_bytes(self, url: str, timeout_seconds: int) -> tuple[bytes, str, int]:
        object.__setattr__(self, "_last_archive_url", url)
        with self._payload_cache_lock:
            cached_payload = self._payload_cache.get(url)
        if cached_payload is not None:
            object.__setattr__(self, "_memory_hits", self._memory_hits + 1)
            object.__setattr__(self, "_last_cache_hit_source", "memory")
            return cached_payload, "memory", 0
        disk_started_at = perf_counter()
        disk_cached_payload = self._load_payload_from_disk_cache(url)
        if disk_cached_payload is not None:
            with self._payload_cache_lock:
                self._payload_cache[url] = disk_cached_payload
            object.__setattr__(self, "_disk_hits", self._disk_hits + 1)
            object.__setattr__(self, "_last_cache_hit_source", "disk")
            return (
                disk_cached_payload,
                "disk",
                round((perf_counter() - disk_started_at) * 1000),
            )
        object.__setattr__(self, "_cache_misses", self._cache_misses + 1)
        object.__setattr__(self, "_last_cache_hit_source", "network")
        request_started_at = perf_counter()
        if self.fetch_bytes is not None:
            payload = self.fetch_bytes(url, timeout_seconds)
            with self._payload_cache_lock:
                self._payload_cache[url] = payload
            self._store_payload_in_disk_cache(url, payload)
            return payload, "network", round((perf_counter() - request_started_at) * 1000)
        request = Request(
            url,
            headers={
                "Accept": "application/gzip,application/octet-stream",
                "User-Agent": "cryptotechnolog/bybit-trade-backfill",
            },
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read()
        with self._payload_cache_lock:
            self._payload_cache[url] = payload
        self._store_payload_in_disk_cache(url, payload)
        return payload, "network", round((perf_counter() - request_started_at) * 1000)

    def _load_payload_from_disk_cache(self, url: str) -> bytes | None:
        cache_path = self._cache_path_for_url(url)
        if cache_path is None or not cache_path.exists():
            return None
        ttl = self.config.cache_ttl
        if ttl <= timedelta(0):
            return None
        modified_at = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=UTC)
        if datetime.now(tz=UTC) - modified_at > ttl:
            with contextlib.suppress(OSError):
                cache_path.unlink()
            return None
        return cache_path.read_bytes()

    def _store_payload_in_disk_cache(self, url: str, payload: bytes) -> None:
        cache_path = self._cache_path_for_url(url)
        if cache_path is None:
            return
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = cache_path.with_suffix(f"{cache_path.suffix}.tmp")
        temp_path.write_bytes(payload)
        temp_path.replace(cache_path)
        object.__setattr__(self, "_cache_writes", self._cache_writes + 1)

    def _cache_path_for_url(self, url: str) -> Path | None:
        cache_dir = self.config.cache_dir
        if cache_dir is None:
            return None
        parsed = urlparse(url)
        relative_parts = [part for part in parsed.path.split("/") if part]
        if not relative_parts:
            return None
        return cache_dir.joinpath(*relative_parts)

    def _prune_disk_cache_if_needed(self, *, reference_at: datetime) -> None:
        cache_dir = self.config.cache_dir
        ttl = self.config.cache_ttl
        if cache_dir is None or ttl <= timedelta(0) or not cache_dir.exists():
            return
        last_pruned_at = self._disk_cache_state.get("last_pruned_at")
        normalized_reference_at = reference_at.astimezone(UTC)
        if last_pruned_at is not None and normalized_reference_at - last_pruned_at < ttl:
            return
        prune_before = normalized_reference_at - ttl
        pruned_files = 0
        for cache_path in cache_dir.rglob("*.gz"):
            modified_at = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=UTC)
            if modified_at >= prune_before:
                continue
            try:
                cache_path.unlink()
            except OSError:
                continue
            pruned_files += 1
        self._disk_cache_state["last_pruned_at"] = normalized_reference_at
        object.__setattr__(self, "_last_cleanup_at", normalized_reference_at)
        object.__setattr__(self, "_last_pruned_files", pruned_files)

    def _append_trade_timestamps(
        self,
        *,
        payload: bytes,
        window_started_at: datetime,
        observed_at: datetime,
        aggregation: _MutableLoadedSymbolWindow,
    ) -> None:
        decode_started_at = perf_counter()
        with (
            gzip.GzipFile(fileobj=BytesIO(payload)) as gz_file,
            io.TextIOWrapper(gz_file, encoding="utf-8", newline="") as text_stream,
        ):
            parse_started_at = perf_counter()
            reader = csv.reader(text_stream)
            first_row = next(reader, None)
            timestamp_column_index = (
                _resolve_timestamp_column_index(first_row) if first_row is not None else None
            )
            if timestamp_column_index is None and first_row:
                self._append_timestamp_value(
                    raw_value=first_row[0],
                    window_started_at=window_started_at,
                    observed_at=observed_at,
                    aggregation=aggregation,
                )
            for row in reader:
                if not row:
                    continue
                if timestamp_column_index is not None:
                    if timestamp_column_index >= len(row):
                        continue
                    raw_value = row[timestamp_column_index]
                else:
                    raw_value = row[0]
                self._append_timestamp_value(
                    raw_value=raw_value,
                    window_started_at=window_started_at,
                    observed_at=observed_at,
                    aggregation=aggregation,
                )
            self._record_parse_timing(
                gzip_decode_ms=round((parse_started_at - decode_started_at) * 1000),
                csv_parse_ms=round((perf_counter() - parse_started_at) * 1000),
            )
            return

    def _append_timestamp_value(
        self,
        *,
        raw_value: object,
        window_started_at: datetime,
        observed_at: datetime,
        aggregation: _MutableLoadedSymbolWindow,
    ) -> None:
        timestamp = _parse_timestamp_value(raw_value)
        if timestamp is None or timestamp < window_started_at or timestamp > observed_at:
            return
        bucket_start = _floor_to_bucket(
            observed_at=timestamp,
            bucket_width=_TRADE_COUNT_BUCKET_WIDTH,
        )
        aggregation.bucket_counts[bucket_start] = aggregation.bucket_counts.get(bucket_start, 0) + 1
        aggregation.trade_count += 1
        if aggregation.latest_trade_at is None or timestamp > aggregation.latest_trade_at:
            aggregation.latest_trade_at = timestamp

    def _record_network_fetch_ms(self, duration_ms: int) -> None:
        with self._metrics_lock:
            object.__setattr__(self, "_last_network_fetch_ms", duration_ms)
            object.__setattr__(
                self,
                "_total_network_fetch_ms",
                self._total_network_fetch_ms + duration_ms,
            )

    def _record_disk_read_ms(self, duration_ms: int) -> None:
        with self._metrics_lock:
            object.__setattr__(self, "_last_disk_read_ms", duration_ms)
            object.__setattr__(
                self,
                "_total_disk_read_ms",
                self._total_disk_read_ms + duration_ms,
            )

    def _record_parse_timing(self, *, gzip_decode_ms: int, csv_parse_ms: int) -> None:
        with self._metrics_lock:
            object.__setattr__(self, "_last_gzip_decode_ms", gzip_decode_ms)
            object.__setattr__(self, "_last_csv_parse_ms", csv_parse_ms)
            object.__setattr__(
                self,
                "_total_gzip_decode_ms",
                self._total_gzip_decode_ms + gzip_decode_ms,
            )
            object.__setattr__(
                self,
                "_total_csv_parse_ms",
                self._total_csv_parse_ms + csv_parse_ms,
            )

    def _record_archive_total_ms(self, duration_ms: int) -> None:
        with self._metrics_lock:
            object.__setattr__(self, "_last_archive_total_ms", duration_ms)
            object.__setattr__(
                self,
                "_total_archive_total_ms",
                self._total_archive_total_ms + duration_ms,
            )

    def _record_symbol_total_ms(self, *, symbol: str, duration_ms: int) -> None:
        with self._metrics_lock:
            object.__setattr__(self, "_last_symbol_total_ms", duration_ms)
            object.__setattr__(self, "_last_symbol", symbol)
            object.__setattr__(
                self,
                "_total_symbol_total_ms",
                self._total_symbol_total_ms + duration_ms,
            )


def create_bybit_historical_trade_backfill_service(
    *,
    contour: BybitTradeBackfillContour,
) -> BybitHistoricalTradeBackfillService:
    settings = get_settings()
    return BybitHistoricalTradeBackfillService(
        config=BybitHistoricalTradeBackfillConfig(
            contour=contour,
            cache_dir=settings.data_dir / "live_feed" / "bybit_archive_cache" / contour,
        ),
    )


def _resolve_timestamp_column_index(header_row: list[str] | None) -> int | None:
    if not header_row:
        return None
    normalized_to_index = {
        str(column_name).strip(): index for index, column_name in enumerate(header_row)
    }
    for field_name in _TIMESTAMP_FIELD_CANDIDATES:
        if field_name in normalized_to_index:
            return normalized_to_index[field_name]
    return None


def _parse_timestamp_value(raw_value: object) -> datetime | None:
    if raw_value is None:
        return None
    normalized = str(raw_value).strip()
    if not normalized:
        return None
    if normalized.isdigit():
        return _parse_unix_timestamp_int(int(normalized))
    if normalized.count(".") == 1:
        whole_seconds, fractional_seconds = normalized.split(".", 1)
        if whole_seconds.isdigit() and fractional_seconds.isdigit():
            return _parse_unix_timestamp_decimal_seconds(
                whole_seconds=whole_seconds,
                fractional_seconds=fractional_seconds,
            )
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _normalize_symbol(raw_symbol: str) -> str:
    normalized = raw_symbol.strip().upper()
    if not normalized:
        raise ValueError("Bybit historical backfill requires non-empty symbol")
    return normalized


def _parse_unix_timestamp_int(raw_int: int) -> datetime | None:
    if raw_int >= 10**15:
        return datetime.fromtimestamp(raw_int / 1_000_000, tz=UTC)
    if raw_int >= 10**12:
        return datetime.fromtimestamp(raw_int / 1000, tz=UTC)
    if raw_int >= 10**9:
        return datetime.fromtimestamp(raw_int, tz=UTC)
    return None


def _parse_unix_timestamp_decimal_seconds(
    *,
    whole_seconds: str,
    fractional_seconds: str,
) -> datetime | None:
    raw_seconds = int(whole_seconds)
    if raw_seconds < 10**9:
        return None
    microseconds = int((fractional_seconds + "000000")[:6])
    return datetime.fromtimestamp(raw_seconds, tz=UTC) + timedelta(microseconds=microseconds)


def _build_archive_dates(*, window_started_at: datetime, observed_at: datetime) -> tuple[date, ...]:
    dates: list[date] = []
    current_date = window_started_at.date()
    normalized_observed_at = observed_at.astimezone(UTC)
    final_date = normalized_observed_at.date()
    if normalized_observed_at.time() == datetime.min.time():
        final_date -= timedelta(days=1)
    while current_date <= final_date:
        dates.append(current_date)
        current_date += timedelta(days=1)
    return tuple(dates)


def _resolve_closed_archive_boundary(
    *,
    window_started_at: datetime,
    covered_until_at: datetime,
) -> datetime:
    normalized_window_started_at = window_started_at.astimezone(UTC)
    normalized_covered_until_at = covered_until_at.astimezone(UTC)
    current_day_started_at = normalized_covered_until_at.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    if current_day_started_at <= normalized_window_started_at:
        return normalized_window_started_at
    return current_day_started_at


def _archive_day_closed_at(archive_date: date) -> datetime:
    return datetime(
        year=archive_date.year,
        month=archive_date.month,
        day=archive_date.day,
        tzinfo=UTC,
    ) + timedelta(days=1)


def _floor_to_bucket(*, observed_at: datetime, bucket_width: timedelta) -> datetime:
    normalized_observed_at = observed_at.astimezone(UTC)
    bucket_seconds = int(bucket_width.total_seconds())
    timestamp_seconds = int(normalized_observed_at.timestamp())
    floored_seconds = timestamp_seconds - (timestamp_seconds % bucket_seconds)
    return datetime.fromtimestamp(floored_seconds, tz=UTC)


__all__ = [
    "BybitHistoricalRecoveryPlan",
    "BybitHistoricalTradeBackfillConfig",
    "BybitHistoricalTradeBackfillResult",
    "BybitHistoricalTradeBackfillService",
    "BybitTradeBackfillContour",
    "create_bybit_historical_trade_backfill_service",
]
