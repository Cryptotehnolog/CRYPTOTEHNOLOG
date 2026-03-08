# ==================== Tests for backtest/recorder.py ====================

from datetime import datetime
from pathlib import Path
import tempfile

import pandas as pd

from cryptotechnolog.backtest.events import (
    BalanceUpdateEvent,
    OrderEvent,
    PositionUpdateEvent,
    TickEvent,
    TradeEvent,
)
from cryptotechnolog.backtest.recorder import (
    BALANCE_STOP_THRESHOLD,
    SPREAD_THRESHOLD,
    EventRecorder,
)


class TestRecorderConstants:
    """Tests for recorder constants."""

    def test_spread_threshold_value(self):
        """Test SPREAD_THRESHOLD has correct value."""
        assert SPREAD_THRESHOLD == 10

    def test_balance_stop_threshold_value(self):
        """Test BALANCE_STOP_THRESHOLD has correct value."""
        assert BALANCE_STOP_THRESHOLD == 9000


class TestEventRecorder:
    """Tests for EventRecorder class."""

    def test_init_without_output_dir(self):
        """Test initialization without output directory."""
        recorder = EventRecorder()

        assert recorder.output_dir is None
        assert recorder.events == []
        assert recorder.ticks == []
        assert recorder.orders == []
        assert recorder.trades == []

    def test_init_with_output_dir(self):
        """Test initialization with output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = EventRecorder(output_dir=tmpdir)

            assert recorder.output_dir is not None
            assert recorder.output_dir.exists()

    def test_init_with_string_path(self):
        """Test initialization with string path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = EventRecorder(output_dir=tmpdir)

            assert isinstance(recorder.output_dir, Path)

    def test_record_tick(self):
        """Test recording a tick event."""
        recorder = EventRecorder()

        tick = TickEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            symbol="BTCUSDT",
            bid=42000.0,
            ask=42010.0,
            last=42005.0,
            volume=1.0,
        )

        recorder.record_tick(tick)

        assert len(recorder.ticks) == 1
        assert len(recorder.events) == 1
        assert recorder.ticks[0]["symbol"] == "BTCUSDT"
        assert recorder.ticks[0]["bid"] == 42000.0

    def test_record_tick_calculates_spread_and_mid(self):
        """Test tick recording includes spread and mid."""
        recorder = EventRecorder()

        tick = TickEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="ETHUSDT",
            bid=2000.0,
            ask=2010.0,
            last=2005.0,
            volume=0.5,
        )

        recorder.record_tick(tick)

        assert recorder.ticks[0]["spread"] == 10.0
        assert recorder.ticks[0]["mid"] == 2005.0

    def test_record_order(self):
        """Test recording an order event."""
        recorder = EventRecorder()

        order = OrderEvent(
            timestamp=datetime(2024, 1, 1),
            order_id="order_001",
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            quantity=0.1,
            price=42000.0,
            status="filled",
            filled_quantity=0.1,
            average_fill_price=42000.0,
        )

        recorder.record_order(order)

        assert len(recorder.orders) == 1
        assert len(recorder.events) == 1
        assert recorder.orders[0]["order_id"] == "order_001"
        assert recorder.orders[0]["side"] == "buy"

    def test_record_trade(self):
        """Test recording a trade event."""
        recorder = EventRecorder()

        trade = TradeEvent(
            timestamp=datetime(2024, 1, 1),
            trade_id="trade_001",
            order_id="order_001",
            symbol="BTCUSDT",
            side="buy",
            quantity=0.1,
            price=42000.0,
            commission=4.2,
        )

        recorder.record_trade(trade)

        assert len(recorder.trades) == 1
        assert len(recorder.events) == 1
        assert recorder.trades[0]["trade_id"] == "trade_001"
        assert recorder.trades[0]["commission"] == 4.2

    def test_record_position_update(self):
        """Test recording position update."""
        recorder = EventRecorder()

        update = PositionUpdateEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            position_size=0.5,
            entry_price=41000.0,
            current_price=42000.0,
            unrealized_pnl=500.0,
        )

        recorder.record_position_update(update)

        assert len(recorder.position_updates) == 1
        assert recorder.position_updates[0]["position_size"] == 0.5

    def test_record_balance_update(self):
        """Test recording balance update."""
        recorder = EventRecorder()

        update = BalanceUpdateEvent(
            timestamp=datetime(2024, 1, 1),
            asset="USDT",
            balance_before=10000.0,
            balance_after=9950.0,
            reason="trade",
        )

        recorder.record_balance_update(update)

        assert len(recorder.balance_updates) == 1
        assert recorder.balance_updates[0]["delta"] == -50.0

    def test_to_dataframe_empty(self):
        """Test converting empty recorder to DataFrame."""
        recorder = EventRecorder()

        df = recorder.to_dataframe()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_to_dataframe_with_events(self):
        """Test converting events to DataFrame."""
        recorder = EventRecorder()

        tick = TickEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            bid=42000.0,
            ask=42010.0,
            last=42005.0,
            volume=1.0,
        )
        recorder.record_tick(tick)

        df = recorder.to_dataframe()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "timestamp" in df.columns

    def test_ticks_to_dataframe(self):
        """Test converting ticks to DataFrame."""
        recorder = EventRecorder()

        tick = TickEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            bid=42000.0,
            ask=42010.0,
            last=42005.0,
            volume=1.0,
        )
        recorder.record_tick(tick)

        df = recorder.ticks_to_dataframe()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1

    def test_trades_to_dataframe(self):
        """Test converting trades to DataFrame."""
        recorder = EventRecorder()

        trade = TradeEvent(
            timestamp=datetime(2024, 1, 1),
            trade_id="trade_001",
            order_id="order_001",
            symbol="BTCUSDT",
            side="buy",
            quantity=0.1,
            price=42000.0,
        )
        recorder.record_trade(trade)

        df = recorder.trades_to_dataframe()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1

    def test_save_without_output_dir(self):
        """Test save returns None without output directory."""
        recorder = EventRecorder()

        result = recorder.save()

        assert result is None

    def test_save_with_output_dir(self):
        """Test saving events to JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = EventRecorder(output_dir=tmpdir)

            tick = TickEvent(
                timestamp=datetime(2024, 1, 1),
                symbol="BTCUSDT",
                bid=42000.0,
                ask=42010.0,
                last=42005.0,
                volume=1.0,
            )
            recorder.record_tick(tick)

            result = recorder.save()

            assert result is not None
            assert result.exists()
            assert result.suffix == ".json"

    def test_save_with_custom_filename(self):
        """Test saving with custom filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = EventRecorder(output_dir=tmpdir)

            tick = TickEvent(
                timestamp=datetime(2024, 1, 1),
                symbol="BTCUSDT",
                bid=42000.0,
                ask=42010.0,
                last=42005.0,
                volume=1.0,
            )
            recorder.record_tick(tick)

            result = recorder.save(filename="custom.json")

            assert result is not None
            assert result.name == "custom.json"

    def test_save_csv_without_output_dir(self):
        """Test save_csv returns None without output directory."""
        recorder = EventRecorder()

        result = recorder.save_csv()

        assert result is None

    def test_save_csv_with_output_dir(self):
        """Test saving events to CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = EventRecorder(output_dir=tmpdir)

            tick = TickEvent(
                timestamp=datetime(2024, 1, 1),
                symbol="BTCUSDT",
                bid=42000.0,
                ask=42010.0,
                last=42005.0,
                volume=1.0,
            )
            recorder.record_tick(tick)

            result = recorder.save_csv()

            assert result is not None
            assert result.exists()
            assert result.suffix == ".csv"

    def test_get_summary_empty(self):
        """Test get_summary with no events."""
        recorder = EventRecorder()

        summary = recorder.get_summary()

        assert summary["total_events"] == 0
        assert summary["ticks"] == 0
        assert summary["start_time"] is None
        assert summary["end_time"] is None

    def test_get_summary_with_events(self):
        """Test get_summary with events."""
        recorder = EventRecorder()

        tick = TickEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            bid=42000.0,
            ask=42010.0,
            last=42005.0,
            volume=1.0,
        )
        recorder.record_tick(tick)

        summary = recorder.get_summary()

        assert summary["total_events"] == 1
        assert summary["ticks"] == 1

    def test_clear(self):
        """Test clearing all events."""
        recorder = EventRecorder()

        tick = TickEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            bid=42000.0,
            ask=42010.0,
            last=42005.0,
            volume=1.0,
        )
        recorder.record_tick(tick)

        recorder.clear()

        assert len(recorder.events) == 0
        assert len(recorder.ticks) == 0
