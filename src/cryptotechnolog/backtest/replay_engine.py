# ==================== CRYPTOTEHNOLOG Replay Engine ====================
# Tick-by-tick historical data replay for backtesting

from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

from cryptotechnolog.backtest import (
    BalanceUpdateEvent,
    EventRecorder,
    OrderEvent,
    PositionUpdateEvent,
    TickEvent,
    TradeEvent,
)


@dataclass
class ReplayConfig:
    """Configuration for replay engine."""

    # Data source
    data_source: str = "csv"  # "csv", "parquet", "dataframe"
    data_path: str | Path = ""

    # Replay settings
    start_time: datetime | None = None
    end_time: datetime | None = None
    speed: float = 1.0  # 1.0 = real-time, 0.0 = unlimited, >1 = faster

    # Simulation settings
    initial_balance: float = 10_000.0
    commission_rate: float = 0.001  # 0.1%

    # Output settings
    record_events: bool = True
    output_dir: str | Path | None = None

    # Callbacks
    on_tick: Callable[[TickEvent], None] | None = None
    on_order: Callable[[OrderEvent], None] | None = None
    on_trade: Callable[[TradeEvent], None] | None = None
    on_position_update: Callable[[PositionUpdateEvent], None] | None = None
    on_balance_update: Callable[[BalanceUpdateEvent], None] | None = None


class ReplayEngine:
    """
    Replay Engine for tick-by-tick historical simulation.

    Features:
    - Load historical data from CSV/Parquet
    - Precise tick-by-tick replay
    - Event recording for analysis
    - Callbacks for strategy execution
    - State snapshots for debugging

    Usage:
        config = ReplayConfig(data_path="ticks.csv", on_tick=my_strategy)
        engine = ReplayEngine(config)
        results = engine.run()
    """

    def __init__(self, config: ReplayConfig):
        """
        Initialize replay engine.

        Args:
            config: Replay configuration
        """
        self.config = config
        self.recorder = EventRecorder(config.output_dir) if config.record_events else None

        # State
        self.current_tick: TickEvent | None = None
        self.current_time: datetime | None = None
        self.ticks_processed: int = 0

        # Account state
        self.balance: float = config.initial_balance
        self.positions: dict[str, float] = {}  # symbol -> size
        self.orders: dict[str, OrderEvent] = {}  # order_id -> order

        # Data
        self._data: pd.DataFrame | None = None
        self._data_iterator: Iterator[tuple[Any, pd.Series]] | None = None

    def load_csv(self, path: str | Path) -> "ReplayEngine":
        """Load tick data from CSV file."""
        path = Path(path)

        # Required columns
        required_cols = ["timestamp", "symbol", "bid", "ask", "last", "volume"]

        df = pd.read_csv(path, parse_dates=["timestamp"])

        # Validate columns
        missing = set(required_cols) - set(df.columns)
        if missing:
            msg = f"Missing required columns: {missing}"
            raise ValueError(msg)

        # Filter by time range
        if self.config.start_time:
            df = df[df["timestamp"] >= self.config.start_time]
        if self.config.end_time:
            df = df[df["timestamp"] <= self.config.end_time]

        df = df.sort_values("timestamp").reset_index(drop=True)

        self._data = df
        self._data_iterator = df.iterrows()

        return self

    def load_parquet(self, path: str | Path) -> "ReplayEngine":
        """Load tick data from Parquet file."""
        path = Path(path)

        df = pd.read_parquet(path)

        # Ensure timestamp column
        if "timestamp" not in df.columns:
            msg = "Parquet must have 'timestamp' column"
            raise ValueError(msg)

        # Filter by time range
        if self.config.start_time:
            df = df[df["timestamp"] >= self.config.start_time]
        if self.config.end_time:
            df = df[df["timestamp"] <= self.config.end_time]

        df = df.sort_values("timestamp").reset_index(drop=True)

        self._data = df
        self._data_iterator = df.iterrows()

        return self

    def load_dataframe(self, df: pd.DataFrame) -> "ReplayEngine":
        """Load tick data from DataFrame."""
        # Ensure required columns
        required_cols = ["timestamp", "symbol", "bid", "ask", "last", "volume"]
        missing = set(required_cols) - set(df.columns)
        if missing:
            msg = f"Missing required columns: {missing}"
            raise ValueError(msg)

        # Filter by time range
        if self.config.start_time:
            df = df[df["timestamp"] >= self.config.start_time]
        if self.config.end_time:
            df = df[df["timestamp"] <= self.config.end_time]

        df = df.sort_values("timestamp").reset_index(drop=True)

        self._data = df
        self._data_iterator = df.iterrows()

        return self

    def _create_tick_event(self, row: pd.Series) -> TickEvent:
        """Create TickEvent from DataFrame row."""
        ts_raw = row["timestamp"]
        ts = datetime.fromisoformat(str(ts_raw)) if not isinstance(ts_raw, datetime) else ts_raw
        return TickEvent(
            timestamp=ts,
            symbol=str(row["symbol"]),
            bid=float(row["bid"]),
            ask=float(row["ask"]),
            last=float(row["last"]),
            volume=float(row["volume"]),
            bid_size=float(row.get("bid_size", 0.0)),
            ask_size=float(row.get("ask_size", 0.0)),
            exchange=str(row.get("exchange", "unknown")),
            metadata=dict(row) if hasattr(row, "to_dict") else {},
        )

    def tick_iterator(self) -> Generator[TickEvent, None, None]:
        """
        Iterate over ticks one by one.

        Yields:
            TickEvent for each tick in the dataset
        """
        if self._data_iterator is None:
            msg = "No data loaded. Call load_csv(), load_parquet(), or load_dataframe() first."
            raise RuntimeError(msg)

        for _idx, row in self._data_iterator:
            tick = self._create_tick_event(row)
            self.current_tick = tick
            self.current_time = tick.timestamp
            self.ticks_processed += 1

            yield tick

    def run(self) -> dict[str, Any]:
        """
        Run the full replay.

        Returns:
            Dictionary with results and statistics
        """
        if self._data_iterator is None:
            msg = "No data loaded. Call load_csv(), load_parquet(), or load_dataframe() first."
            raise RuntimeError(msg)

        # Reset state
        self.balance = self.config.initial_balance
        self.positions.clear()
        self.orders.clear()
        self.ticks_processed = 0

        start_time = datetime.now()

        # Process each tick
        for tick in self.tick_iterator():
            # Record tick
            if self.recorder:
                self.recorder.record_tick(tick)

            # Call on_tick callback
            if self.config.on_tick:
                self.config.on_tick(tick)

        end_time = datetime.now()

        # Build results
        results: dict[str, Any] = {
            "ticks_processed": self.ticks_processed,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "final_balance": self.balance,
            "final_positions": dict(self.positions),
            "total_orders": len(self.orders),
            "summary": self.recorder.get_summary() if self.recorder else {},
        }

        # Save events if configured
        if self.recorder and self.config.output_dir:
            self.recorder.save()

        return results

    def run_until(
        self,
        condition: Callable[[TickEvent, dict[str, Any]], bool],
        max_ticks: int | None = None,
    ) -> dict[str, Any]:
        """
        Run replay until condition is met.

        Args:
            condition: Function that returns True to stop
            max_ticks: Maximum ticks to process

        Returns:
            Results dictionary
        """
        if self._data_iterator is None:
            msg = "No data loaded."
            raise RuntimeError(msg)

        # Reset state
        self.balance = self.config.initial_balance
        self.positions.clear()
        self.orders.clear()
        self.ticks_processed = 0

        state: dict[str, Any] = {
            "balance": self.balance,
            "positions": self.positions,
            "orders": self.orders,
        }

        for tick in self.tick_iterator():
            # Record
            if self.recorder:
                self.recorder.record_tick(tick)

            # Callback
            if self.config.on_tick:
                self.config.on_tick(tick)

            # Update state
            state["balance"] = self.balance
            state["positions"] = dict(self.positions)

            # Check stop condition
            if condition(tick, state):
                break

            # Check max ticks
            if max_ticks and self.ticks_processed >= max_ticks:
                break

        return {
            "ticks_processed": self.ticks_processed,
            "final_balance": self.balance,
            "final_positions": dict(self.positions),
            "summary": self.recorder.get_summary() if self.recorder else {},
        }

    def get_state_snapshot(self) -> dict[str, Any]:
        """
        Get current state snapshot for debugging.

        Returns:
            Dictionary with current state
        """
        return {
            "timestamp": self.current_time.isoformat() if self.current_time else None,
            "tick": (
                {
                    "symbol": self.current_tick.symbol if self.current_tick else None,
                    "bid": self.current_tick.bid if self.current_tick else None,
                    "ask": self.current_tick.ask if self.current_tick else None,
                    "volume": self.current_tick.volume if self.current_tick else None,
                }
                if self.current_tick
                else None
            ),
            "balance": self.balance,
            "positions": dict(self.positions),
            "orders_count": len(self.orders),
            "ticks_processed": self.ticks_processed,
        }

    def save_state_snapshot(self, path: str | Path) -> None:
        """Save current state snapshot to JSON for debugging."""
        path = Path(path)
        snapshot = self.get_state_snapshot()

        with path.open("w") as f:
            json.dump(snapshot, f, indent=2, default=str)

    # ==================== Order Execution Helpers ====================

    def submit_market_order(
        self,
        symbol: str,
        side: str,  # "buy" or "sell"
        quantity: float,
    ) -> OrderEvent:
        """Submit a market order."""
        order = OrderEvent(
            timestamp=self.current_time or datetime.now(),
            order_id=f"ord_{self.ticks_processed}_{len(self.orders)}",
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=quantity,
            price=None,
            status="filled",
            filled_quantity=quantity,
            average_fill_price=self.current_tick.last if self.current_tick else 0.0,
        )

        self.orders[order.order_id] = order

        # Update balance
        fill_price = order.average_fill_price if order.average_fill_price is not None else 0.0
        cost: float = quantity * fill_price
        commission: float = cost * self.config.commission_rate

        if side == "buy":
            self.balance -= cost + commission
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
        else:
            self.balance += cost - commission
            self.positions[symbol] = self.positions.get(symbol, 0) - quantity

        # Record
        if self.recorder:
            self.recorder.record_order(order)

        if self.config.on_order:
            self.config.on_order(order)

        return order

    def get_position(self, symbol: str) -> float:
        """Get current position size for symbol."""
        return self.positions.get(symbol, 0.0)

    def get_unrealized_pnl(self, symbol: str) -> float:
        """Calculate unrealized PnL for position."""
        position = self.positions.get(symbol, 0.0)
        if position == 0 or not self.current_tick:
            return 0.0

        tick = self.current_tick
        last_price = tick.last if tick.last is not None else 0.0
        bid_price = tick.bid if tick.bid is not None else 0.0
        ask_price = tick.ask if tick.ask is not None else 0.0

        if position > 0:  # Long
            return position * (last_price - bid_price)
        # Short
        return -position * (ask_price - last_price)
