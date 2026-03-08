# ==================== Tests for backtest/events.py ====================

from datetime import datetime

from cryptotechnolog.backtest.events import (
    BalanceUpdateEvent,
    EventType,
    OrderEvent,
    PositionUpdateEvent,
    TickEvent,
    TradeEvent,
)


class TestEventType:
    """Tests for EventType enum."""

    def test_event_type_values(self):
        """Test EventType enum values."""
        assert EventType.TICK.value == "tick"
        assert EventType.ORDER.value == "order"
        assert EventType.TRADE.value == "trade"
        assert EventType.POSITION_UPDATE.value == "position_update"
        assert EventType.RISK_CHECK.value == "risk_check"
        assert EventType.BALANCE_UPDATE.value == "balance_update"


class TestTickEvent:
    """Tests for TickEvent dataclass."""

    def test_tick_creation(self):
        """Test creating a basic tick event."""
        tick = TickEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            bid=42000.0,
            ask=42010.0,
            last=42005.0,
            volume=1.0,
        )

        assert tick.symbol == "BTCUSDT"
        assert tick.bid == 42000.0
        assert tick.ask == 42010.0

    def test_tick_spread_property(self):
        """Test tick spread calculation."""
        tick = TickEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            bid=42000.0,
            ask=42010.0,
            last=42005.0,
            volume=1.0,
        )

        assert tick.spread == 10.0

    def test_tick_mid_property(self):
        """Test tick mid price calculation."""
        tick = TickEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            bid=42000.0,
            ask=42010.0,
            last=42005.0,
            volume=1.0,
        )

        assert tick.mid == 42005.0

    def test_tick_event_type_property(self):
        """Test tick event_type property."""
        tick = TickEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            bid=42000.0,
            ask=42010.0,
            last=42005.0,
            volume=1.0,
        )

        assert tick.event_type == EventType.TICK

    def test_tick_default_values(self):
        """Test tick default values."""
        tick = TickEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            bid=42000.0,
            ask=42010.0,
            last=42005.0,
            volume=1.0,
        )

        assert tick.bid_size == 0.0
        assert tick.ask_size == 0.0
        assert tick.exchange == "unknown"
        assert tick.metadata == {}

    def test_tick_custom_exchange(self):
        """Test tick with custom exchange."""
        tick = TickEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            bid=42000.0,
            ask=42010.0,
            last=42005.0,
            volume=1.0,
            exchange="binance",
        )

        assert tick.exchange == "binance"

    def test_tick_with_metadata(self):
        """Test tick with metadata."""
        tick = TickEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            bid=42000.0,
            ask=42010.0,
            last=42005.0,
            volume=1.0,
            metadata={"source": "test"},
        )

        assert tick.metadata["source"] == "test"


class TestOrderEvent:
    """Tests for OrderEvent dataclass."""

    def test_order_creation(self):
        """Test creating an order event."""
        order = OrderEvent(
            timestamp=datetime(2024, 1, 1),
            order_id="order_001",
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            quantity=0.1,
            price=42000.0,
        )

        assert order.order_id == "order_001"
        assert order.side == "buy"
        assert order.status == "pending"

    def test_order_event_type(self):
        """Test order event_type property."""
        order = OrderEvent(
            timestamp=datetime(2024, 1, 1),
            order_id="order_001",
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            quantity=0.1,
            price=42000.0,
        )

        assert order.event_type == EventType.ORDER

    def test_order_default_values(self):
        """Test order default values."""
        order = OrderEvent(
            timestamp=datetime(2024, 1, 1),
            order_id="order_001",
            symbol="BTCUSDT",
            side="buy",
            order_type="market",
            quantity=0.1,
            price=None,
        )

        assert order.status == "pending"
        assert order.filled_quantity == 0.0
        assert order.average_fill_price is None
        assert order.metadata == {}


class TestTradeEvent:
    """Tests for TradeEvent dataclass."""

    def test_trade_creation(self):
        """Test creating a trade event."""
        trade = TradeEvent(
            timestamp=datetime(2024, 1, 1),
            trade_id="trade_001",
            order_id="order_001",
            symbol="BTCUSDT",
            side="buy",
            quantity=0.1,
            price=42000.0,
        )

        assert trade.trade_id == "trade_001"
        assert trade.side == "buy"
        assert trade.commission == 0.0

    def test_trade_total_value(self):
        """Test trade total_value calculation."""
        trade = TradeEvent(
            timestamp=datetime(2024, 1, 1),
            trade_id="trade_001",
            order_id="order_001",
            symbol="BTCUSDT",
            side="buy",
            quantity=0.1,
            price=42000.0,
        )

        assert trade.total_value == 4200.0

    def test_trade_event_type(self):
        """Test trade event_type property."""
        trade = TradeEvent(
            timestamp=datetime(2024, 1, 1),
            trade_id="trade_001",
            order_id="order_001",
            symbol="BTCUSDT",
            side="buy",
            quantity=0.1,
            price=42000.0,
        )

        assert trade.event_type == EventType.TRADE

    def test_trade_default_commission_asset(self):
        """Test trade default commission asset."""
        trade = TradeEvent(
            timestamp=datetime(2024, 1, 1),
            trade_id="trade_001",
            order_id="order_001",
            symbol="BTCUSDT",
            side="buy",
            quantity=0.1,
            price=42000.0,
        )

        assert trade.commission_asset == "USDT"


class TestPositionUpdateEvent:
    """Tests for PositionUpdateEvent dataclass."""

    def test_position_update_creation(self):
        """Test creating a position update event."""
        update = PositionUpdateEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            position_size=0.5,
            entry_price=41000.0,
            current_price=42000.0,
            unrealized_pnl=500.0,
        )

        assert update.position_size == 0.5
        assert update.realized_pnl == 0.0

    def test_position_update_event_type(self):
        """Test position update event_type property."""
        update = PositionUpdateEvent(
            timestamp=datetime(2024, 1, 1),
            symbol="BTCUSDT",
            position_size=0.5,
            entry_price=41000.0,
            current_price=42000.0,
            unrealized_pnl=500.0,
        )

        assert update.event_type == EventType.POSITION_UPDATE


class TestBalanceUpdateEvent:
    """Tests for BalanceUpdateEvent dataclass."""

    def test_balance_update_creation(self):
        """Test creating a balance update event."""
        update = BalanceUpdateEvent(
            timestamp=datetime(2024, 1, 1),
            asset="USDT",
            balance_before=10000.0,
            balance_after=9950.0,
            reason="trade",
        )

        assert update.balance_before == 10000.0
        assert update.balance_after == 9950.0

    def test_balance_update_delta(self):
        """Test balance update delta calculation."""
        update = BalanceUpdateEvent(
            timestamp=datetime(2024, 1, 1),
            asset="USDT",
            balance_before=10000.0,
            balance_after=9950.0,
            reason="trade",
        )

        assert update.delta == -50.0

    def test_balance_update_event_type(self):
        """Test balance update event_type property."""
        update = BalanceUpdateEvent(
            timestamp=datetime(2024, 1, 1),
            asset="USDT",
            balance_before=10000.0,
            balance_after=9950.0,
            reason="trade",
        )

        assert update.event_type == EventType.BALANCE_UPDATE
