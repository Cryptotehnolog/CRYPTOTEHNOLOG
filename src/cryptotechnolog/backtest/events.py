# ==================== CRYPTOTEHNOLOG Backtest Events ====================
# Core event types for replay engine

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


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
    metadata: dict[str, Any] = field(default_factory=dict)  # type: ignore[assignment]

    @property
    def spread(self) -> float:  # type: ignore[return-value]
        """Calculate bid-ask spread."""
        return self.ask - self.bid

    @property
    def mid(self) -> float:  # type: ignore[return-value]
        """Calculate mid price."""
        return (self.bid + self.ask) / 2

    @property
    def event_type(self) -> EventType:  # type: ignore[return-value]
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
    metadata: dict[str, Any] = field(default_factory=dict)  # type: ignore[assignment]

    @property
    def event_type(self) -> EventType:  # type: ignore[return-value]
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
    metadata: dict[str, Any] = field(default_factory=dict)  # type: ignore[assignment]

    @property
    def total_value(self) -> float:  # type: ignore[return-value]
        """Calculate total trade value."""
        return self.quantity * self.price

    @property
    def event_type(self) -> EventType:  # type: ignore[return-value]
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
    metadata: dict[str, Any] = field(default_factory=dict)  # type: ignore[assignment]

    @property
    def event_type(self) -> EventType:  # type: ignore[return-value]
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
    metadata: dict[str, Any] = field(default_factory=dict)  # type: ignore[assignment]

    @property
    def delta(self) -> float:  # type: ignore[return-value]
        return self.balance_after - self.balance_before

    @property
    def event_type(self) -> EventType:  # type: ignore[return-value]
        return EventType.BALANCE_UPDATE
