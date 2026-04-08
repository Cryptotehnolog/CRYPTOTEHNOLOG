"""Derived 24h trade-count layer for Bybit public trade streams."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_ROLLING_WINDOW = timedelta(hours=24)
_BUCKET_WIDTH = timedelta(minutes=1)
_SECONDS_PER_MINUTE = 60
_PERSISTENCE_FLUSH_INTERVAL = timedelta(seconds=30)
_MAX_RESTORE_GAP = timedelta(seconds=90)
_PERSISTENCE_FORMAT_VERSION = 1


@dataclass(slots=True, frozen=True)
class BybitDerivedTradeCountSymbolSnapshot:
    """Operator-facing per-symbol derived trade-count snapshot."""

    symbol: str
    trade_count_24h: int | None
    observed_trade_count_since_reset: int


@dataclass(slots=True, frozen=True)
class BybitDerivedTradeCountDiagnostics:
    """Operator-facing diagnostics for derived trade-count reliability."""

    state: str
    ready: bool
    observation_started_at: str | None
    reliable_after: str | None
    last_gap_at: str | None
    last_gap_reason: str | None
    backfill_status: str | None
    backfill_needed: bool
    backfill_processed_archives: int | None
    backfill_total_archives: int | None
    backfill_progress_percent: int | None
    last_backfill_at: str | None
    last_backfill_source: str | None
    last_backfill_reason: str | None
    symbol_snapshots: tuple[BybitDerivedTradeCountSymbolSnapshot, ...]


@dataclass(slots=True, frozen=True)
class BybitDerivedTradeCountPersistedState:
    """Persisted local snapshot for derived trade-count restart recovery."""

    persisted_at: datetime
    state: str
    observation_started_at: datetime | None
    last_gap_at: datetime | None
    last_gap_reason: str | None
    live_tail_required_after: datetime | None
    latest_observed_trade_at: datetime | None
    observed_trade_count_since_reset: dict[str, int]
    trade_count_buckets: dict[str, dict[datetime, int]]
    historical_window_restored: bool = False


@dataclass(slots=True, frozen=True)
class BybitDerivedTradeCountPersistenceStore:
    """Local JSON persistence for derived trade-count state."""

    path: Path

    def load(self) -> BybitDerivedTradeCountPersistedState | None:
        if not self.path.exists():
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        if int(payload.get("format_version", 0)) != _PERSISTENCE_FORMAT_VERSION:
            return None
        raw_buckets = payload.get("trade_count_buckets")
        raw_counts = payload.get("observed_trade_count_since_reset")
        if not isinstance(raw_buckets, dict) or not isinstance(raw_counts, dict):
            return None
        return BybitDerivedTradeCountPersistedState(
            persisted_at=_datetime_or_none(payload.get("persisted_at")) or datetime.now(tz=UTC),
            state=str(payload.get("state", "warming_up")),
            observation_started_at=_datetime_or_none(payload.get("observation_started_at")),
            last_gap_at=_datetime_or_none(payload.get("last_gap_at")),
            last_gap_reason=(
                str(payload["last_gap_reason"])
                if isinstance(payload.get("last_gap_reason"), str)
                else None
            ),
            live_tail_required_after=_datetime_or_none(payload.get("live_tail_required_after")),
            latest_observed_trade_at=_datetime_or_none(payload.get("latest_observed_trade_at")),
            observed_trade_count_since_reset={
                str(symbol): int(value)
                for symbol, value in raw_counts.items()
                if isinstance(symbol, str) and isinstance(value, int)
            },
            trade_count_buckets={
                str(symbol): {
                    restored_bucket: int(count)
                    for bucket_start, count in symbol_buckets.items()
                    if isinstance(bucket_start, str)
                    and isinstance(count, int)
                    and (restored_bucket := _datetime_or_none(bucket_start)) is not None
                }
                for symbol, symbol_buckets in raw_buckets.items()
                if isinstance(symbol, str) and isinstance(symbol_buckets, dict)
            },
            historical_window_restored=bool(payload.get("historical_window_restored", False)),
        )

    def save(self, state: BybitDerivedTradeCountPersistedState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format_version": _PERSISTENCE_FORMAT_VERSION,
            "persisted_at": state.persisted_at.astimezone(UTC).isoformat(),
            "state": state.state,
            "observation_started_at": _iso_or_none(state.observation_started_at),
            "last_gap_at": _iso_or_none(state.last_gap_at),
            "last_gap_reason": state.last_gap_reason,
            "live_tail_required_after": _iso_or_none(state.live_tail_required_after),
            "latest_observed_trade_at": _iso_or_none(state.latest_observed_trade_at),
            "historical_window_restored": state.historical_window_restored,
            "observed_trade_count_since_reset": state.observed_trade_count_since_reset,
            "trade_count_buckets": {
                symbol: {
                    bucket_start.astimezone(UTC).isoformat(): count
                    for bucket_start, count in sorted(symbol_buckets.items())
                }
                for symbol, symbol_buckets in state.trade_count_buckets.items()
            },
        }
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        temp_path.replace(self.path)


@dataclass(slots=True)
class BybitDerivedTradeCountTracker:
    """Track rolling 24h trade counts with bounded-memory minute buckets."""

    symbols: tuple[str, ...]
    window: timedelta = _ROLLING_WINDOW
    bucket_width: timedelta = _BUCKET_WIDTH
    _trade_count_buckets: dict[str, dict[datetime, int]] = field(init=False)
    _observed_trade_count_since_reset: dict[str, int] = field(init=False)
    _state: str = field(default="warming_up", init=False)
    _observation_started_at: datetime | None = field(default=None, init=False)
    _last_gap_at: datetime | None = field(default=None, init=False)
    _last_gap_reason: str | None = field(default=None, init=False)
    _latest_observed_trade_at: datetime | None = field(default=None, init=False)
    _last_persisted_at: datetime | None = field(default=None, init=False)
    _last_persisted_trade_bucket: datetime | None = field(default=None, init=False)
    _backfill_status: str | None = field(default=None, init=False)
    _backfill_needed: bool = field(default=False, init=False)
    _backfill_processed_archives: int | None = field(default=None, init=False)
    _backfill_total_archives: int | None = field(default=None, init=False)
    _last_backfill_at: datetime | None = field(default=None, init=False)
    _last_backfill_source: str | None = field(default=None, init=False)
    _last_backfill_reason: str | None = field(default=None, init=False)
    _live_tail_required_after: datetime | None = field(default=None, init=False)
    _historical_window_restored: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._trade_count_buckets = {symbol: {} for symbol in self.symbols}
        self._observed_trade_count_since_reset = dict.fromkeys(self.symbols, 0)

    def mark_observation_started(self, *, observed_at: datetime) -> None:
        """Resume accumulation after a healthy subscription boundary."""
        normalized_observed_at = observed_at.astimezone(UTC)
        if self._state == "ready":
            return
        if self._state == "not_reliable_after_gap":
            self._state = "warming_up"
        if self._state == "live_tail_pending_after_gap":
            return
        if self._observation_started_at is None:
            self._observation_started_at = normalized_observed_at

    def note_trade(self, *, symbol: str, observed_at: datetime) -> None:
        """Accumulate one observed public trade using exchange event time."""
        if symbol not in self._trade_count_buckets:
            return
        normalized_observed_at = observed_at.astimezone(UTC)
        self.mark_observation_started(observed_at=normalized_observed_at)
        bucket_start = _floor_to_bucket(
            observed_at=normalized_observed_at,
            bucket_width=self.bucket_width,
        )
        buckets = self._trade_count_buckets[symbol]
        buckets[bucket_start] = buckets.get(bucket_start, 0) + 1
        self._observed_trade_count_since_reset[symbol] += 1
        self._latest_observed_trade_at = normalized_observed_at
        self._prune_symbol(symbol=symbol, observed_at=normalized_observed_at)
        if (
            self._live_tail_required_after is not None
            and normalized_observed_at >= self._live_tail_required_after
        ):
            self._live_tail_required_after = None
            if self._state == "live_tail_pending_after_gap":
                self._state = "warming_up"
        if (
            self._state == "warming_up"
            and self._observation_started_at is not None
            and normalized_observed_at - self._observation_started_at >= self.window
            and self._live_tail_required_after is None
        ):
            self._state = "ready"

    def mark_gap(self, *, observed_at: datetime, reason: str) -> None:
        """Reset reliability after a disconnect gap or recovery boundary."""
        normalized_observed_at = observed_at.astimezone(UTC)
        preserve_backfill_not_needed = (
            self._backfill_needed is False and self._backfill_status == "not_needed"
        )
        for symbol in self.symbols:
            self._trade_count_buckets[symbol].clear()
            self._observed_trade_count_since_reset[symbol] = 0
        self._state = "not_reliable_after_gap"
        self._observation_started_at = None
        self._last_gap_at = normalized_observed_at
        self._last_gap_reason = reason
        self._latest_observed_trade_at = None
        self._backfill_status = "not_needed" if preserve_backfill_not_needed else None
        self._backfill_needed = False
        self._backfill_processed_archives = None
        self._backfill_total_archives = None
        self._last_backfill_at = None
        self._last_backfill_source = None
        self._last_backfill_reason = None
        self._live_tail_required_after = None
        self._historical_window_restored = False

    def mark_gap_preserving_historical_window(self, *, observed_at: datetime, reason: str) -> None:
        """Сбросить ready-state после gap, но сохранить уже восстановленное historical окно."""
        normalized_observed_at = observed_at.astimezone(UTC)
        preserved_observation_started_at = self._observation_started_at
        for symbol in self.symbols:
            self._prune_symbol(symbol=symbol, observed_at=normalized_observed_at)
            self._observed_trade_count_since_reset[symbol] = 0
        self._state = "live_tail_pending_after_gap"
        self._observation_started_at = preserved_observation_started_at or normalized_observed_at
        self._last_gap_at = normalized_observed_at
        self._last_gap_reason = reason
        self._latest_observed_trade_at = None
        self._live_tail_required_after = normalized_observed_at

    @property
    def has_restored_historical_window(self) -> bool:
        return self._historical_window_restored

    def get_diagnostics(self, *, observed_at: datetime) -> BybitDerivedTradeCountDiagnostics:
        """Return operator-facing readiness and count snapshots."""
        normalized_observed_at = observed_at.astimezone(UTC)
        if (
            self._state == "warming_up"
            and self._observation_started_at is not None
            and normalized_observed_at - self._observation_started_at >= self.window
            and self._live_tail_required_after is None
        ):
            self._state = "ready"
        symbol_snapshots: list[BybitDerivedTradeCountSymbolSnapshot] = []
        for symbol in self.symbols:
            self._prune_symbol(symbol=symbol, observed_at=normalized_observed_at)
            rolling_trade_count = sum(self._trade_count_buckets[symbol].values())
            symbol_snapshots.append(
                BybitDerivedTradeCountSymbolSnapshot(
                    symbol=symbol,
                    trade_count_24h=rolling_trade_count if self.ready else None,
                    observed_trade_count_since_reset=self._observed_trade_count_since_reset[symbol],
                )
            )
        return BybitDerivedTradeCountDiagnostics(
            state=self._state,
            ready=self.ready,
            observation_started_at=_iso_or_none(self._observation_started_at),
            reliable_after=_iso_or_none(self.reliable_after),
            last_gap_at=_iso_or_none(self._last_gap_at),
            last_gap_reason=self._last_gap_reason,
            backfill_status=self._backfill_status,
            backfill_needed=self._backfill_needed,
            backfill_processed_archives=self._backfill_processed_archives,
            backfill_total_archives=self._backfill_total_archives,
            backfill_progress_percent=_calculate_backfill_progress_percent(
                processed_archives=self._backfill_processed_archives,
                total_archives=self._backfill_total_archives,
            ),
            last_backfill_at=_iso_or_none(self._last_backfill_at),
            last_backfill_source=self._last_backfill_source,
            last_backfill_reason=self._last_backfill_reason,
            symbol_snapshots=tuple(symbol_snapshots),
        )

    @property
    def ready(self) -> bool:
        return self._state == "ready"

    @property
    def reliable_after(self) -> datetime | None:
        baseline_ready_at = (
            self._observation_started_at + self.window
            if self._observation_started_at is not None
            else None
        )
        if baseline_ready_at is None:
            return self._live_tail_required_after
        if self._live_tail_required_after is None:
            return baseline_ready_at
        return max(baseline_ready_at, self._live_tail_required_after)

    def should_persist(self, *, observed_at: datetime, force: bool = False) -> bool:
        if force:
            return True
        normalized_observed_at = observed_at.astimezone(UTC)
        current_bucket = _floor_to_bucket(
            observed_at=normalized_observed_at,
            bucket_width=self.bucket_width,
        )
        if self._last_persisted_at is None or self._last_persisted_trade_bucket is None:
            return True
        if current_bucket > self._last_persisted_trade_bucket:
            return True
        return normalized_observed_at - self._last_persisted_at >= _PERSISTENCE_FLUSH_INTERVAL

    def mark_persisted(self, *, observed_at: datetime) -> None:
        normalized_observed_at = observed_at.astimezone(UTC)
        self._last_persisted_at = normalized_observed_at
        self._last_persisted_trade_bucket = _floor_to_bucket(
            observed_at=self._latest_observed_trade_at or normalized_observed_at,
            bucket_width=self.bucket_width,
        )

    def to_persisted_state(self, *, persisted_at: datetime) -> BybitDerivedTradeCountPersistedState:
        normalized_persisted_at = persisted_at.astimezone(UTC)
        for symbol in self.symbols:
            self._prune_symbol(symbol=symbol, observed_at=normalized_persisted_at)
        return BybitDerivedTradeCountPersistedState(
            persisted_at=normalized_persisted_at,
            state=self._state,
            observation_started_at=self._observation_started_at,
            last_gap_at=self._last_gap_at,
            last_gap_reason=self._last_gap_reason,
            live_tail_required_after=self._live_tail_required_after,
            latest_observed_trade_at=self._latest_observed_trade_at,
            historical_window_restored=self._historical_window_restored,
            observed_trade_count_since_reset=dict(self._observed_trade_count_since_reset),
            trade_count_buckets={
                symbol: dict(symbol_buckets)
                for symbol, symbol_buckets in self._trade_count_buckets.items()
            },
        )

    def restore_from_persisted_state(
        self,
        state: BybitDerivedTradeCountPersistedState,
        *,
        restored_at: datetime,
        max_restore_gap: timedelta = _MAX_RESTORE_GAP,
    ) -> None:
        normalized_restored_at = restored_at.astimezone(UTC)
        if normalized_restored_at - state.persisted_at.astimezone(UTC) > max_restore_gap:
            self.mark_gap(observed_at=normalized_restored_at, reason="restart_persistence_gap")
            return
        for symbol in self.symbols:
            self._trade_count_buckets[symbol] = dict(state.trade_count_buckets.get(symbol, {}))
            self._observed_trade_count_since_reset[symbol] = int(
                state.observed_trade_count_since_reset.get(symbol, 0)
            )
            self._prune_symbol(symbol=symbol, observed_at=normalized_restored_at)
        self._state = (
            state.state
            if state.state in {"warming_up", "ready", "live_tail_pending_after_gap"}
            else "not_reliable_after_gap"
        )
        self._observation_started_at = (
            state.observation_started_at.astimezone(UTC)
            if state.observation_started_at is not None
            else None
        )
        self._last_gap_at = (
            state.last_gap_at.astimezone(UTC) if state.last_gap_at is not None else None
        )
        self._last_gap_reason = state.last_gap_reason
        self._live_tail_required_after = (
            state.live_tail_required_after.astimezone(UTC)
            if state.live_tail_required_after is not None
            else None
        )
        self._latest_observed_trade_at = (
            state.latest_observed_trade_at.astimezone(UTC)
            if state.latest_observed_trade_at is not None
            else None
        )
        self._historical_window_restored = bool(state.historical_window_restored)
        if self._state == "not_reliable_after_gap":
            for symbol in self.symbols:
                self._trade_count_buckets[symbol].clear()
                self._observed_trade_count_since_reset[symbol] = 0
            self._historical_window_restored = False
        if (
            self._state == "warming_up"
            and self._observation_started_at is not None
            and normalized_restored_at - self._observation_started_at >= self.window
            and self._live_tail_required_after is None
        ):
            self._state = "ready"
        self.mark_persisted(observed_at=state.persisted_at)

    def restore_historical_window(
        self,
        *,
        trades_by_symbol: dict[str, tuple[datetime, ...]] | None = None,
        trade_buckets_by_symbol: dict[str, dict[datetime, int]] | None = None,
        latest_trade_at_by_symbol: dict[str, datetime | None] | None = None,
        window_started_at: datetime,
        covered_until_at: datetime,
        observed_at: datetime,
        source: str = "bybit_public_archive",
        processed_archives: int | None = None,
        total_archives: int | None = None,
        status: str = "backfilled",
        reason: str | None = None,
    ) -> None:
        normalized_observed_at = observed_at.astimezone(UTC)
        normalized_window_started_at = window_started_at.astimezone(UTC)
        normalized_covered_until_at = covered_until_at.astimezone(UTC)
        preexisting_latest_trade_at = self._latest_observed_trade_at
        covered_bucket = _floor_to_bucket(
            observed_at=normalized_covered_until_at,
            bucket_width=self.bucket_width,
        )
        live_tail_buckets = {
            symbol: {
                bucket_start: count
                for bucket_start, count in self._trade_count_buckets[symbol].items()
                if bucket_start >= covered_bucket
            }
            for symbol in self.symbols
        }
        latest_trade_at: datetime | None = None
        for symbol in self.symbols:
            restored_buckets: dict[datetime, int] = {}
            compact_buckets = (
                trade_buckets_by_symbol.get(symbol, {})
                if trade_buckets_by_symbol is not None
                else {}
            )
            if compact_buckets:
                for bucket_start, count in compact_buckets.items():
                    normalized_bucket_start = bucket_start.astimezone(UTC)
                    restored_buckets[normalized_bucket_start] = restored_buckets.get(
                        normalized_bucket_start, 0
                    ) + int(count)
                compact_latest_trade_at = (
                    latest_trade_at_by_symbol.get(symbol)
                    if latest_trade_at_by_symbol is not None
                    else None
                )
                if compact_latest_trade_at is not None:
                    normalized_latest_trade_at = compact_latest_trade_at.astimezone(UTC)
                    if latest_trade_at is None or normalized_latest_trade_at > latest_trade_at:
                        latest_trade_at = normalized_latest_trade_at
            else:
                for trade_at in (trades_by_symbol or {}).get(symbol, ()):
                    normalized_trade_at = trade_at.astimezone(UTC)
                    bucket_start = _floor_to_bucket(
                        observed_at=normalized_trade_at,
                        bucket_width=self.bucket_width,
                    )
                    restored_buckets[bucket_start] = restored_buckets.get(bucket_start, 0) + 1
                    if latest_trade_at is None or normalized_trade_at > latest_trade_at:
                        latest_trade_at = normalized_trade_at
            for bucket_start, count in live_tail_buckets[symbol].items():
                restored_buckets[bucket_start] = restored_buckets.get(bucket_start, 0) + count
            self._trade_count_buckets[symbol] = restored_buckets
            self._prune_symbol(symbol=symbol, observed_at=normalized_observed_at)
        self._observation_started_at = normalized_window_started_at
        effective_latest_trade_at: datetime | None
        if preexisting_latest_trade_at is None:
            effective_latest_trade_at = latest_trade_at
        elif latest_trade_at is None:
            effective_latest_trade_at = preexisting_latest_trade_at
        else:
            effective_latest_trade_at = max(preexisting_latest_trade_at, latest_trade_at)
        self._latest_observed_trade_at = effective_latest_trade_at
        self._live_tail_required_after = (
            normalized_covered_until_at
            if effective_latest_trade_at is None
            or effective_latest_trade_at < normalized_covered_until_at
            else None
        )
        self._state = (
            "ready"
            if (
                normalized_observed_at - normalized_window_started_at >= self.window
                and self._live_tail_required_after is None
            )
            else "warming_up"
        )
        self._historical_window_restored = True
        self._backfill_status = status
        self._backfill_needed = True
        self._backfill_processed_archives = processed_archives
        self._backfill_total_archives = total_archives
        self._last_backfill_at = normalized_observed_at
        self._last_backfill_source = source
        self._last_backfill_reason = reason

    def mark_backfill_unavailable(
        self,
        *,
        observed_at: datetime,
        reason: str,
        source: str = "bybit_public_archive",
        processed_archives: int | None = None,
        total_archives: int | None = None,
    ) -> None:
        self._backfill_status = "unavailable"
        self._backfill_needed = True
        self._backfill_processed_archives = processed_archives
        self._backfill_total_archives = total_archives
        self._last_backfill_at = observed_at.astimezone(UTC)
        self._last_backfill_source = source
        self._last_backfill_reason = reason

    def mark_backfill_not_needed(self) -> None:
        self._backfill_needed = False
        self._backfill_status = "not_needed"
        self._backfill_processed_archives = None
        self._backfill_total_archives = None
        self._last_backfill_reason = None

    def mark_backfill_pending(self, *, total_archives: int | None = None) -> None:
        self._backfill_needed = True
        self._backfill_status = "pending"
        self._backfill_processed_archives = 0
        self._backfill_total_archives = total_archives
        self._last_backfill_reason = None

    def mark_backfill_running(self, *, processed_archives: int, total_archives: int) -> None:
        self._backfill_needed = True
        self._backfill_status = "running"
        self._backfill_processed_archives = processed_archives
        self._backfill_total_archives = total_archives
        self._last_backfill_reason = None

    def mark_backfill_skipped(
        self,
        *,
        observed_at: datetime,
        reason: str,
        source: str = "bybit_public_archive",
        processed_archives: int | None = None,
        total_archives: int | None = None,
    ) -> None:
        self._backfill_needed = True
        self._backfill_status = "skipped"
        self._backfill_processed_archives = processed_archives
        self._backfill_total_archives = total_archives
        self._last_backfill_at = observed_at.astimezone(UTC)
        self._last_backfill_source = source
        self._last_backfill_reason = reason

    def _prune_symbol(self, *, symbol: str, observed_at: datetime) -> None:
        threshold = _floor_to_bucket(
            observed_at=observed_at - self.window,
            bucket_width=self.bucket_width,
        )
        buckets = self._trade_count_buckets[symbol]
        stale_buckets = [bucket_start for bucket_start in buckets if bucket_start < threshold]
        for bucket_start in stale_buckets:
            del buckets[bucket_start]


def _floor_to_bucket(*, observed_at: datetime, bucket_width: timedelta) -> datetime:
    normalized = observed_at.astimezone(UTC).replace(second=0, microsecond=0)
    bucket_seconds = int(bucket_width.total_seconds())
    if bucket_seconds <= _SECONDS_PER_MINUTE:
        return normalized
    bucket_minutes = bucket_seconds // _SECONDS_PER_MINUTE
    minute = (normalized.minute // bucket_minutes) * bucket_minutes
    return normalized.replace(minute=minute)


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _calculate_backfill_progress_percent(
    *,
    processed_archives: int | None,
    total_archives: int | None,
) -> int | None:
    if processed_archives is None or total_archives is None or total_archives <= 0:
        return None
    return max(0, min(100, int((processed_archives / total_archives) * 100)))


def _datetime_or_none(raw_value: object) -> datetime | None:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None
    return datetime.fromisoformat(raw_value).astimezone(UTC)


__all__ = [
    "BybitDerivedTradeCountDiagnostics",
    "BybitDerivedTradeCountPersistedState",
    "BybitDerivedTradeCountPersistenceStore",
    "BybitDerivedTradeCountSymbolSnapshot",
    "BybitDerivedTradeCountTracker",
]
