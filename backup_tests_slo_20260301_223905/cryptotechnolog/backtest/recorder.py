# ==================== CRYPTOTEHNOLOG Event Recorder ====================
# Records all events during replay for analysis and debugging

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from cryptotechnolog.backtest.events import (
        BalanceUpdateEvent,
        OrderEvent,
        PositionUpdateEvent,
        TickEvent,
        TradeEvent,
    )


# Constants for magic values
SPREAD_THRESHOLD = 10  # Wide spread threshold for mean reversion
BALANCE_STOP_THRESHOLD = 9000  # Balance threshold for stopping backtest


class EventRecorder:
    """
    Records all events during backtest replay.

    Allows:
    - Replay analysis after simulation
    - Debug issues in production
    - Generate performance reports
    """

    def __init__(self, output_dir: str | Path | None = None):
        """
        Initialize event recorder.

        Args:
            output_dir: Directory to save recorded events.
                       If None, events are stored in memory only.
        """
        self.output_dir = Path(output_dir) if output_dir else None
        self.events: list[dict[str, Any]] = []
        self.ticks: list[dict[str, Any]] = []
        self.orders: list[dict[str, Any]] = []
        self.trades: list[dict[str, Any]] = []
        self.position_updates: list[dict[str, Any]] = []
        self.balance_updates: list[dict[str, Any]] = []

        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def record_tick(self, tick: TickEvent) -> None:
        """Record a tick event."""
        event_data: dict[str, Any] = {
            "timestamp": tick.timestamp.isoformat(),
            "symbol": tick.symbol,
            "bid": tick.bid,
            "ask": tick.ask,
            "last": tick.last,
            "volume": tick.volume,
            "spread": tick.spread,
            "mid": tick.mid,
            "exchange": tick.exchange,
        }
        self.ticks.append(event_data)
        self.events.append(event_data)

    def record_order(self, order: OrderEvent) -> None:
        """Record an order event."""
        event_data: dict[str, Any] = {
            "timestamp": order.timestamp.isoformat(),
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side,
            "order_type": order.order_type,
            "quantity": order.quantity,
            "price": order.price,
            "status": order.status,
            "filled_quantity": order.filled_quantity,
            "average_fill_price": order.average_fill_price,
        }
        self.orders.append(event_data)
        self.events.append(event_data)

    def record_trade(self, trade: TradeEvent) -> None:
        """Record a trade event."""
        event_data: dict[str, Any] = {
            "timestamp": trade.timestamp.isoformat(),
            "trade_id": trade.trade_id,
            "order_id": trade.order_id,
            "symbol": trade.symbol,
            "side": trade.side,
            "quantity": trade.quantity,
            "price": trade.price,
            "commission": trade.commission,
            "total_value": trade.total_value,
        }
        self.trades.append(event_data)
        self.events.append(event_data)

    def record_position_update(self, update: PositionUpdateEvent) -> None:
        """Record a position update event."""
        event_data: dict[str, Any] = {
            "timestamp": update.timestamp.isoformat(),
            "symbol": update.symbol,
            "position_size": update.position_size,
            "entry_price": update.entry_price,
            "current_price": update.current_price,
            "unrealized_pnl": update.unrealized_pnl,
            "realized_pnl": update.realized_pnl,
        }
        self.position_updates.append(event_data)
        self.events.append(event_data)

    def record_balance_update(self, update: BalanceUpdateEvent) -> None:
        """Record a balance update event."""
        event_data: dict[str, Any] = {
            "timestamp": update.timestamp.isoformat(),
            "asset": update.asset,
            "balance_before": update.balance_before,
            "balance_after": update.balance_after,
            "delta": update.delta,
            "reason": update.reason,
        }
        self.balance_updates.append(event_data)
        self.events.append(event_data)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert all events to a pandas DataFrame."""
        if not self.events:
            return pd.DataFrame()

        df = pd.DataFrame(self.events)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    def ticks_to_dataframe(self) -> pd.DataFrame:
        """Convert tick events to DataFrame."""
        if not self.ticks:
            return pd.DataFrame()

        df = pd.DataFrame(self.ticks)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df.sort_values("timestamp").reset_index(drop=True)

    def trades_to_dataframe(self) -> pd.DataFrame:
        """Convert trade events to DataFrame."""
        if not self.trades:
            return pd.DataFrame()

        df = pd.DataFrame(self.trades)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df.sort_values("timestamp").reset_index(drop=True)

    def save(self, filename: str | None = None) -> Path | None:
        """
        Save all events to JSON file.

        Args:
            filename: Custom filename. If None, uses timestamp-based name.

        Returns:
            Path to saved file, or None if no output directory configured.
        """
        if not self.output_dir:
            return None

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backtest_events_{timestamp}.json"

        filepath = self.output_dir / filename

        with filepath.open("w") as f:
            json.dump(self.events, f, indent=2, default=str)

        return filepath

    def save_csv(self, filename: str | None = None) -> Path | None:
        """
        Save events to CSV file.

        Args:
            filename: Custom filename. If None, uses timestamp-based name.

        Returns:
            Path to saved file, or None if no output directory configured.
        """
        if not self.output_dir:
            return None

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backtest_events_{timestamp}.csv"

        filepath = self.output_dir / filename
        df = self.to_dataframe()
        df.to_csv(filepath, index=False)

        return filepath

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics of recorded events."""
        return {
            "total_events": len(self.events),
            "ticks": len(self.ticks),
            "orders": len(self.orders),
            "trades": len(self.trades),
            "position_updates": len(self.position_updates),
            "balance_updates": len(self.balance_updates),
            "start_time": self.events[0]["timestamp"] if self.events else None,
            "end_time": self.events[-1]["timestamp"] if self.events else None,
        }

    def clear(self) -> None:
        """Clear all recorded events."""
        self.events.clear()
        self.ticks.clear()
        self.orders.clear()
        self.trades.clear()
        self.position_updates.clear()
        self.balance_updates.clear()
