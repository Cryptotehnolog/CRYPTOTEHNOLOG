"""
Event contracts для Market Data Layer.

Здесь фиксируется только vocabulary и typed payload contracts.
Runtime ingestion/orchestration будет использовать эти контракты в следующих шагах.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority, SystemEventSource, SystemEventType

if TYPE_CHECKING:
    from uuid import UUID

    from .models import (
        AdmissibleUniverseSnapshot,
        DataQualitySignal,
        OHLCVBarContract,
        OrderBookSnapshotContract,
        RankedUniverseSnapshot,
        RawUniverseSnapshot,
        SymbolMetricsContract,
        TickContract,
        UniverseQualityAssessment,
    )


class SupportsEventPayload(Protocol):
    """Протокол для typed payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в payload, совместимый с Event Bus."""


class MarketDataEventType(StrEnum):
    """Стандартный event vocabulary Phase 6."""

    TICK_RECEIVED = SystemEventType.TICK_RECEIVED
    BAR_COMPLETED = SystemEventType.BAR_COMPLETED
    ORDERBOOK_UPDATED = SystemEventType.ORDERBOOK_UPDATED
    SYMBOL_METRICS_UPDATED = SystemEventType.SYMBOL_METRICS_UPDATED
    UNIVERSE_RAW_UPDATED = SystemEventType.UNIVERSE_RAW_UPDATED
    UNIVERSE_ADMISSIBLE_UPDATED = SystemEventType.UNIVERSE_ADMISSIBLE_UPDATED
    UNIVERSE_RANKED_UPDATED = SystemEventType.UNIVERSE_RANKED_UPDATED
    UNIVERSE_CONFIDENCE_UPDATED = SystemEventType.UNIVERSE_CONFIDENCE_UPDATED
    UNIVERSE_CONFIDENCE_LOW = SystemEventType.UNIVERSE_CONFIDENCE_LOW
    UNIVERSE_READY = SystemEventType.UNIVERSE_READY
    UNIVERSE_EMPTY = SystemEventType.UNIVERSE_EMPTY
    SYMBOL_ADMITTED_TO_UNIVERSE = SystemEventType.SYMBOL_ADMITTED_TO_UNIVERSE
    SYMBOL_REMOVED_FROM_UNIVERSE = SystemEventType.SYMBOL_REMOVED_FROM_UNIVERSE
    DATA_GAP_DETECTED = SystemEventType.DATA_GAP_DETECTED
    MARKET_DATA_STALE = SystemEventType.MARKET_DATA_STALE
    MARKET_DATA_OUTLIER_DETECTED = SystemEventType.MARKET_DATA_OUTLIER_DETECTED
    MARKET_DATA_SOURCE_DEGRADED = SystemEventType.MARKET_DATA_SOURCE_DEGRADED


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в словарь payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_market_data_event(event_type: MarketDataEventType) -> Priority:
    """Определить приоритет события Market Data Layer."""
    if event_type in {
        MarketDataEventType.UNIVERSE_CONFIDENCE_LOW,
        MarketDataEventType.UNIVERSE_EMPTY,
        MarketDataEventType.DATA_GAP_DETECTED,
        MarketDataEventType.MARKET_DATA_SOURCE_DEGRADED,
    }:
        return Priority.CRITICAL

    if event_type in {
        MarketDataEventType.BAR_COMPLETED,
        MarketDataEventType.UNIVERSE_ADMISSIBLE_UPDATED,
        MarketDataEventType.UNIVERSE_RANKED_UPDATED,
        MarketDataEventType.SYMBOL_REMOVED_FROM_UNIVERSE,
        MarketDataEventType.MARKET_DATA_STALE,
        MarketDataEventType.MARKET_DATA_OUTLIER_DETECTED,
    }:
        return Priority.HIGH

    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class TickReceivedPayload:
    """Payload контракта TICK_RECEIVED."""

    symbol: str
    exchange: str
    price: str
    quantity: str
    side: str
    timestamp: str
    trade_id: str
    is_buyer_maker: bool

    @classmethod
    def from_contract(cls, tick: TickContract) -> TickReceivedPayload:
        """Создать payload из typed tick contract."""
        return cls(
            symbol=tick.symbol,
            exchange=tick.exchange,
            price=str(tick.price),
            quantity=str(tick.quantity),
            side=tick.side.value,
            timestamp=tick.timestamp.isoformat(),
            trade_id=tick.trade_id,
            is_buyer_maker=tick.is_buyer_maker,
        )

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


@dataclass(slots=True, frozen=True)
class BarCompletedPayload:
    """Payload контракта BAR_COMPLETED."""

    symbol: str
    exchange: str
    timeframe: str
    open_time: str
    close_time: str
    open: str
    high: str
    low: str
    close: str
    volume: str
    bid_volume: str
    ask_volume: str
    trades_count: int
    is_closed: bool
    is_gap_affected: bool

    @classmethod
    def from_contract(cls, bar: OHLCVBarContract) -> BarCompletedPayload:
        """Создать payload из typed bar contract."""
        return cls(
            symbol=bar.symbol,
            exchange=bar.exchange,
            timeframe=bar.timeframe.value,
            open_time=bar.open_time.isoformat(),
            close_time=bar.close_time.isoformat(),
            open=str(bar.open),
            high=str(bar.high),
            low=str(bar.low),
            close=str(bar.close),
            volume=str(bar.volume),
            bid_volume=str(bar.bid_volume),
            ask_volume=str(bar.ask_volume),
            trades_count=bar.trades_count,
            is_closed=bar.is_closed,
            is_gap_affected=bar.is_gap_affected,
        )

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


@dataclass(slots=True, frozen=True)
class OrderBookUpdatedPayload:
    """Payload контракта ORDERBOOK_UPDATED."""

    symbol: str
    exchange: str
    timestamp: str
    bids: tuple[tuple[str, str, int | None], ...]
    asks: tuple[tuple[str, str, int | None], ...]
    spread_bps: str
    checksum: str | None
    is_gap_affected: bool

    @classmethod
    def from_contract(cls, snapshot: OrderBookSnapshotContract) -> OrderBookUpdatedPayload:
        """Создать payload из typed orderbook contract."""
        return cls(
            symbol=snapshot.symbol,
            exchange=snapshot.exchange,
            timestamp=snapshot.timestamp.isoformat(),
            bids=tuple(
                (str(level.price), str(level.quantity), level.orders_count)
                for level in snapshot.bids
            ),
            asks=tuple(
                (str(level.price), str(level.quantity), level.orders_count)
                for level in snapshot.asks
            ),
            spread_bps=str(snapshot.spread_bps),
            checksum=snapshot.checksum,
            is_gap_affected=snapshot.is_gap_affected,
        )

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


@dataclass(slots=True, frozen=True)
class SymbolMetricsUpdatedPayload:
    """Payload контракта SYMBOL_METRICS_UPDATED."""

    symbol: str
    exchange: str
    calculated_at: str
    spread_bps: str
    top_of_book_depth_usd: str
    depth_5bps_usd: str
    latency_ms: str
    coverage_ratio: str
    data_freshness_ms: int
    quality_score: str
    funding_8h: str | None
    volume_24h_usd: str | None
    open_interest_usd: str | None
    metadata: dict[str, object]

    @classmethod
    def from_contract(cls, metrics: SymbolMetricsContract) -> SymbolMetricsUpdatedPayload:
        """Создать payload из typed symbol metrics contract."""
        return cls(
            symbol=metrics.symbol,
            exchange=metrics.exchange,
            calculated_at=metrics.calculated_at.isoformat(),
            spread_bps=str(metrics.spread_bps),
            top_of_book_depth_usd=str(metrics.top_of_book_depth_usd),
            depth_5bps_usd=str(metrics.depth_5bps_usd),
            latency_ms=str(metrics.latency_ms),
            coverage_ratio=str(metrics.coverage_ratio),
            data_freshness_ms=metrics.data_freshness_ms,
            quality_score=str(metrics.quality_score),
            funding_8h=str(metrics.funding_8h) if metrics.funding_8h is not None else None,
            volume_24h_usd=(
                str(metrics.volume_24h_usd) if metrics.volume_24h_usd is not None else None
            ),
            open_interest_usd=(
                str(metrics.open_interest_usd)
                if metrics.open_interest_usd is not None
                else None
            ),
            metadata=metrics.metadata.copy(),
        )

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


@dataclass(slots=True, frozen=True)
class UniverseSnapshotPayload:
    """Payload для versioned universe snapshots."""

    version: int
    snapshot_type: str
    created_at: str
    symbols: tuple[tuple[str, str], ...]
    symbols_count: int
    confidence: str | None = None
    upstream_admissible_version: int | None = None
    ranking_model: str | None = None
    excluded_symbols: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_raw_snapshot(cls, snapshot: RawUniverseSnapshot) -> UniverseSnapshotPayload:
        """Сконвертировать raw universe snapshot в event payload."""
        return cls(
            version=snapshot.version,
            snapshot_type="raw",
            created_at=snapshot.created_at.isoformat(),
            symbols=tuple((symbol.symbol, symbol.exchange) for symbol in snapshot.symbols),
            symbols_count=len(snapshot.symbols),
        )

    @classmethod
    def from_admissible_snapshot(
        cls,
        snapshot: AdmissibleUniverseSnapshot,
    ) -> UniverseSnapshotPayload:
        """Сконвертировать admissible universe snapshot в event payload."""
        return cls(
            version=snapshot.version,
            snapshot_type="admissible",
            created_at=snapshot.created_at.isoformat(),
            symbols=tuple(
                (item.symbol.symbol, item.symbol.exchange) for item in snapshot.symbols
            ),
            symbols_count=len(snapshot.symbols),
            confidence=(
                str(snapshot.confidence) if snapshot.confidence is not None else None
            ),
            excluded_symbols=tuple(
                (excluded.symbol, excluded.exchange) for excluded in snapshot.excluded_symbols
            ),
        )

    @classmethod
    def from_ranked_snapshot(cls, snapshot: RankedUniverseSnapshot) -> UniverseSnapshotPayload:
        """Сконвертировать ranked universe snapshot в event payload."""
        return cls(
            version=snapshot.version,
            snapshot_type="ranked",
            created_at=snapshot.created_at.isoformat(),
            symbols=tuple((entry.symbol.symbol, entry.symbol.exchange) for entry in snapshot.entries),
            symbols_count=len(snapshot.entries),
            upstream_admissible_version=snapshot.upstream_admissible_version,
            ranking_model=snapshot.ranking_model,
        )

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


@dataclass(slots=True, frozen=True)
class UniverseQualityPayload:
    """Payload для confidence/quality semantics universe."""

    version: int
    measured_at: str
    confidence: str
    state: str
    raw_count: int
    admissible_count: int
    ranked_count: int
    blocking_reasons: tuple[str, ...]
    worst_symbols: tuple[str, ...]

    @classmethod
    def from_assessment(cls, assessment: UniverseQualityAssessment) -> UniverseQualityPayload:
        """Создать payload из typed quality assessment."""
        return cls(
            version=assessment.version,
            measured_at=assessment.measured_at.isoformat(),
            confidence=str(assessment.confidence),
            state=assessment.state.value,
            raw_count=assessment.raw_count,
            admissible_count=assessment.admissible_count,
            ranked_count=assessment.ranked_count,
            blocking_reasons=assessment.blocking_reasons,
            worst_symbols=assessment.worst_symbols,
        )

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


@dataclass(slots=True, frozen=True)
class SymbolUniverseChangePayload:
    """Payload для добавления/удаления символа из admissible universe."""

    symbol: str
    exchange: str
    version: int
    changed_at: str
    reasons: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


@dataclass(slots=True, frozen=True)
class DataQualitySignalPayload:
    """Payload для data quality сигналов."""

    symbol: str
    exchange: str
    issue_type: str
    severity: str
    detected_at: str
    feed: str
    gap_duration_ms: int | None
    staleness_ms: int | None
    outlier_score: str | None
    details: dict[str, object]

    @classmethod
    def from_signal(cls, signal: DataQualitySignal) -> DataQualitySignalPayload:
        """Создать payload из typed data quality signal."""
        return cls(
            symbol=signal.symbol,
            exchange=signal.exchange,
            issue_type=signal.issue_type.value,
            severity=signal.severity.value,
            detected_at=signal.detected_at.isoformat(),
            feed=signal.feed,
            gap_duration_ms=signal.gap_duration_ms,
            staleness_ms=signal.staleness_ms,
            outlier_score=(
                str(signal.outlier_score) if signal.outlier_score is not None else None
            ),
            details=signal.details.copy(),
        )

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""
        return _slots_dataclass_to_payload(self)


def build_market_data_event(
    *,
    event_type: MarketDataEventType,
    payload: SupportsEventPayload,
    source: str = SystemEventSource.MARKET_DATA_MANAGER,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для Market Data Layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_market_data_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event
