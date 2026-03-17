"""Unit tests for cryptotechnolog.backtest.replay_engine module."""

from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

from cryptotechnolog.backtest.events import OrderEvent, TickEvent
from cryptotechnolog.backtest.replay_engine import ReplayConfig, ReplayEngine


class TestReplayConfig:
    """Tests for ReplayConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = ReplayConfig()
        assert config.data_source == "csv"
        assert config.initial_balance == 10_000.0
        assert config.commission_rate == 0.001
        assert config.speed == 1.0

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = ReplayConfig(
            data_source="parquet",
            data_path="/path/to/data",
            initial_balance=50_000.0,
            commission_rate=0.002,
        )
        assert config.data_source == "parquet"
        assert config.data_path == "/path/to/data"
        assert config.initial_balance == 50_000.0
        assert config.commission_rate == 0.002


class TestReplayEngine:
    """Tests for ReplayEngine class."""

    @pytest.fixture
    def sample_csv_data(self) -> str:
        """Sample CSV data for testing."""
        return """timestamp,symbol,bid,ask,last,volume
2024-01-01 10:00:00,BTCUSDT,50000.0,50001.0,50000.5,100.0
2024-01-01 10:00:01,BTCUSDT,50001.0,50002.0,50001.5,150.0
2024-01-01 10:00:02,BTCUSDT,50002.0,50003.0,50002.5,200.0
"""

    @pytest.fixture
    def sample_dataframe(self, sample_csv_data: str) -> pd.DataFrame:
        """Sample DataFrame for testing."""
        df = pd.read_csv(StringIO(sample_csv_data), parse_dates=["timestamp"])
        return df

    def test_init(self) -> None:
        """Test engine initialization."""
        config = ReplayConfig()
        engine = ReplayEngine(config)
        assert engine.config is config
        assert engine.balance == config.initial_balance
        assert engine.ticks_processed == 0

    def test_init_without_recorder(self) -> None:
        """Test initialization without event recorder."""
        config = ReplayConfig(record_events=False)
        engine = ReplayEngine(config)
        assert engine.recorder is None

    def test_load_csv(self, tmp_path: Path, sample_csv_data: str) -> None:
        """Test loading data from CSV."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(sample_csv_data)

        config = ReplayConfig()
        engine = ReplayEngine(config)
        engine.load_csv(csv_file)

        assert engine._data is not None
        assert len(engine._data) == 3

    def test_load_csv_missing_columns(self, tmp_path: Path) -> None:
        """Test loading CSV with missing columns."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("timestamp,symbol\n2024-01-01 10:00:00,BTCUSDT")

        config = ReplayConfig()
        engine = ReplayEngine(config)

        with pytest.raises(ValueError, match="Missing required columns"):
            engine.load_csv(csv_file)

    def test_load_csv_with_time_filter(self, tmp_path: Path, sample_csv_data: str) -> None:
        """Test loading CSV with time filter."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(sample_csv_data)

        config = ReplayConfig(
            start_time=datetime(2024, 1, 1, 10, 0, 1),
            end_time=datetime(2024, 1, 1, 10, 0, 2),
        )
        engine = ReplayEngine(config)
        engine.load_csv(csv_file)

        assert len(engine._data) == 2

    def test_load_parquet(self, tmp_path: Path, sample_dataframe: pd.DataFrame) -> None:
        """Test loading data from Parquet."""
        parquet_file = tmp_path / "test.parquet"
        sample_dataframe.to_parquet(parquet_file, index=False)

        config = ReplayConfig()
        engine = ReplayEngine(config)
        engine.load_parquet(parquet_file)

        assert engine._data is not None

    def test_load_parquet_missing_timestamp(self, tmp_path: Path) -> None:
        """Test loading Parquet without timestamp column."""
        df = pd.DataFrame({"symbol": ["BTCUSDT"], "bid": [50000.0]})
        parquet_file = tmp_path / "test.parquet"
        df.to_parquet(parquet_file, index=False)

        config = ReplayConfig()
        engine = ReplayEngine(config)

        with pytest.raises(ValueError, match="Parquet must have 'timestamp' column"):
            engine.load_parquet(parquet_file)

    def test_load_dataframe(self, sample_dataframe: pd.DataFrame) -> None:
        """Test loading data from DataFrame."""
        config = ReplayConfig()
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)

        assert engine._data is not None
        assert len(engine._data) == 3

    def test_load_dataframe_missing_columns(self) -> None:
        """Test loading DataFrame with missing columns."""
        df = pd.DataFrame({"symbol": ["BTCUSDT"], "bid": [50000.0]})

        config = ReplayConfig()
        engine = ReplayEngine(config)

        with pytest.raises(ValueError, match="Missing required columns"):
            engine.load_dataframe(df)

    def test_create_tick_event(self, sample_dataframe: pd.DataFrame) -> None:
        """Test creating tick event from DataFrame row."""
        config = ReplayConfig()
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)

        row = sample_dataframe.iloc[0]
        tick = engine._create_tick_event(row)

        assert isinstance(tick, TickEvent)
        assert tick.symbol == "BTCUSDT"
        assert tick.bid == 50000.0
        assert tick.ask == 50001.0

    def test_tick_iterator(self, sample_dataframe: pd.DataFrame) -> None:
        """Test tick iterator."""
        config = ReplayConfig()
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)

        ticks = list(engine.tick_iterator())
        assert len(ticks) == 3
        assert isinstance(ticks[0], TickEvent)

    def test_tick_iterator_no_data(self) -> None:
        """Test tick iterator with no data loaded."""
        config = ReplayConfig()
        engine = ReplayEngine(config)

        with pytest.raises(RuntimeError, match="No data loaded"):
            list(engine.tick_iterator())

    def test_run(self, sample_dataframe: pd.DataFrame) -> None:
        """Test running the replay engine."""
        config = ReplayConfig(record_events=False)
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)

        results = engine.run()

        assert results["ticks_processed"] == 3
        assert results["final_balance"] == config.initial_balance

    def test_run_with_callback(self, sample_dataframe: pd.DataFrame) -> None:
        """Test running with on_tick callback."""
        callback_ticks = []

        def on_tick(tick: TickEvent) -> None:
            callback_ticks.append(tick)

        config = ReplayConfig(on_tick=on_tick, record_events=False)
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)

        engine.run()

        assert len(callback_ticks) == 3

    def test_run_no_data(self) -> None:
        """Test running without data loaded."""
        config = ReplayConfig()
        engine = ReplayEngine(config)

        with pytest.raises(RuntimeError, match="No data loaded"):
            engine.run()

    def test_run_until(self, sample_dataframe: pd.DataFrame) -> None:
        """Test run_until method."""
        config = ReplayConfig(record_events=False)
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)

        def stop_condition(tick: TickEvent, state: dict) -> bool:
            # Process all 3 ticks
            return False

        results = engine.run_until(stop_condition)

        # Should process all ticks since condition never met
        assert results["ticks_processed"] == 3

    def test_run_until_max_ticks(self, sample_dataframe: pd.DataFrame) -> None:
        """Test run_until with max_ticks limit."""
        config = ReplayConfig(record_events=False)
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)

        results = engine.run_until(lambda tick, state: False, max_ticks=2)

        assert results["ticks_processed"] == 2

    def test_get_state_snapshot(self, sample_dataframe: pd.DataFrame) -> None:
        """Test getting state snapshot."""
        config = ReplayConfig(record_events=False)
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)

        # Manually process exactly one tick
        tick_iter = engine.tick_iterator()
        next(tick_iter)  # Process first tick only

        snapshot = engine.get_state_snapshot()

        assert snapshot["balance"] == config.initial_balance
        assert snapshot["ticks_processed"] == 1

    def test_get_state_snapshot_no_tick(self) -> None:
        """Test getting state snapshot with no tick processed."""
        config = ReplayConfig()
        engine = ReplayEngine(config)

        snapshot = engine.get_state_snapshot()

        assert snapshot["tick"] is None
        assert snapshot["balance"] == config.initial_balance

    def test_save_state_snapshot(self, tmp_path: Path, sample_dataframe: pd.DataFrame) -> None:
        """Test saving state snapshot."""
        snapshot_file = tmp_path / "snapshot.json"

        config = ReplayConfig(record_events=False)
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)
        list(engine.tick_iterator())

        engine.save_state_snapshot(snapshot_file)

        assert snapshot_file.exists()

    def test_submit_market_order_buy(self, sample_dataframe: pd.DataFrame) -> None:
        """Test submitting buy market order."""
        config = ReplayConfig(record_events=False)
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)
        list(engine.tick_iterator())

        initial_balance = engine.balance

        order = engine.submit_market_order("BTCUSDT", "buy", 0.1)

        assert order.side == "buy"
        assert order.status == "filled"
        assert engine.balance < initial_balance
        assert engine.positions["BTCUSDT"] == 0.1

    def test_submit_market_order_sell(self, sample_dataframe: pd.DataFrame) -> None:
        """Test submitting sell market order."""
        config = ReplayConfig(record_events=False)
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)
        list(engine.tick_iterator())

        # First buy to have position
        engine.submit_market_order("BTCUSDT", "buy", 0.1)
        initial_balance = engine.balance

        # Then sell
        order = engine.submit_market_order("BTCUSDT", "sell", 0.1)

        assert order.side == "sell"
        assert engine.balance > initial_balance

    def test_submit_market_order_with_callback(self, sample_dataframe: pd.DataFrame) -> None:
        """Test submitting order with callback."""
        callback_orders = []

        def on_order(order: OrderEvent) -> None:
            callback_orders.append(order)

        config = ReplayConfig(on_order=on_order, record_events=False)
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)
        list(engine.tick_iterator())

        engine.submit_market_order("BTCUSDT", "buy", 0.1)

        assert len(callback_orders) == 1

    def test_get_position(self, sample_dataframe: pd.DataFrame) -> None:
        """Test getting position."""
        config = ReplayConfig(record_events=False)
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)
        list(engine.tick_iterator())

        # No position initially
        assert engine.get_position("BTCUSDT") == 0.0

        # Create position
        engine.submit_market_order("BTCUSDT", "buy", 0.1)
        assert engine.get_position("BTCUSDT") == 0.1

    def test_get_unrealized_pnl_no_position(self, sample_dataframe: pd.DataFrame) -> None:
        """Test unrealized PnL with no position."""
        config = ReplayConfig(record_events=False)
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)
        list(engine.tick_iterator())

        pnl = engine.get_unrealized_pnl("BTCUSDT")
        assert pnl == 0.0

    def test_get_unrealized_pnl_long(self, sample_dataframe: pd.DataFrame) -> None:
        """Test unrealized PnL for long position."""
        config = ReplayConfig(record_events=False)
        engine = ReplayEngine(config)
        engine.load_dataframe(sample_dataframe)
        list(engine.tick_iterator())

        engine.submit_market_order("BTCUSDT", "buy", 0.1)
        pnl = engine.get_unrealized_pnl("BTCUSDT")

        assert pnl >= 0.0

    def test_get_unrealized_pnl_no_tick(self) -> None:
        """Test unrealized PnL with no tick processed."""
        config = ReplayConfig()
        engine = ReplayEngine(config)

        pnl = engine.get_unrealized_pnl("BTCUSDT")
        assert pnl == 0.0
