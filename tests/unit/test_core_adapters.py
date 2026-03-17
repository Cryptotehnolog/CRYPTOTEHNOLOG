"""Unit tests for cryptotechnolog.core.adapters module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from cryptotechnolog.core.adapters import (
    PostgresOrderRepository,
    PostgresPositionRepository,
    PostgresRiskLimitRepository,
    StructlogAdapter,
)


class TestStructlogAdapter:
    """Tests for StructlogAdapter class."""

    def test_init_without_name(self) -> None:
        """Test initialization without name."""
        adapter = StructlogAdapter()
        assert adapter._logger is not None

    def test_init_with_name(self) -> None:
        """Test initialization with name."""
        adapter = StructlogAdapter(name="test_logger")
        assert adapter._logger is not None

    def test_debug(self) -> None:
        """Test debug log level."""
        adapter = StructlogAdapter()
        adapter.debug("test message", key="value")

    def test_info(self) -> None:
        """Test info log level."""
        adapter = StructlogAdapter()
        adapter.info("test message", key="value")

    def test_warning(self) -> None:
        """Test warning log level."""
        adapter = StructlogAdapter()
        adapter.warning("test message", key="value")

    def test_error(self) -> None:
        """Test error log level."""
        adapter = StructlogAdapter()
        adapter.error("test message", key="value")

    def test_critical(self) -> None:
        """Test critical log level."""
        adapter = StructlogAdapter()
        adapter.critical("test message", key="value")

    def test_exception(self) -> None:
        """Test exception log level."""
        adapter = StructlogAdapter()
        adapter.exception("test message", key="value")

    def test_bind(self) -> None:
        """Test bind method creates new adapter with context."""
        adapter = StructlogAdapter()
        bound = adapter.bind(user_id="123", request_id="abc")
        assert bound is not None
        assert isinstance(bound, StructlogAdapter)


class TestPostgresOrderRepository:
    """Tests for PostgresOrderRepository class."""

    @pytest.fixture
    def mock_pool(self) -> MagicMock:
        """Create mock connection pool."""
        pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        return pool

    @pytest.mark.asyncio
    async def test_save(self, mock_pool: MagicMock) -> None:
        """Test saving an order."""
        repo = PostgresOrderRepository(mock_pool)
        order = {
            "id": "order_1",
            "symbol": "BTCUSDT",
            "side": "buy",
            "quantity": 0.1,
            "price": 50000.0,
        }
        await repo.save(order)
        mock_pool.acquire.return_value.__aenter__.return_value.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_id_found(self, mock_pool: MagicMock) -> None:
        """Test finding order by ID when exists."""
        mock_conn = MagicMock()
        mock_row = {"id": "order_1", "symbol": "BTCUSDT"}
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresOrderRepository(pool)
        result = await repo.find_by_id("order_1")
        assert result == {"id": "order_1", "symbol": "BTCUSDT"}

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, mock_pool: MagicMock) -> None:
        """Test finding order by ID when not exists."""
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresOrderRepository(pool)
        result = await repo.find_by_id("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_symbol(self, mock_pool: MagicMock) -> None:
        """Test finding orders by symbol."""
        mock_conn = MagicMock()
        mock_rows = [
            {"id": "order_1", "symbol": "BTCUSDT"},
            {"id": "order_2", "symbol": "BTCUSDT"},
        ]
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresOrderRepository(pool)
        result = await repo.find_by_symbol("BTCUSDT")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_find_open_orders_with_symbol(self, mock_pool: MagicMock) -> None:
        """Test finding open orders with symbol filter."""
        mock_conn = MagicMock()
        mock_rows = [{"id": "order_1", "symbol": "BTCUSDT", "status": "open"}]
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresOrderRepository(pool)
        result = await repo.find_open_orders(symbol="BTCUSDT")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_open_orders_without_symbol(self, mock_pool: MagicMock) -> None:
        """Test finding all open orders without filter."""
        mock_conn = MagicMock()
        mock_rows = [
            {"id": "order_1", "symbol": "BTCUSDT", "status": "open"},
            {"id": "order_2", "symbol": "ETHUSDT", "status": "pending"},
        ]
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresOrderRepository(pool)
        result = await repo.find_open_orders()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_update_status(self, mock_pool: MagicMock) -> None:
        """Test updating order status."""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresOrderRepository(pool)
        result = await repo.update_status("order_1", "filled")
        assert result is True

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, mock_pool: MagicMock) -> None:
        """Test updating status of nonexistent order."""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresOrderRepository(pool)
        result = await repo.update_status("nonexistent", "filled")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete(self, mock_pool: MagicMock) -> None:
        """Test deleting an order."""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 1")

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresOrderRepository(pool)
        result = await repo.delete("order_1")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_pool: MagicMock) -> None:
        """Test deleting nonexistent order."""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 0")

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresOrderRepository(pool)
        result = await repo.delete("nonexistent")
        assert result is False


class TestPostgresPositionRepository:
    """Tests for PostgresPositionRepository class."""

    @pytest.fixture
    def mock_pool(self) -> MagicMock:
        """Create mock connection pool."""
        pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        return pool

    @pytest.mark.asyncio
    async def test_save(self, mock_pool: MagicMock) -> None:
        """Test saving a position."""
        repo = PostgresPositionRepository(mock_pool)
        position = {
            "id": "pos_1",
            "symbol": "BTCUSDT",
            "side": "long",
            "quantity": 0.1,
            "entry_price": 50000.0,
            "current_price": 51000.0,
            "pnl": 100.0,
        }
        await repo.save(position)
        mock_pool.acquire.return_value.__aenter__.return_value.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_id_found(self, mock_pool: MagicMock) -> None:
        """Test finding position by ID when exists."""
        mock_conn = MagicMock()
        mock_row = {"id": "pos_1", "symbol": "BTCUSDT"}
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresPositionRepository(pool)
        result = await repo.find_by_id("pos_1")
        assert result == {"id": "pos_1", "symbol": "BTCUSDT"}

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, mock_pool: MagicMock) -> None:
        """Test finding position by ID when not exists."""
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresPositionRepository(pool)
        result = await repo.find_by_id("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_symbol_found(self, mock_pool: MagicMock) -> None:
        """Test finding position by symbol when exists."""
        mock_conn = MagicMock()
        mock_row = {"id": "pos_1", "symbol": "BTCUSDT", "status": "open"}
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresPositionRepository(pool)
        result = await repo.find_by_symbol("BTCUSDT")
        assert result == {"id": "pos_1", "symbol": "BTCUSDT", "status": "open"}

    @pytest.mark.asyncio
    async def test_find_by_symbol_not_found(self, mock_pool: MagicMock) -> None:
        """Test finding position by symbol when not exists."""
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresPositionRepository(pool)
        result = await repo.find_by_symbol("BTCUSDT")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_all(self, mock_pool: MagicMock) -> None:
        """Test finding all open positions."""
        mock_conn = MagicMock()
        mock_rows = [
            {"id": "pos_1", "symbol": "BTCUSDT", "status": "open"},
            {"id": "pos_2", "symbol": "ETHUSDT", "status": "open"},
        ]
        mock_conn.fetch = AsyncMock(return_value=mock_rows)

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresPositionRepository(pool)
        result = await repo.find_all()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_update_pnl(self, mock_pool: MagicMock) -> None:
        """Test updating position PnL."""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresPositionRepository(pool)
        result = await repo.update_pnl("pos_1", 100.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_close(self, mock_pool: MagicMock) -> None:
        """Test closing a position."""
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresPositionRepository(pool)
        result = await repo.close("pos_1")
        assert result is True


class TestPostgresRiskLimitRepository:
    """Tests for PostgresRiskLimitRepository class."""

    @pytest.fixture
    def mock_pool(self) -> MagicMock:
        """Create mock connection pool."""
        pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        return pool

    @pytest.mark.asyncio
    async def test_get_limits_found(self, mock_pool: MagicMock) -> None:
        """Test getting risk limits when exists."""
        mock_conn = MagicMock()
        mock_row = {
            "account_id": "acc_1",
            "max_position_size": 10000.0,
            "max_daily_loss": 1000.0,
            "max_leverage": 10,
        }
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresRiskLimitRepository(pool)
        result = await repo.get_limits("acc_1")
        assert result is not None
        assert result["account_id"] == "acc_1"

    @pytest.mark.asyncio
    async def test_get_limits_not_found(self, mock_pool: MagicMock) -> None:
        """Test getting risk limits when not exists."""
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        repo = PostgresRiskLimitRepository(pool)
        result = await repo.get_limits("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_limits(self, mock_pool: MagicMock) -> None:
        """Test saving risk limits."""
        repo = PostgresRiskLimitRepository(mock_pool)
        limits = {
            "max_position_size": 10000.0,
            "max_daily_loss": 1000.0,
            "max_leverage": 10,
        }
        await repo.save_limits("acc_1", limits)
        mock_pool.acquire.return_value.__aenter__.return_value.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_current_exposure(self, mock_pool: MagicMock) -> None:
        """Test updating current exposure."""
        repo = PostgresRiskLimitRepository(mock_pool)
        exposure = {"BTC": 5000.0, "ETH": 3000.0}
        await repo.update_current_exposure("acc_1", exposure)
        mock_pool.acquire.return_value.__aenter__.return_value.execute.assert_called_once()
