"""
Доменные модели Risk Engine.

Этот модуль содержит только типизированные доменные контракты
для управления рисками без привязки к transport-слоям и orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class OrderSide(StrEnum):
    """Направление ордера."""

    BUY = "buy"
    SELL = "sell"


class PositionSide(StrEnum):
    """Направление позиции."""

    LONG = "long"
    SHORT = "short"


class TrailingState(StrEnum):
    """Состояние трейлинга позиции."""

    INACTIVE = "inactive"
    ARMED = "armed"
    ACTIVE = "active"
    EMERGENCY = "emergency"
    TERMINATED = "terminated"


class TrailingTier(StrEnum):
    """Тир трейлинга по текущему PnL в R."""

    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"


class TrailingMode(StrEnum):
    """Режим работы трейлинга."""

    NORMAL = "NORMAL"
    STRUCTURAL = "STRUCTURAL"
    EMERGENCY = "EMERGENCY"


class TrailingEvaluationType(StrEnum):
    """Явная семантика записи trailing history/audit."""

    MOVE = "MOVE"
    BLOCKED = "BLOCKED"
    STATE_SYNC = "STATE_SYNC"
    TERMINATE = "TERMINATE"


class RejectReason(StrEnum):
    """Причины отклонения риск-проверки."""

    STATE_MACHINE_NOT_TRADING = "state_machine_not_trading"
    STOP_LOSS_REQUIRED = "stop_loss_required"
    ENTRY_EQUALS_STOP = "entry_equals_stop"
    INVALID_QUANTITY = "invalid_quantity"
    INVALID_POSITION_SIZE = "invalid_position_size"
    MAX_R_PER_TRADE_EXCEEDED = "max_r_per_trade_exceeded"
    MAX_POSITION_SIZE_EXCEEDED = "max_position_size_exceeded"
    MAX_TOTAL_R_EXCEEDED = "max_total_r_exceeded"
    MAX_TOTAL_EXPOSURE_EXCEEDED = "max_total_exposure_exceeded"
    DRAWDOWN_HARD_LIMIT_EXCEEDED = "drawdown_hard_limit_exceeded"
    VELOCITY_DRAWDOWN_TRIGGERED = "velocity_drawdown_triggered"
    POSITION_SIZING_FAILED = "position_sizing_failed"
    CORRELATION_LIMIT_EXCEEDED = "correlation_limit_exceeded"
    CORRELATION_GROUP_LIMIT_EXCEEDED = "correlation_group_limit_exceeded"


@dataclass(slots=True, frozen=True)
class Order:
    """
    Ордер для предторговой проверки риска.

    Все денежные значения должны передаваться как Decimal.
    """

    order_id: str
    symbol: str
    side: OrderSide
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal | None = None
    quantity: Decimal | None = None
    risk_usd: Decimal | None = None
    strategy_id: str | None = None
    exchange_id: str = "bybit"


@dataclass(slots=True, frozen=True)
class PositionSize:
    """
    Результат расчёта размера позиции по R-unit логике.

    Поле `requested_risk_usd` отражает исходную цель риска,
    а `actual_risk_usd`/`actual_risk_r` — фактический риск после округления
    и применения лимита `max_position_size`.
    """

    quantity: Decimal
    position_size_usd: Decimal
    requested_risk_usd: Decimal
    actual_risk_usd: Decimal
    actual_risk_r: Decimal
    risk_per_unit: Decimal
    capped_by_max_position_size: bool = False


@dataclass(slots=True, frozen=True)
class RiskCheckResult:
    """
    Результат проверки риска для сделки.

    Модель сохраняет доменный контракт для будущего `RiskEngine`,
    не завязываясь на внутренние словари.
    """

    allowed: bool
    reason: RejectReason | str
    risk_r: Decimal = Decimal("0")
    position_size_usd: Decimal = Decimal("0")
    position_size_base: Decimal = Decimal("0")
    current_total_r: Decimal = Decimal("0")
    max_total_r: Decimal = Decimal("0")
    correlation_with_portfolio: Decimal | None = None
    recommended_exchange: str | None = None
    max_size: Decimal | None = None
    check_duration_ms: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class Position:
    """
    Доменная модель открытой позиции.

    Важное решение для следующего шага:
    `current_stop` отделён от `entry_price`, а `initial_stop` хранится явно.
    Это позволяет `RiskLedger` различать исходный и текущий риск без вывода
    из истории событий.
    """

    position_id: str
    symbol: str
    side: PositionSide
    entry_price: Decimal
    initial_stop: Decimal
    current_stop: Decimal
    quantity: Decimal
    risk_capital_usd: Decimal
    strategy_id: str | None = None
    exchange_id: str = "bybit"
    trailing_state: TrailingState = TrailingState.INACTIVE
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True, frozen=True)
class StopUpdate:
    """
    Результат оценки нового стопа.

    Эта модель не исполняет обновление сама и не меняет ledger.
    Она фиксирует доменный intent для следующего шага, где появится
    обязательная синхронизация с `RiskLedger`.

    `evaluation_type` делает семантику истории явной:
    terminate/state-sync сценарии не маскируются под обычный stop move.
    """

    position_id: str
    old_stop: Decimal
    new_stop: Decimal
    pnl_r: Decimal
    evaluation_type: TrailingEvaluationType
    tier: TrailingTier
    mode: TrailingMode
    state: str
    risk_before: Decimal
    risk_after: Decimal
    should_execute: bool
    reason: str


@dataclass(slots=True, frozen=True)
class MarketSnapshot:
    """
    Снимок рынка для оценки трейлинга.

    Это доменный контракт для `TrailingPolicy`, а не transport payload.
    """

    mark_price: Decimal
    atr: Decimal
    best_bid: Decimal
    best_ask: Decimal
    adx: Decimal
    confirmed_highs: int = 0
    confirmed_lows: int = 0
    structural_stop: Decimal | None = None
    is_stale: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True, frozen=True)
class PositionRiskRecord:
    """
    Каноническая запись риска позиции в RiskLedger.

    Это единый источник истины для открытой позиции:
    отдельно фиксируются исходный и текущий риск, а также
    актуальный стоп и состояние трейлинга.
    """

    position_id: str
    symbol: str
    side: PositionSide
    entry_price: Decimal
    initial_stop: Decimal
    current_stop: Decimal
    quantity: Decimal
    risk_capital_usd: Decimal
    strategy_id: str | None
    initial_risk_usd: Decimal
    initial_risk_r: Decimal
    current_risk_usd: Decimal
    current_risk_r: Decimal
    current_price: Decimal
    unrealized_pnl_usd: Decimal
    unrealized_pnl_percent: Decimal
    trailing_state: TrailingState
    opened_at: datetime
    updated_at: datetime
    exchange_id: str = "bybit"


@dataclass(slots=True, frozen=True)
class FundingRateQuote:
    """
    Funding rate на конкретной бирже.

    Значение `rate` задаётся как ставка за funding period,
    например `0.001` = 0.1% за период.
    """

    exchange: str
    rate: Decimal


@dataclass(slots=True, frozen=True)
class FundingRateSnapshot:
    """
    Нормализованный снимок funding rates по символу.

    Содержит только доменные данные без привязки к transport payload.
    """

    symbol: str
    quotes: tuple[FundingRateQuote, ...]
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True, frozen=True)
class FundingExchangeRecommendation:
    """
    Рекомендация по выбору биржи с учётом funding cost/yield.

    Для LONG ищется минимальная ставка funding.
    Для SHORT ищется максимальная ставка funding.
    """

    symbol: str
    side: PositionSide
    current_exchange: str | None
    current_rate: Decimal | None
    recommended_exchange: str
    recommended_rate: Decimal
    rate_improvement: Decimal
    should_switch: bool
    entry_allowed: bool
    reason: str


@dataclass(slots=True, frozen=True)
class FundingOpportunity:
    """
    Обнаруженная возможность funding arbitrage между биржами.

    LONG открывается на бирже с минимальным funding,
    SHORT — на бирже с максимальным funding.
    """

    symbol: str
    long_exchange: str
    long_rate: Decimal
    short_exchange: str
    short_rate: Decimal
    spread: Decimal
    annualized_spread: Decimal
    detected_at: datetime
