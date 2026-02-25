"""
Тесты для stubs (src/core/stubs.py).

Проверяют:
- RiskEngineStub
- ExecutionLayerStub
- StrategyManagerStub
- StateMachineStub
- PortfolioGovernorStub
- Утилиты для работы с заглушками
"""

import pytest

from src.core.stubs import (
    ExecutionLayerStub,
    Order,
    OrderResult,
    PortfolioGovernorStub,
    RiskCheckResult,
    RiskEngineStub,
    State,
    StateMachineStub,
    Strategy,
    StrategyManagerStub,
    create_stub,
    get_stub_components,
)


class TestRiskEngineStub:
    """Тесты для RiskEngineStub."""

    def test_init(self) -> None:
        """Инициализация RiskEngine."""
        engine = RiskEngineStub()

        assert engine.enabled is True
        assert engine._max_position_size_usd == 100_000.0
        assert engine._max_daily_loss_usd == 10_000.0

    @pytest.mark.asyncio
    async def test_check_trade_allowed(self) -> None:
        """Проверка допустимой сделки."""
        engine = RiskEngineStub()

        result = await engine.check_trade("BTC/USDT", 1000.0, "buy")

        assert isinstance(result, RiskCheckResult)
        assert result.allowed is True
        assert result.details["symbol"] == "BTC/USDT"
        assert result.details["size_usd"] == 1000.0

    @pytest.mark.asyncio
    async def test_check_trade_sell(self) -> None:
        """Проверка продажи."""
        engine = RiskEngineStub()

        result = await engine.check_trade("ETH/USDT", 500.0, "sell")

        assert result.allowed is True
        assert result.details["side"] == "sell"

    @pytest.mark.asyncio
    async def test_check_order(self) -> None:
        """Проверка ордера."""
        engine = RiskEngineStub()

        result = await engine.check_order(
            order_type="limit",
            symbol="BTC/USDT",
            size=0.1,
            price=50000.0,
        )

        assert result.allowed is True
        assert result.details["order_type"] == "limit"

    @pytest.mark.asyncio
    async def test_get_risk_limits(self) -> None:
        """Получение лимитов риска."""
        engine = RiskEngineStub()

        limits = await engine.get_risk_limits()

        assert "max_position_size_usd" in limits
        assert "max_daily_loss_usd" in limits
        assert "note" in limits

    @pytest.mark.asyncio
    async def test_get_current_risk(self) -> None:
        """Получение текущего риска."""
        engine = RiskEngineStub()

        risk = await engine.get_current_risk()

        assert "current_exposure_usd" in risk
        assert "daily_pnl_usd" in risk
        assert risk["risk_score"] == 0.0

    @pytest.mark.asyncio
    async def test_pause_trading(self) -> None:
        """Приостановка торговли."""
        engine = RiskEngineStub()

        result = await engine.pause_trading("test_reason")

        assert result is True

    @pytest.mark.asyncio
    async def test_resume_trading(self) -> None:
        """Возобновление торговли."""
        engine = RiskEngineStub()

        result = await engine.resume_trading()

        assert result is True

    @pytest.mark.asyncio
    async def test_force_liquidation(self) -> None:
        """Принудительная ликвидация."""
        engine = RiskEngineStub()

        result = await engine.force_liquidation("BTC/USDT")

        assert result is True


class TestExecutionLayerStub:
    """Тесты для ExecutionLayerStub."""

    def test_init(self) -> None:
        """Инициализация ExecutionLayer."""
        executor = ExecutionLayerStub()

        assert executor.is_connected is True
        assert len(executor._pending_orders) == 0

    @pytest.mark.asyncio
    async def test_connect(self) -> None:
        """Подключение к биржам."""
        executor = ExecutionLayerStub()

        result = await executor.connect()

        assert result is True
        assert executor.is_connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self) -> None:
        """Отключение от бирж."""
        executor = ExecutionLayerStub()

        result = await executor.disconnect()

        assert result is True
        assert executor.is_connected is False

    @pytest.mark.asyncio
    async def test_execute_order(self) -> None:
        """Исполнение ордера."""
        executor = ExecutionLayerStub()

        order = Order(
            order_id="test_001",
            symbol="BTC/USDT",
            side="buy",
            order_type="market",
            size=0.1,
            price=50000.0,
        )

        result = await executor.execute_order(order)

        assert isinstance(result, OrderResult)
        assert result.success is True
        assert result.filled_size == 0.1

    @pytest.mark.asyncio
    async def test_execute_order_without_id(self) -> None:
        """Исполнение ордера без ID."""
        executor = ExecutionLayerStub()

        order = Order(
            order_id="",
            symbol="ETH/USDT",
            side="sell",
            order_type="limit",
            size=1.0,
            price=3000.0,
        )

        result = await executor.execute_order(order)

        assert result.success is True
        assert result.order_id.startswith("stub_")

    @pytest.mark.asyncio
    async def test_cancel_order(self) -> None:
        """Отмена ордера."""
        executor = ExecutionLayerStub()

        result = await executor.cancel_order("test_001", "BTC/USDT")

        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_all_orders(self) -> None:
        """Отмена всех ордеров."""
        executor = ExecutionLayerStub()

        result = await executor.cancel_all_orders()

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_cancel_all_orders_with_symbol(self) -> None:
        """Отмена ордеров по символу."""
        executor = ExecutionLayerStub()

        result = await executor.cancel_all_orders("BTC/USDT")

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_order_status_not_found(self) -> None:
        """Получение статуса несуществующего ордера."""
        executor = ExecutionLayerStub()

        result = await executor.get_order_status("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_open_orders_empty(self) -> None:
        """Получение открытых ордеров (пусто)."""
        executor = ExecutionLayerStub()

        result = await executor.get_open_orders()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_balance(self) -> None:
        """Получение баланса."""
        executor = ExecutionLayerStub()

        balance = await executor.get_balance("BTC")

        assert "available" in balance
        assert "locked" in balance
        assert balance["total"] == 0.0

    @pytest.mark.asyncio
    async def test_get_positions_empty(self) -> None:
        """Получение позиций (пусто)."""
        executor = ExecutionLayerStub()

        result = await executor.get_positions()

        assert result == []


class TestStrategyManagerStub:
    """Тесты для StrategyManagerStub."""

    def test_init(self) -> None:
        """Инициализация StrategyManager."""
        manager = StrategyManagerStub()

        assert manager.is_running is False
        assert len(manager._strategies) == 0

    @pytest.mark.asyncio
    async def test_start(self) -> None:
        """Запуск менеджера."""
        manager = StrategyManagerStub()

        result = await manager.start()

        assert result is True
        assert manager.is_running is True

    @pytest.mark.asyncio
    async def test_stop(self) -> None:
        """Остановка менеджера."""
        manager = StrategyManagerStub()
        await manager.start()

        result = await manager.stop()

        assert result is True
        assert manager.is_running is False

    @pytest.mark.asyncio
    async def test_register_strategy(self) -> None:
        """Регистрация стратегии."""
        manager = StrategyManagerStub()

        strategy = Strategy(name="test_strategy", enabled=False)
        result = await manager.register_strategy(strategy)

        assert result is True
        assert "test_strategy" in manager._strategies

    @pytest.mark.asyncio
    async def test_enable_strategy(self) -> None:
        """Включение стратегии."""
        manager = StrategyManagerStub()

        strategy = Strategy(name="test_strategy", enabled=False)
        await manager.register_strategy(strategy)

        result = await manager.enable_strategy("test_strategy")

        assert result is True

    @pytest.mark.asyncio
    async def test_disable_strategy(self) -> None:
        """Отключение стратегии."""
        manager = StrategyManagerStub()

        strategy = Strategy(name="test_strategy", enabled=True)
        await manager.register_strategy(strategy)

        result = await manager.disable_strategy("test_strategy")

        assert result is True

    @pytest.mark.asyncio
    async def test_disable_all_strategies(self) -> None:
        """Отключение всех стратегий."""
        manager = StrategyManagerStub()

        result = await manager.disable_all_strategies()

        assert result == 0  # Заглушка возвращает 0

    @pytest.mark.asyncio
    async def test_get_strategy(self) -> None:
        """Получение стратегии."""
        manager = StrategyManagerStub()

        strategy = Strategy(name="test_strategy", enabled=True)
        await manager.register_strategy(strategy)

        result = await manager.get_strategy("test_strategy")

        assert result is not None
        assert result.name == "test_strategy"

    @pytest.mark.asyncio
    async def test_get_strategy_not_found(self) -> None:
        """Получение несуществующей стратегии."""
        manager = StrategyManagerStub()

        result = await manager.get_strategy("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_strategies(self) -> None:
        """Получение всех стратегий."""
        manager = StrategyManagerStub()

        await manager.register_strategy(Strategy(name="s1"))
        await manager.register_strategy(Strategy(name="s2"))

        result = await manager.get_all_strategies()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_enabled_strategies(self) -> None:
        """Получение включённых стратегий."""
        manager = StrategyManagerStub()

        await manager.register_strategy(Strategy(name="s1", enabled=True))
        await manager.register_strategy(Strategy(name="s2", enabled=False))

        result = await manager.get_enabled_strategies()

        assert len(result) == 1
        assert result[0].name == "s1"


class TestStateMachineStub:
    """Тесты для StateMachineStub."""

    def test_init_default(self) -> None:
        """Инициализация с состоянием по умолчанию."""
        sm = StateMachineStub()

        assert sm.current_state == State.READY

    def test_init_custom_state(self) -> None:
        """Инициализация с кастомным состоянием."""
        sm = StateMachineStub(initial_state=State.TRADING)

        assert sm.current_state == State.TRADING

    @pytest.mark.asyncio
    async def test_transition(self) -> None:
        """Переход состояния."""
        sm = StateMachineStub()

        result = await sm.transition(State.TRADING, "test_reason")

        assert result is True
        assert sm.current_state == State.TRADING

    @pytest.mark.asyncio
    async def test_can_transition(self) -> None:
        """Проверка возможности перехода."""
        sm = StateMachineStub()

        result = await sm.can_transition(State.HALTED)

        assert result is True


class TestPortfolioGovernorStub:
    """Тесты для PortfolioGovernorStub."""

    def test_init(self) -> None:
        """Инициализация PortfolioGovernor."""
        pg = PortfolioGovernorStub()

        assert len(pg._positions) == 0

    @pytest.mark.asyncio
    async def test_open_position(self) -> None:
        """Открытие позиции."""
        pg = PortfolioGovernorStub()

        result = await pg.open_position("BTC/USDT", 0.1, 50000.0)

        assert result is True
        assert "BTC/USDT" in pg._positions

    @pytest.mark.asyncio
    async def test_close_position(self) -> None:
        """Закрытие позиции."""
        pg = PortfolioGovernorStub()
        await pg.open_position("BTC/USDT", 0.1, 50000.0)

        result = await pg.close_position("BTC/USDT")

        assert result is True
        assert "BTC/USDT" not in pg._positions

    @pytest.mark.asyncio
    async def test_get_positions(self) -> None:
        """Получение позиций."""
        pg = PortfolioGovernorStub()
        await pg.open_position("BTC/USDT", 0.1, 50000.0)
        await pg.open_position("ETH/USDT", 1.0, 3000.0)

        result = await pg.get_positions()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_total_pnl(self) -> None:
        """Получение общего P&L."""
        pg = PortfolioGovernorStub()

        result = await pg.get_total_pnl()

        assert result == 0.0


class TestStubUtilities:
    """Тесты для утилит работы со заглушками."""

    def test_get_stub_components(self) -> None:
        """Получение списка заглушек."""
        stubs = get_stub_components()

        assert "RiskEngine" in stubs
        assert "ExecutionLayer" in stubs
        assert "StrategyManager" in stubs
        assert "StateMachine" in stubs
        assert "PortfolioGovernor" in stubs

    def test_create_stub(self) -> None:
        """Создание экземпляра заглушки."""
        stub = create_stub("RiskEngine")

        assert isinstance(stub, RiskEngineStub)

    def test_create_stub_execution_layer(self) -> None:
        """Создание ExecutionLayer."""
        stub = create_stub("ExecutionLayer")

        assert isinstance(stub, ExecutionLayerStub)

    def test_create_stub_strategy_manager(self) -> None:
        """Создание StrategyManager."""
        stub = create_stub("StrategyManager")

        assert isinstance(stub, StrategyManagerStub)

    def test_create_stub_invalid(self) -> None:
        """Создание с неверным именем."""
        with pytest.raises(ValueError, match="Неизвестная заглушка"):
            create_stub("InvalidStub")


class TestStubsAliases:
    """Тесты для aliases."""

    def test_risk_engine_alias(self) -> None:
        """Проверка alias RiskEngine."""
        from src.core.stubs import RiskEngine

        assert RiskEngine is RiskEngineStub

    def test_execution_layer_alias(self) -> None:
        """Проверка alias ExecutionLayer."""
        from src.core.stubs import ExecutionLayer

        assert ExecutionLayer is ExecutionLayerStub

    def test_strategy_manager_alias(self) -> None:
        """Проверка alias StrategyManager."""
        from src.core.stubs import StrategyManager

        assert StrategyManager is StrategyManagerStub


class TestStubsEdgeCases:
    """Тесты граничных случаев."""

    @pytest.mark.asyncio
    async def test_risk_engine_large_size(self) -> None:
        """Проверка с большим размером позиции."""
        engine = RiskEngineStub()

        # Заглушка позволяет любой размер
        result = await engine.check_trade("BTC/USDT", 1_000_000.0, "buy")

        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_execution_layer_many_orders(self) -> None:
        """Отправка многих ордеров."""
        executor = ExecutionLayerStub()

        results = []
        for i in range(100):
            order = Order(
                order_id=f"order_{i}",
                symbol="BTC/USDT",
                side="buy",
                order_type="market",
                size=0.01,
            )
            result = await executor.execute_order(order)
            results.append(result)

        # Все должны быть успешными
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_strategy_manager_many_strategies(self) -> None:
        """Управление многими стратегиями."""
        manager = StrategyManagerStub()

        for i in range(50):
            strategy = Strategy(
                name=f"strategy_{i}",
                enabled=i % 2 == 0,
            )
            await manager.register_strategy(strategy)

        all_strategies = await manager.get_all_strategies()
        enabled_strategies = await manager.get_enabled_strategies()

        assert len(all_strategies) == 50
        assert len(enabled_strategies) == 25


# Mark all tests as unit tests
pytest.mark.unit(__name__)
