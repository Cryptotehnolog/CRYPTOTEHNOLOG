"""
Заглушки для компонентов из будущих фаз.

Используются для:
1. Тестирования Фаз 1-2 без зависимостей
2. Документирования интерфейсов
3. Постепенной миграции (stub → real implementation)

ВНИМАНИЕ: Это заглушки для разработки и тестирования.
Для production использовать реальные реализации из соответствующих фаз.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid

from cryptotechnolog.config import get_logger

logger = get_logger(__name__)

# Флаг использования заглушек (устанавливается при импорте)
USE_STUBS: bool = True


# ============================================================================
# ФАЗА 5: RISK ENGINE
# ============================================================================


@dataclass
class RiskCheckResult:
    """Результат проверки риска."""

    allowed: bool
    reason: str | None = None
    risk_score: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


class RiskEngineStub:
    """
    Заглушка Risk Engine (реализация в Фазе 5).

    В production это будет полноценный компонент с:
    - R-unit system
    - Position size validation
    - Drawdown monitoring
    - Correlation checks
    - Real-time risk limits

    Заглушка всегда возвращает allowed=True и не выполняет
    реальных проверок риска.

    Пример использования:
        >>> from cryptotechnolog.core.stubs import RiskEngineStub
        >>> engine = RiskEngineStub()
        >>> result = await engine.check_trade("BTC/USDT", 1000.0, "buy")
        >>> print(result.allowed)  # True
    """

    def __init__(self) -> None:
        """Инициализировать заглушку Risk Engine."""
        self._enabled: bool = True
        self._max_position_size_usd: float = 100_000.0
        self._max_daily_loss_usd: float = 10_000.0

        logger.warning(
            "⚠️  Используется ЗАГЛУШКА RiskEngine",
            real_implementation="Фаза 5: Risk Engine",
            note="Для production требуется реальная реализация",
        )

    @property
    def enabled(self) -> bool:
        """Проверить включён ли Risk Engine."""
        return self._enabled

    async def check_trade(
        self,
        symbol: str,
        size_usd: float,
        side: str,
    ) -> RiskCheckResult:
        """
        Проверить допустимость сделки.

        ЗАГЛУШКА: Всегда возвращает allowed=True без реальной проверки.

        Аргументы:
            symbol: Торговая пара (например, "BTC/USDT")
            size_usd: Размер позиции в USD
            side: Направление сделки ("buy" или "sell")

        Returns:
            RiskCheckResult с allowed=True

        Примечание:
            Это заглушка. Реальная реализация будет:
            - Проверять лимиты позиций
            - Рассчитывать R-units
            - Проверять корреляцию с другими позициями
            - Мониторить просадку
        """
        logger.debug(
            "RiskEngine stub: проверка пропущена",
            symbol=symbol,
            size_usd=size_usd,
            side=side,
        )

        return RiskCheckResult(
            allowed=True,
            reason="stub_implementation",
            risk_score=0.0,
            details={
                "symbol": symbol,
                "size_usd": size_usd,
                "side": side,
                "note": "Это заглушка - реальная проверка не выполнялась",
            },
        )

    async def check_order(
        self,
        order_type: str,
        symbol: str,
        size: float,
        price: float | None = None,
    ) -> RiskCheckResult:
        """
        Проверить допустимость ордера.

        ЗАГЛУШКА: Всегда возвращает allowed=True.

        Аргументы:
            order_type: Тип ордера ("market", "limit", "stop")
            symbol: Торговая пара
            size: Размер ордера
            price: Цена ордера (для лимитных ордеров)

        Returns:
            RiskCheckResult с allowed=True
        """
        logger.debug(
            "RiskEngine stub: проверка ордера пропущена",
            order_type=order_type,
            symbol=symbol,
            size=size,
            price=price,
        )

        return RiskCheckResult(
            allowed=True,
            reason="stub_implementation",
            risk_score=0.0,
            details={"order_type": order_type, "symbol": symbol},
        )

    async def get_risk_limits(self) -> dict[str, Any]:
        """
        Получить текущие лимиты риска.

        Returns:
            Словарь с лимитами риска
        """
        return {
            "max_position_size_usd": self._max_position_size_usd,
            "max_daily_loss_usd": self._max_daily_loss_usd,
            "max_leverage": 1.0,
            "max_correlated_positions": 5,
            "note": "Заглушка - лимиты не проверяются",
        }

    async def get_current_risk(self) -> dict[str, Any]:
        """
        Получить текущее состояние риска.

        Returns:
            Словарь с текущим риском
        """
        return {
            "current_exposure_usd": 0.0,
            "daily_pnl_usd": 0.0,
            "risk_score": 0.0,
            "active_positions": 0,
            "note": "Заглушка - риск не отслеживается",
        }

    async def pause_trading(self, reason: str = "manual") -> bool:
        """
        Приостановить торговлю.

        ЗАГЛУШКА: Просто возвращает True.

        Аргументы:
            reason: Причина приостановки

        Returns:
            True
        """
        logger.warning(
            "RiskEngine stub: pause_trading() вызван",
            reason=reason,
            note="Заглушка - торговля не остановлена",
        )
        return True

    async def resume_trading(self) -> bool:
        """
        Возобновить торговлю.

        ЗАГЛУШКА: Просто возвращает True.

        Returns:
            True
        """
        logger.warning(
            "RiskEngine stub: resume_trading() вызван",
            note="Заглушка - торговля не возобновлена",
        )
        return True

    async def force_liquidation(self, symbol: str) -> bool:
        """
        Принудительно ликвидировать позицию.

        ЗАГЛУШКА: Просто возвращает True.

        Аргументы:
            symbol: Торговая пара для ликвидации

        Returns:
            True
        """
        logger.warning(
            "RiskEngine stub: force_liquidation() вызван",
            symbol=symbol,
            note="Заглушка - ликвидация не выполнена",
        )
        return True


# ============================================================================
# ФАЗА 10: EXECUTION LAYER
# ============================================================================


@dataclass
class Order:
    """Ордер на бирже."""

    order_id: str
    symbol: str
    side: str  # "buy" или "sell"
    order_type: str  # "market", "limit", "stop"
    size: float
    price: float | None = None
    status: str = "pending"  # "pending", "filled", "cancelled", "rejected"
    filled_size: float = 0.0
    average_price: float | None = None


@dataclass
class OrderResult:
    """Результат исполнения ордера."""

    success: bool
    order_id: str
    message: str
    filled_size: float = 0.0
    average_price: float | None = None


class ExecutionLayerStub:
    """
    Заглушка Execution Layer (реализация в Фазе 10).

    В production это будет полноценный компонент с:
    - Multiple exchange adapters (Binance, Coinbase, etc.)
    - Order management system
    - Smart order routing
    - Execution quality monitoring

    Заглушка не отправляет ордера на биржу, а просто
    имитирует успешное исполнение.

    Пример использования:
        >>> from cryptotechnolog.core.stubs import ExecutionLayerStub, Order
        >>> executor = ExecutionLayerStub()
        >>> order = Order("test_001", "BTC/USDT", "buy", "market", 0.1)
        >>> result = await executor.execute_order(order)
        >>> print(result.success)  # True
    """

    def __init__(self) -> None:
        """Инициализировать заглушку Execution Layer."""
        self._connected: bool = True
        self._pending_orders: dict[str, Order] = {}

        logger.warning(
            "⚠️  Используется ЗАГЛУШКА ExecutionLayer",
            real_implementation="Фаза 10: Execution Layer",
            note="Для production требуется реальная реализация",
        )

    @property
    def is_connected(self) -> bool:
        """Проверить подключение к биржам."""
        return self._connected

    async def connect(self) -> bool:
        """
        Подключиться к биржам.

        Returns:
            True
        """
        self._connected = True
        logger.info("ExecutionLayer stub: подключение имитировано")
        return True

    async def disconnect(self) -> bool:
        """
        Отключиться от бирж.

        Returns:
            True
        """
        self._connected = False
        self._pending_orders.clear()
        logger.info("ExecutionLayer stub: отключение имитировано")
        return True

    async def execute_order(self, order: Order) -> OrderResult:
        """
        Отправить ордер на биржу.

        ЗАГЛУШКА: Имитирует успешное исполнение ордера.

        Аргументы:
            order: Ордер для исполнения

        Returns:
            OrderResult с success=True и сгенерированным order_id

        Примечание:
            Это заглушка. Реальная реализация будет:
            - Отправлять ордера на биржу через API
            - Обрабатывать ответы биржи
            - Управлять повторными попытками
            - Вести логи исполнения
        """
        logger.debug(
            "ExecutionLayer stub: ордер НЕ отправлен на биржу",
            order_id=order.order_id,
            symbol=order.symbol,
            size=order.size,
        )

        # Генерируем фиктивный order_id если не предоставлен
        actual_order_id = order.order_id or f"stub_{uuid.uuid4().hex[:8]}"

        return OrderResult(
            success=True,
            order_id=actual_order_id,
            message="Ордер имитирован (заглушка)",
            filled_size=order.size,
            average_price=order.price,
        )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Отменить ордер.

        ЗАГЛУШКА: Всегда возвращает True.

        Аргументы:
            order_id: ID ордера для отмены
            symbol: Торговая пара

        Returns:
            True
        """
        logger.debug(
            "ExecutionLayer stub: отмена ордера имитирована",
            order_id=order_id,
            symbol=symbol,
        )

        if order_id in self._pending_orders:
            del self._pending_orders[order_id]

        return True

    async def cancel_all_orders(self, symbol: str | None = None) -> list[str]:
        """
        Отменить все активные ордера.

        ЗАГЛУШКА: Возвращает пустой список.

        Аргументы:
            symbol: Опционально фильтр по торговой паре

        Returns:
            Пустой список отменённых ордеров
        """
        logger.warning(
            "ExecutionLayer stub: cancel_all_orders() вызван",
            symbol=symbol or "all",
            note="Заглушка - ордера не отменены",
        )

        # Очищаем ожидающие ордера
        cancelled = list(self._pending_orders.keys())
        self._pending_orders.clear()

        return cancelled

    async def get_order_status(self, order_id: str) -> Order | None:
        """
        Получить статус ордера.

        ЗАГЛУШКА: Возвращает None.

        Аргументы:
            order_id: ID ордера

        Returns:
            None (ордер не найден)
        """
        return self._pending_orders.get(order_id)

    async def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        """
        Получить список открытых ордеров.

        ЗАГЛУШКА: Возвращает пустой список.

        Аргументы:
            symbol: Опционально фильтр по торговой паре

        Returns:
            Пустой список
        """
        if symbol:
            return [order for order in self._pending_orders.values() if order.symbol == symbol]
        return list(self._pending_orders.values())

    async def get_balance(self, symbol: str) -> dict[str, float | str]:
        """
        Получить баланс.

        ЗАГЛУШКА: Возвращает нулевой баланс.

        Аргументы:
            symbol: Валюта

        Returns:
            Словарь с нулевым балансом
        """
        return {
            "available": 0.0,
            "locked": 0.0,
            "total": 0.0,
            "note": "Заглушка - баланс не получен",
        }

    async def get_positions(self) -> list[dict[str, Any]]:
        """
        Получить список открытых позиций.

        ЗАГЛУШКА: Возвращает пустой список.

        Returns:
            Пустой список позиций
        """
        return []


# ============================================================================
# ФАЗА 14: STRATEGY MANAGER
# ============================================================================


@dataclass
class Strategy:
    """Торговая стратегия."""

    name: str
    enabled: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)
    status: str = "stopped"  # "running", "stopped", "paused"


class StrategyManagerStub:
    """
    Заглушка Strategy Manager (реализация в Фазе 14).

    В production это будет полноценный компонент с:
    - Strategy lifecycle management
    - Parameter validation
    - Signal generation
    - Performance tracking

    Заглушка не управляет реальными стратегиями.

    Пример использования:
        >>> from cryptotechnolog.core.stubs import StrategyManagerStub
        >>> manager = StrategyManagerStub()
        >>> result = await manager.disable_all_strategies()
        >>> print(result)  # 0
    """

    def __init__(self) -> None:
        """Инициализировать заглушку Strategy Manager."""
        self._strategies: dict[str, Strategy] = {}
        self._running: bool = False

        logger.warning(
            "⚠️  Используется ЗАГЛУШКА StrategyManager",
            real_implementation="Фаза 14: Strategy Manager",
            note="Для production требуется реальная реализация",
        )

    @property
    def is_running(self) -> bool:
        """Проверить запущен ли менеджер."""
        return self._running

    async def start(self) -> bool:
        """
        Запустить менеджер стратегий.

        Returns:
            True
        """
        self._running = True
        logger.info("StrategyManager stub: запущен")
        return True

    async def stop(self) -> bool:
        """
        Остановить менеджер стратегий.

        Returns:
            True
        """
        self._running = False
        logger.info("StrategyManager stub: остановлен")
        return True

    async def register_strategy(self, strategy: Strategy) -> bool:
        """
        Зарегистрировать стратегию.

        ЗАГЛУШКА: Просто добавляет в словарь.

        Аргументы:
            strategy: Стратегия для регистрации

        Returns:
            True
        """
        self._strategies[strategy.name] = strategy
        logger.debug(
            "StrategyManager stub: стратегия зарегистрирована",
            name=strategy.name,
        )
        return True

    async def enable_strategy(self, strategy_name: str) -> bool:
        """
        Включить стратегию.

        ЗАГЛУШКА: Просто возвращает True.

        Аргументы:
            strategy_name: Имя стратегии

        Returns:
            True
        """
        logger.warning(
            "StrategyManager stub: enable_strategy() вызван",
            strategy_name=strategy_name,
            note="Заглушка - стратегия не включена",
        )

        if strategy_name in self._strategies:
            self._strategies[strategy_name].enabled = True

        return True

    async def disable_strategy(self, strategy_name: str) -> bool:
        """
        Отключить стратегию.

        ЗАГЛУШКА: Просто возвращает True.

        Аргументы:
            strategy_name: Имя стратегии

        Returns:
            True
        """
        logger.warning(
            "StrategyManager stub: disable_strategy() вызван",
            strategy_name=strategy_name,
            note="Заглушка - стратегия не отключена",
        )

        if strategy_name in self._strategies:
            self._strategies[strategy_name].enabled = False

        return True

    async def disable_all_strategies(self) -> int:
        """
        Отключить все торговые стратегии.

        ЗАГЛУШКА: Возвращает 0 (количество отключенных стратегий).

        Returns:
            0
        """
        logger.warning(
            "StrategyManager stub: disable_all_strategies() вызван",
            note="Заглушка - стратегии не отключены",
        )

        disabled_count = 0
        for strategy in self._strategies.values():
            if strategy.enabled:
                strategy.enabled = False
                disabled_count += 1

        return 0  # Заглушка всегда возвращает 0

    async def get_strategy(self, strategy_name: str) -> Strategy | None:
        """
        Получить стратегию по имени.

        Аргументы:
            strategy_name: Имя стратегии

        Returns:
            Стратегия или None
        """
        return self._strategies.get(strategy_name)

    async def get_all_strategies(self) -> list[Strategy]:
        """
        Получить все стратегии.

        Returns:
            Список всех стратегий
        """
        return list(self._strategies.values())

    async def get_enabled_strategies(self) -> list[Strategy]:
        """
        Получить включённые стратегии.

        Returns:
            Список включённых стратегий
        """
        return [s for s in self._strategies.values() if s.enabled]


# ============================================================================
# ФАЗА 2: STATE MACHINE (дополнительно)
# ============================================================================


class State:
    """Состояние системы."""

    INITIALIZING = "INITIALIZING"
    READY = "READY"
    TRADING = "TRADING"
    DEGRADED = "DEGRADED"
    HALTED = "HALTED"
    EMERGENCY = "EMERGENCY"


class StateMachineStub:
    """
    Заглушка State Machine (реализация в Фазе 2).

    В production это будет полноценный компонент с:
    - State transitions with guards
    - Event-driven state changes
    - Transition validation

    Заглушка просто хранит текущее состояние.
    """

    def __init__(self, initial_state: str = State.READY) -> None:
        """Инициализировать заглушку State Machine."""
        self._current_state: str = initial_state

        logger.warning(
            "⚠️  Используется ЗАГЛУШКА StateMachine",
            real_implementation="Фаза 2: State Machine",
            note="Для production требуется реальная реализация",
        )

    @property
    def current_state(self) -> str:
        """Получить текущее состояние."""
        return self._current_state

    async def transition(self, new_state: str, reason: str = "") -> bool:
        """
        Перейти в новое состояние.

        ЗАГЛУШКА: Просто меняет состояние.

        Аргументы:
            new_state: Новое состояние
            reason: Причина перехода

        Returns:
            True
        """
        old_state = self._current_state
        self._current_state = new_state

        logger.info(
            "StateMachine stub: переход состояния",
            old_state=old_state,
            new_state=new_state,
            reason=reason,
        )

        return True

    async def can_transition(self, new_state: str) -> bool:
        """
        Проверить возможность перехода.

        ЗАГЛУШКА: Всегда возвращает True.

        Аргументы:
            new_state: Новое состояние

        Returns:
            True
        """
        return True


# ============================================================================
# ФАЗА 9: PORTFOLIO GOVERNOR (дополнительно)
# ============================================================================


@dataclass
class Position:
    """Позиция в портфеле."""

    symbol: str
    size: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0


class PortfolioGovernorStub:
    """
    Заглушка Portfolio Governor (реализация в Фазе 9).

    В production это будет полноценный компонент с:
    - Position tracking
    - P&L calculation
    - Rebalancing logic
    """

    def __init__(self) -> None:
        """Инициализировать заглушку Portfolio Governor."""
        self._positions: dict[str, Position] = {}

        logger.warning(
            "⚠️  Используется ЗАГЛУШКА PortfolioGovernor",
            real_implementation="Фаза 9: Portfolio Governor",
            note="Для production требуется реальная реализация",
        )

    async def open_position(self, symbol: str, size: float, entry_price: float) -> bool:
        """
        Открыть позицию.

        ЗАГЛУШКА: Просто добавляет в словарь.

        Аргументы:
            symbol: Торговая пара
            size: Размер позиции
            entry_price: Цена входа

        Returns:
            True
        """
        self._positions[symbol] = Position(
            symbol=symbol,
            size=size,
            entry_price=entry_price,
            current_price=entry_price,
        )
        return True

    async def close_position(self, symbol: str) -> bool:
        """
        Закрыть позицию.

        ЗАГЛУШКА: Просто удаляет из словаря.

        Аргументы:
            symbol: Торговая пара

        Returns:
            True
        """
        if symbol in self._positions:
            del self._positions[symbol]
        return True

    async def get_positions(self) -> list[Position]:
        """
        Получить все позиции.

        Returns:
            Список позиций
        """
        return list(self._positions.values())

    async def get_total_pnl(self) -> float:
        """
        Получить общий P&L.

        Returns:
            0.0 (заглушка)
        """
        return 0.0


# ============================================================================
# УТИЛИТЫ ДЛЯ ИСПОЛЬЗОВАНИЯ ЗАГЛУШЕК
# ============================================================================


def get_stub_components() -> dict[str, type]:
    """
    Получить словарь всех доступных заглушек.

    Returns:
        Словарь имя -> класс заглушки
    """
    return {
        "RiskEngine": RiskEngineStub,
        "ExecutionLayer": ExecutionLayerStub,
        "StrategyManager": StrategyManagerStub,
        "StateMachine": StateMachineStub,
        "PortfolioGovernor": PortfolioGovernorStub,
    }


def create_stub(stub_name: str) -> Any:
    """
    Создать экземпляр заглушки по имени.

    Аргументы:
        stub_name: Имя заглушки

    Returns:
        Экземпляр заглушки

    Raises:
        ValueError: Если заглушка не найдена
    """
    stubs = get_stub_components()

    if stub_name not in stubs:
        raise ValueError(f"Неизвестная заглушка: {stub_name}. Доступны: {list(stubs.keys())}")

    return stubs[stub_name]()


# ============================================================================
# ДЛЯ СОВМЕСТИМОСТИ С ИМПОРТАМИ ИЗ ДРУГИХ ЧАСТЕЙ СИСТЕМЫ
# ============================================================================

# Aliases для удобного импорта
RiskEngine = RiskEngineStub
ExecutionLayer = ExecutionLayerStub
StrategyManager = StrategyManagerStub
