"""
Typed event contracts для Phase 20 backtesting / replay foundation.

Этот vocabulary intentionally узкий:
- без analytics / reporting ownership;
- без dashboard / operator semantics;
- без comparison / ranking semantics;
- без paper/live comparison ownership;
- без simulated Execution / OMS takeover.

Legacy generic replay-engine events сохранены ниже только как compatibility contour.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Any, Protocol, cast

from cryptotechnolog.core.event import Event, Priority

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from .models import HistoricalInputContract, ReplayCandidate


class ReplayEventType(StrEnum):
    """Минимальный event vocabulary Phase 20 foundation."""

    REPLAY_INPUT_REGISTERED = "REPLAY_INPUT_REGISTERED"
    REPLAY_CANDIDATE_UPDATED = "REPLAY_CANDIDATE_UPDATED"
    REPLAY_EXECUTED = "REPLAY_EXECUTED"
    REPLAY_ABSTAINED = "REPLAY_ABSTAINED"
    REPLAY_INVALIDATED = "REPLAY_INVALIDATED"


class ReplayEventSource(StrEnum):
    """Стандартные источники событий replay layer."""

    REPLAY_RUNTIME = "REPLAY_RUNTIME"
    REPLAY_CONTOUR = "REPLAY_CONTOUR"


class SupportsReplayPayload(Protocol):
    """Протокол для typed replay payload contracts."""

    def to_payload(self) -> dict[str, object]:
        """Конвертировать контракт в Event payload."""


def _slots_dataclass_to_payload(instance: object) -> dict[str, object]:
    """Преобразовать slots-dataclass в payload без зависимости от __dict__."""
    dataclass_type = cast("Any", instance.__class__)
    return {field.name: getattr(instance, field.name) for field in fields(dataclass_type)}


def default_priority_for_replay_event(event_type: ReplayEventType) -> Priority:
    """Определить приоритет foundation replay event."""
    if event_type == ReplayEventType.REPLAY_EXECUTED:
        return Priority.HIGH
    return Priority.NORMAL


@dataclass(slots=True, frozen=True)
class HistoricalInputPayload:
    """Payload historical input contract для event publication."""

    input_id: str
    input_name: str
    symbol: str
    exchange: str
    source: str
    kind: str
    timeframe: str | None
    source_reference: str | None
    coverage_start_at: str
    coverage_end_at: str
    observed_events: int
    expected_events: int
    metadata: dict[str, object]

    @classmethod
    def from_input(cls, historical_input: HistoricalInputContract) -> HistoricalInputPayload:
        return cls(
            input_id=str(historical_input.input_id),
            input_name=historical_input.input_name,
            symbol=historical_input.symbol,
            exchange=historical_input.exchange,
            source=historical_input.source.value,
            kind=historical_input.kind.value,
            timeframe=(
                historical_input.timeframe.value if historical_input.timeframe is not None else None
            ),
            source_reference=historical_input.source_reference,
            coverage_start_at=historical_input.coverage_window.start_at.isoformat(),
            coverage_end_at=historical_input.coverage_window.end_at.isoformat(),
            observed_events=historical_input.coverage_window.observed_events,
            expected_events=historical_input.coverage_window.expected_events,
            metadata=historical_input.metadata.copy(),
        )

    def to_payload(self) -> dict[str, object]:
        return _slots_dataclass_to_payload(self)


@dataclass(slots=True, frozen=True)
class ReplayCandidatePayload:
    """Payload replay candidate для event publication."""

    replay_id: str
    contour_name: str
    replay_name: str
    symbol: str
    exchange: str
    source: str
    status: str
    decision: str
    validity_status: str
    historical_input_id: str | None
    timeframe: str | None
    validation_review_id: str | None
    paper_rehearsal_id: str | None
    reason_code: str | None
    generated_at: str
    expires_at: str | None
    coverage_start_at: str
    coverage_end_at: str
    observed_events: int
    expected_events: int
    missing_inputs: tuple[str, ...]
    recorder_state: dict[str, object] | None
    metadata: dict[str, object]

    @classmethod
    def from_candidate(cls, candidate: ReplayCandidate) -> ReplayCandidatePayload:
        recorder_state: dict[str, object] | None = None
        if candidate.recorder_state is not None:
            recorder_state = {
                "recorded_events": candidate.recorder_state.recorded_events,
                "persisted_artifact": candidate.recorder_state.persisted_artifact,
                "last_recorded_at": (
                    candidate.recorder_state.last_recorded_at.isoformat()
                    if candidate.recorder_state.last_recorded_at is not None
                    else None
                ),
            }
        return cls(
            replay_id=str(candidate.replay_id),
            contour_name=candidate.contour_name,
            replay_name=candidate.replay_name,
            symbol=candidate.symbol,
            exchange=candidate.exchange,
            source=candidate.source.value,
            status=candidate.status.value,
            decision=candidate.decision.value,
            validity_status=candidate.validity.status.value,
            historical_input_id=(
                str(candidate.historical_input_id)
                if candidate.historical_input_id is not None
                else None
            ),
            timeframe=candidate.timeframe.value if candidate.timeframe is not None else None,
            validation_review_id=(
                str(candidate.validation_review_id)
                if candidate.validation_review_id is not None
                else None
            ),
            paper_rehearsal_id=(
                str(candidate.paper_rehearsal_id)
                if candidate.paper_rehearsal_id is not None
                else None
            ),
            reason_code=candidate.reason_code.value if candidate.reason_code is not None else None,
            generated_at=candidate.freshness.generated_at.isoformat(),
            expires_at=(
                candidate.freshness.expires_at.isoformat()
                if candidate.freshness.expires_at is not None
                else None
            ),
            coverage_start_at=candidate.coverage_window.start_at.isoformat(),
            coverage_end_at=candidate.coverage_window.end_at.isoformat(),
            observed_events=candidate.coverage_window.observed_events,
            expected_events=candidate.coverage_window.expected_events,
            missing_inputs=candidate.validity.missing_inputs,
            recorder_state=recorder_state,
            metadata=candidate.metadata.copy(),
        )

    def to_payload(self) -> dict[str, object]:
        return _slots_dataclass_to_payload(self)


def build_replay_event(
    *,
    event_type: ReplayEventType,
    payload: SupportsReplayPayload,
    source: str = ReplayEventSource.REPLAY_RUNTIME.value,
    correlation_id: UUID | None = None,
    priority: Priority | None = None,
) -> Event:
    """Построить Event Bus-compatible событие для replay layer."""
    event = Event.new(
        event_type=event_type.value,
        source=source,
        payload=payload.to_payload(),
    )
    event.priority = priority or default_priority_for_replay_event(event_type)
    if correlation_id is not None:
        event.correlation_id = correlation_id
    return event


# ==================== Legacy compatibility replay events ====================
# Эти generic dataclasses не являются authoritative foundation truth Phase 20.
# Они оставлены только как compatibility contour для existing legacy tests/code.


class EventType(Enum):
    """Types of events in the backtest system."""

    TICK = "tick"
    ORDER = "order"
    TRADE = "trade"
    POSITION_UPDATE = "position_update"
    RISK_CHECK = "risk_check"
    BALANCE_UPDATE = "balance_update"


@dataclass
class TickEvent:
    """
    Represents a single market tick (price update).

    This is the fundamental unit of data for replay engine.
    Tick-by-tick replay allows precise simulation of order execution.
    """

    timestamp: datetime
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    bid_size: float = 0.0
    ask_size: float = 0.0
    exchange: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        return self.ask - self.bid

    @property
    def mid(self) -> float:
        """Calculate mid price."""
        return (self.bid + self.ask) / 2

    @property
    def event_type(self) -> EventType:
        return EventType.TICK


@dataclass
class OrderEvent:
    """
    Represents an order submission, modification, or cancellation.
    """

    timestamp: datetime
    order_id: str
    symbol: str
    side: str  # "buy" or "sell"
    order_type: str  # "market", "limit", "stop", "stop_limit"
    quantity: float
    price: float | None = None  # None for market orders
    status: str = "pending"  # pending, filled, partial, cancelled, rejected
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> EventType:
        return EventType.ORDER


@dataclass
class TradeEvent:
    """
    Represents a trade execution (filled order).
    """

    timestamp: datetime
    trade_id: str
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    commission: float = 0.0
    commission_asset: str = "USDT"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_value(self) -> float:
        """Calculate total trade value."""
        return self.quantity * self.price

    @property
    def event_type(self) -> EventType:
        return EventType.TRADE


@dataclass
class PositionUpdateEvent:
    """
    Represents a position state change.
    """

    timestamp: datetime
    symbol: str
    position_size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> EventType:
        return EventType.POSITION_UPDATE


@dataclass
class BalanceUpdateEvent:
    """
    Represents account balance change.
    """

    timestamp: datetime
    asset: str
    balance_before: float
    balance_after: float
    reason: str  # "trade", "deposit", "withdrawal", "fee", "pnl"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def delta(self) -> float:
        return self.balance_after - self.balance_before

    @property
    def event_type(self) -> EventType:
        return EventType.BALANCE_UPDATE


__all__ = [
    "BalanceUpdateEvent",
    "EventType",
    "HistoricalInputPayload",
    "OrderEvent",
    "PositionUpdateEvent",
    "ReplayCandidatePayload",
    "ReplayEventSource",
    "ReplayEventType",
    "SupportsReplayPayload",
    "TickEvent",
    "TradeEvent",
    "build_replay_event",
    "default_priority_for_replay_event",
]
