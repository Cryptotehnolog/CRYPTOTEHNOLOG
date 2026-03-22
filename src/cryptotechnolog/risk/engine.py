"""
Первый orchestration-слой RiskEngine для pre-trade checks.

Этот модуль намеренно ограничен:
- только pre-trade gate;
- без event publication;
- без listeners и runtime wiring;
- без post-trade orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from time import perf_counter_ns
from typing import TYPE_CHECKING

from cryptotechnolog.core.state_machine_enums import SystemState, get_state_policy

from .correlation import CorrelationEvaluator, CorrelationViolation
from .drawdown_monitor import DrawdownLevel, DrawdownMonitor
from .models import (
    MarketSnapshot,
    Order,
    Position,
    PositionRiskRecord,
    PositionSide,
    PositionSize,
    RejectReason,
    RiskCheckResult,
    StopUpdate,
)
from .persistence_contracts import (
    IRiskPersistenceRepository,
    PositionRiskLedgerAuditRecord,
    RiskCheckAuditRecord,
    TrailingStopMovementRecord,
    TrailingStopSnapshotRecord,
)
from .position_sizing import PositionSizer, PositionSizingError, PositionSizingParams

if TYPE_CHECKING:
    from .portfolio_state import PortfolioState
    from .risk_ledger import RiskLedger
    from .trailing_policy import TrailingPolicy


class RiskEngineError(Exception):
    """Базовая ошибка RiskEngine."""


class RiskEngineEventType(StrEnum):
    """Стандартные исходящие события event-driven слоя RiskEngine."""

    ORDER_REJECTED = "ORDER_REJECTED"
    RISK_VIOLATION = "RISK_VIOLATION"
    DRAWDOWN_ALERT = "DRAWDOWN_ALERT"
    VELOCITY_KILLSWITCH_TRIGGERED = "VELOCITY_KILLSWITCH_TRIGGERED"
    RISK_POSITION_REGISTERED = "RISK_POSITION_REGISTERED"
    RISK_POSITION_RELEASED = "RISK_POSITION_RELEASED"
    TRAILING_STOP_MOVED = "TRAILING_STOP_MOVED"
    TRAILING_STOP_BLOCKED = "TRAILING_STOP_BLOCKED"
    RISK_ENGINE_STATE_UPDATED = "RISK_ENGINE_STATE_UPDATED"


@dataclass(slots=True, frozen=True)
class RiskEngineConfig:
    """
    Конфигурация первого pre-trade orchestration.

    Значения заданы как foundation для следующего шага с correlation
    и event-driven integration.
    """

    base_r_percent: Decimal
    max_r_per_trade: Decimal
    max_total_r: Decimal
    max_total_exposure_usd: Decimal
    max_position_size: Decimal
    quantity_step: Decimal = Decimal("0.00000001")
    price_precision: Decimal = Decimal("0.00000001")
    risk_precision: Decimal = Decimal("0.00000001")


@dataclass(slots=True, frozen=True)
class PreTradeContext:
    """
    Контекст предторговой проверки.

    Намеренно не содержит transport payload и не зависит от runtime.
    """

    system_state: SystemState
    current_equity: Decimal


@dataclass(slots=True, frozen=True)
class FilledPositionInput:
    """Типизированный вход для обработки ORDER_FILLED."""

    position_id: str
    symbol: str
    side: PositionSide
    entry_price: Decimal
    stop_loss: Decimal
    quantity: Decimal
    risk_capital_usd: Decimal | None = None


@dataclass(slots=True, frozen=True)
class ClosedPositionInput:
    """Типизированный вход для обработки POSITION_CLOSED."""

    position_id: str
    realized_pnl_r: Decimal | None = None
    current_equity: Decimal | None = None


@dataclass(slots=True, frozen=True)
class BarCompletedInput:
    """Типизированный вход для обработки BAR_COMPLETED."""

    symbol: str
    market: MarketSnapshot


@dataclass(slots=True, frozen=True)
class StateTransitionInput:
    """Типизированный вход для обработки STATE_TRANSITION."""

    from_state: SystemState | None
    to_state: SystemState


@dataclass(slots=True, frozen=True)
class PositionRegisteredResult:
    """Результат регистрации позиции в event-driven слое."""

    record: PositionRiskRecord


@dataclass(slots=True, frozen=True)
class PositionReleasedResult:
    """Результат освобождения риска позиции."""

    record: PositionRiskRecord


@dataclass(slots=True, frozen=True)
class BarProcessedResult:
    """Результат обработки BAR_COMPLETED."""

    updates: tuple[StopUpdate, ...]


@dataclass(slots=True, frozen=True)
class StateTransitionResult:
    """Результат синхронизации состояния системы."""

    from_state: SystemState | None
    to_state: SystemState


class RiskEngine:
    """
    Первый рабочий pre-trade gate поверх готового risk foundation.

    Уже использует:
    - `CorrelationEvaluator`
    - `PositionSizer`
    - `PortfolioState`
    - `DrawdownMonitor`
    - `RiskLedger`
    - `TrailingPolicy`

    Осознанно пока не включает:
    - listeners
    - event publication
    - runtime orchestration
    - funding
    """

    def __init__(
        self,
        *,
        config: RiskEngineConfig,
        correlation_evaluator: CorrelationEvaluator,
        position_sizer: PositionSizer,
        portfolio_state: PortfolioState,
        drawdown_monitor: DrawdownMonitor,
        risk_ledger: RiskLedger,
        trailing_policy: TrailingPolicy,
        persistence_repository: IRiskPersistenceRepository | None = None,
        initial_system_state: SystemState = SystemState.TRADING,
    ) -> None:
        self._config = config
        self._correlation_evaluator = correlation_evaluator
        self._position_sizer = position_sizer
        self._portfolio_state = portfolio_state
        self._drawdown_monitor = drawdown_monitor
        self._risk_ledger = risk_ledger
        self._trailing_policy = trailing_policy
        self._persistence_repository = persistence_repository
        self._current_system_state = initial_system_state

    def check_trade(self, order: Order, context: PreTradeContext) -> RiskCheckResult:
        """
        Проверить допустимость сделки перед исполнением.

        Порядок проверок в этом инкременте:
        1. Состояние системы разрешает новые сделки
        2. stop_loss присутствует
        3. Drawdown не превышает жёсткий лимит
        4. Velocity drawdown не сработал
        5. Position sizing рассчитывается успешно
        6. Aggregate risk не превышает лимит
        7. Aggregate exposure не превышает лимит
        """
        started_at = perf_counter_ns()
        current_total_r = self._risk_ledger.get_total_risk_r()

        reject_result = self._check_gate_conditions(
            order=order,
            context=context,
            started_at=started_at,
            current_total_r=current_total_r,
        )
        if reject_result is not None:
            return reject_result

        position_size = self._calculate_position_size(
            order=order,
            context=context,
            started_at=started_at,
            current_total_r=current_total_r,
        )
        if isinstance(position_size, RiskCheckResult):
            return position_size

        self._portfolio_state.assert_total_risk_matches_ledger(current_total_r)
        portfolio_snapshot = self._portfolio_state.snapshot()
        projected_total_r = current_total_r + position_size.actual_risk_r
        projected_exposure = portfolio_snapshot.total_exposure_usd + position_size.position_size_usd

        correlation_assessment = self._correlation_evaluator.assess_new_position(
            symbol=order.symbol,
            portfolio=portfolio_snapshot,
        )
        if not correlation_assessment.allowed:
            return self._reject(
                reason=self._map_correlation_violation_to_reason(correlation_assessment.violation),
                started_at=started_at,
                current_total_r=current_total_r,
                max_total_r=self._config.max_total_r,
                details={
                    "correlation_group": correlation_assessment.group.value,
                    "max_correlation": str(correlation_assessment.max_correlation),
                    "correlation_limit": str(correlation_assessment.correlation_limit),
                    "group_position_count": correlation_assessment.group_position_count,
                    "group_position_limit": correlation_assessment.group_position_limit,
                    "violating_symbol": correlation_assessment.violating_symbol or "",
                },
            )

        if projected_total_r > self._config.max_total_r:
            return self._reject(
                reason=RejectReason.MAX_TOTAL_R_EXCEEDED,
                started_at=started_at,
                current_total_r=current_total_r,
                max_total_r=self._config.max_total_r,
                details={
                    "projected_total_r": str(projected_total_r),
                    "requested_risk_r": str(position_size.actual_risk_r),
                },
            )

        if projected_exposure > self._config.max_total_exposure_usd:
            return self._reject(
                reason=RejectReason.MAX_TOTAL_EXPOSURE_EXCEEDED,
                started_at=started_at,
                current_total_r=current_total_r,
                max_total_r=self._config.max_total_r,
                details={
                    "current_total_exposure_usd": str(portfolio_snapshot.total_exposure_usd),
                    "projected_total_exposure_usd": str(projected_exposure),
                    "max_total_exposure_usd": str(self._config.max_total_exposure_usd),
                },
            )

        drawdown_assessment = self._drawdown_monitor.assess()
        effective_risk = self._effective_risk_budget(context.system_state)

        return RiskCheckResult(
            allowed=True,
            reason="within_limits",
            risk_r=position_size.actual_risk_r,
            position_size_usd=position_size.position_size_usd,
            position_size_base=position_size.quantity,
            current_total_r=current_total_r,
            max_total_r=self._config.max_total_r,
            check_duration_ms=self._elapsed_ms(started_at),
            details={
                "system_state": context.system_state.value,
                "effective_risk_per_trade": str(effective_risk),
                "projected_total_r": str(projected_total_r),
                "projected_total_exposure_usd": str(projected_exposure),
                "correlation_group": correlation_assessment.group.value,
                "max_correlation": str(correlation_assessment.max_correlation),
                "drawdown_level": drawdown_assessment.level.value,
            },
        )

    async def check_trade_with_audit(
        self,
        order: Order,
        context: PreTradeContext,
    ) -> RiskCheckResult:
        """
        Выполнить pre-trade проверку и при наличии repository сохранить audit trail.

        Чистая доменная логика остаётся в `check_trade()`,
        а persistence подключается только как optional side effect.
        """
        result = self.check_trade(order, context)
        await self._persist_risk_check_if_enabled(
            order=order,
            context=context,
            result=result,
        )
        return result

    def _check_gate_conditions(
        self,
        *,
        order: Order,
        context: PreTradeContext,
        started_at: int,
        current_total_r: Decimal,
    ) -> RiskCheckResult | None:
        """Проверить базовые pre-trade gate conditions до расчёта размера позиции."""
        if not context.system_state.is_trading_allowed:
            return self._reject(
                reason=RejectReason.STATE_MACHINE_NOT_TRADING,
                started_at=started_at,
                details={"system_state": context.system_state.value},
            )

        if order.stop_loss is None:
            return self._reject(
                reason=RejectReason.STOP_LOSS_REQUIRED,
                started_at=started_at,
                details={"order_id": order.order_id, "symbol": order.symbol},
            )

        drawdown_assessment = self._drawdown_monitor.assess_equity(context.current_equity)
        if drawdown_assessment.hard_breached:
            return self._reject(
                reason=RejectReason.DRAWDOWN_HARD_LIMIT_EXCEEDED,
                started_at=started_at,
                current_total_r=current_total_r,
                max_total_r=self._config.max_total_r,
                details={
                    "drawdown_percent": str(drawdown_assessment.drawdown_percent),
                    "hard_limit": str(drawdown_assessment.hard_limit),
                    "level": drawdown_assessment.level.value,
                },
            )
        if drawdown_assessment.level is DrawdownLevel.VELOCITY:
            return self._reject(
                reason=RejectReason.VELOCITY_DRAWDOWN_TRIGGERED,
                started_at=started_at,
                current_total_r=current_total_r,
                max_total_r=self._config.max_total_r,
                details={
                    "recent_losses_r": str(drawdown_assessment.recent_losses_r),
                    "velocity_limit_r": str(drawdown_assessment.velocity_loss_r),
                    "window_trades": drawdown_assessment.velocity_window_trades,
                },
            )
        return None

    def _calculate_position_size(
        self,
        *,
        order: Order,
        context: PreTradeContext,
        started_at: int,
        current_total_r: Decimal,
    ) -> RiskCheckResult | PositionSize:
        """Рассчитать размер позиции либо вернуть типизированный reject."""
        effective_risk = self._effective_risk_budget(context.system_state)
        try:
            return self._position_sizer.calculate_position_size(
                PositionSizingParams(
                    entry_price=order.entry_price,
                    stop_loss=order.stop_loss,
                    equity=context.current_equity,
                    base_r_percent=effective_risk,
                    max_r_per_trade=effective_risk,
                    max_position_size=self._effective_max_position_size(context.system_state),
                    quantity_step=self._config.quantity_step,
                    price_precision=self._config.price_precision,
                    risk_precision=self._config.risk_precision,
                )
            )
        except PositionSizingError as error:
            reason = self._map_sizing_error_to_reason(str(error))
            return self._reject(
                reason=reason,
                started_at=started_at,
                current_total_r=self._risk_ledger.get_total_risk_r(),
                max_total_r=self._config.max_total_r,
                details={
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "error": str(error),
                },
            )

    def _effective_risk_budget(self, system_state: SystemState) -> Decimal:
        """Рассчитать effective risk budget с учётом системной деградации."""
        policy = get_state_policy(system_state)
        scaled_limit = self._config.max_r_per_trade * Decimal(str(policy.risk_multiplier))
        return min(self._config.base_r_percent, scaled_limit)

    def _effective_max_position_size(self, system_state: SystemState) -> Decimal:
        """Рассчитать effective max_position_size для текущего системного состояния."""
        policy = get_state_policy(system_state)
        return self._config.max_position_size * Decimal(str(policy.risk_multiplier))

    async def handle_order_filled(
        self,
        data: FilledPositionInput,
    ) -> PositionRegisteredResult:
        """
        Обработать ORDER_FILLED и зарегистрировать открытую позицию.

        Источником истины по риску остаётся `RiskLedger`,
        а `PortfolioState` получает синхронно обновлённый snapshot.
        """
        risk_capital_usd = data.risk_capital_usd or self._drawdown_monitor.get_current_equity()
        position = Position(
            position_id=data.position_id,
            symbol=data.symbol,
            side=data.side,
            entry_price=data.entry_price,
            initial_stop=data.stop_loss,
            current_stop=data.stop_loss,
            quantity=data.quantity,
            risk_capital_usd=risk_capital_usd,
        )
        record = self._risk_ledger.register_position(position)
        self._portfolio_state.sync_position_from_ledger(record)
        self._portfolio_state.assert_position_matches_ledger(record)
        self._portfolio_state.assert_total_risk_matches_ledger(self._risk_ledger.get_total_risk_r())
        await self._persist_position_registration_if_enabled(record)
        return PositionRegisteredResult(record=record)

    async def handle_position_closed(
        self,
        data: ClosedPositionInput,
    ) -> PositionReleasedResult:
        """
        Обработать POSITION_CLOSED и освободить риск позиции.

        Дополнительно этот путь обновляет DrawdownMonitor,
        если в событии есть realized PnL и/или новое значение equity.
        """
        before_terminate = self._risk_ledger.get_position_record(data.position_id)
        terminate_update = self._trailing_policy.terminate(
            position_id=data.position_id,
            system_state=self._current_system_state,
        )
        terminated_record = self._risk_ledger.get_position_record(data.position_id)
        record = self._risk_ledger.release_position(data.position_id)
        self._portfolio_state.release_position_from_ledger(data.position_id)
        self._portfolio_state.assert_total_risk_matches_ledger(self._risk_ledger.get_total_risk_r())

        if data.realized_pnl_r is not None:
            self._drawdown_monitor.record_trade_result(data.realized_pnl_r)
        if data.current_equity is not None:
            self._drawdown_monitor.update_equity(data.current_equity)

        await self._persist_position_termination_if_enabled(
            symbol=record.symbol,
            previous_record=before_terminate,
            terminated_record=terminated_record,
            terminate_update=terminate_update,
        )
        await self._persist_position_release_if_enabled(
            terminated_record=terminated_record,
            released_record=record,
        )

        return PositionReleasedResult(record=record)

    async def handle_bar_completed(
        self,
        data: BarCompletedInput,
    ) -> BarProcessedResult:
        """
        Обработать рыночный бар для всех открытых позиций указанного символа.

        Доменное решение о движении стопа полностью остаётся в `TrailingPolicy`.
        """
        updates: list[StopUpdate] = []
        for record in self._portfolio_state.snapshot().positions:
            if record.symbol != data.symbol:
                continue
            previous_record = record

            pnl_r = self._calculate_unrealized_pnl_r(
                record=record, mark_price=data.market.mark_price
            )
            effective_pnl_r = max(pnl_r, Decimal("0"))

            if self._current_system_state in {
                SystemState.SURVIVAL,
                SystemState.RISK_REDUCTION,
            }:
                update = self._trailing_policy.force_emergency(
                    position_id=record.position_id,
                    pnl_r=effective_pnl_r,
                    market=data.market,
                    system_state=self._current_system_state,
                )
            else:
                update = self._trailing_policy.evaluate(
                    position_id=record.position_id,
                    pnl_r=effective_pnl_r,
                    market=data.market,
                    system_state=self._current_system_state,
                )

            refreshed = self._risk_ledger.get_position_record(record.position_id)
            self._portfolio_state.sync_position_from_ledger(refreshed)
            self._portfolio_state.assert_position_matches_ledger(refreshed)
            self._portfolio_state.assert_total_risk_matches_ledger(
                self._risk_ledger.get_total_risk_r()
            )
            await self._persist_trailing_update_if_enabled(
                symbol=data.symbol,
                previous_record=previous_record,
                refreshed_record=refreshed,
                update=update,
            )
            updates.append(update)

        return BarProcessedResult(updates=tuple(updates))

    async def handle_state_transition(
        self,
        data: StateTransitionInput,
    ) -> StateTransitionResult:
        """Синхронизировать новое системное состояние с event-driven контуром риска."""
        self._current_system_state = data.to_state
        return StateTransitionResult(
            from_state=data.from_state,
            to_state=data.to_state,
        )

    @property
    def current_system_state(self) -> SystemState:
        """Получить текущее состояние event-driven контура RiskEngine."""
        return self._current_system_state

    @property
    def has_persistence_repository(self) -> bool:
        """Проверить, подключён ли optional persistence repository."""
        return self._persistence_repository is not None

    @staticmethod
    def _map_sizing_error_to_reason(error_message: str) -> RejectReason:
        """Преобразовать ошибку sizing в стабильный доменный reject reason."""
        exact_matches = {
            RejectReason.STOP_LOSS_REQUIRED.value: RejectReason.STOP_LOSS_REQUIRED,
            RejectReason.ENTRY_EQUALS_STOP.value: RejectReason.ENTRY_EQUALS_STOP,
            RejectReason.INVALID_QUANTITY.value: RejectReason.INVALID_QUANTITY,
            RejectReason.INVALID_POSITION_SIZE.value: RejectReason.INVALID_POSITION_SIZE,
        }
        mapped = exact_matches.get(error_message)
        if mapped is not None:
            return mapped

        substring_matches = (
            ("max_r_per_trade", RejectReason.MAX_R_PER_TRADE_EXCEEDED),
            ("max_position_size", RejectReason.MAX_POSITION_SIZE_EXCEEDED),
        )
        for marker, reason in substring_matches:
            if marker in error_message:
                return reason

        return RejectReason.POSITION_SIZING_FAILED

    @staticmethod
    def _map_correlation_violation_to_reason(violation: CorrelationViolation) -> RejectReason:
        """Преобразовать correlation-нарушение в стабильный reject reason."""
        mapping = {
            CorrelationViolation.CORRELATION_LIMIT: RejectReason.CORRELATION_LIMIT_EXCEEDED,
            CorrelationViolation.GROUP_LIMIT: RejectReason.CORRELATION_GROUP_LIMIT_EXCEEDED,
            CorrelationViolation.NONE: RejectReason.POSITION_SIZING_FAILED,
        }
        return mapping[violation]

    def _reject(
        self,
        *,
        reason: RejectReason,
        started_at: int,
        current_total_r: Decimal = Decimal("0"),
        max_total_r: Decimal | None = None,
        details: dict[str, str | int] | None = None,
    ) -> RiskCheckResult:
        """Собрать типизированный reject-result."""
        return RiskCheckResult(
            allowed=False,
            reason=reason,
            current_total_r=current_total_r,
            max_total_r=max_total_r or self._config.max_total_r,
            check_duration_ms=self._elapsed_ms(started_at),
            details=details or {},
        )

    @staticmethod
    def _elapsed_ms(started_at: int) -> int:
        """Рассчитать длительность проверки в миллисекундах."""
        return (perf_counter_ns() - started_at) // 1_000_000

    async def _persist_risk_check_if_enabled(
        self,
        *,
        order: Order,
        context: PreTradeContext,
        result: RiskCheckResult,
    ) -> None:
        """Сохранить audit pre-trade проверки, если repository подключён."""
        if self._persistence_repository is None:
            return

        await self._persistence_repository.save_risk_check(
            RiskCheckAuditRecord.from_domain_result(
                order=order,
                result=result,
                system_state=context.system_state,
            )
        )

    async def _persist_position_registration_if_enabled(self, record: PositionRiskRecord) -> None:
        """Сохранить snapshot и audit регистрации позиции, если repository подключён."""
        if self._persistence_repository is None:
            return

        await self._persistence_repository.upsert_position_risk_record(record)
        await self._persistence_repository.append_position_risk_audit(
            PositionRiskLedgerAuditRecord.from_records(
                operation="REGISTER",
                current_record=None,
                next_record=record,
                reason="Позиция зарегистрирована после ORDER_FILLED",
            )
        )

    async def _persist_position_release_if_enabled(
        self,
        *,
        terminated_record: PositionRiskRecord,
        released_record: PositionRiskRecord,
    ) -> None:
        """Сохранить audit release и очистить активные snapshots закрытой позиции."""
        if self._persistence_repository is None:
            return

        await self._persistence_repository.append_position_risk_audit(
            PositionRiskLedgerAuditRecord.from_records(
                operation="RELEASE",
                current_record=terminated_record,
                next_record=None,
                reason="Позиция закрыта и риск освобождён",
            )
        )
        await self._persistence_repository.delete_position_risk_record(released_record.position_id)
        await self._persistence_repository.delete_trailing_stop_snapshot(
            released_record.position_id
        )

    async def _persist_position_termination_if_enabled(
        self,
        *,
        symbol: str,
        previous_record: PositionRiskRecord,
        terminated_record: PositionRiskRecord,
        terminate_update: StopUpdate,
    ) -> None:
        """Сохранить явный audit terminate до release позиции."""
        if self._persistence_repository is None:
            return

        await self._persistence_repository.upsert_position_risk_record(terminated_record)
        await self._persistence_repository.upsert_trailing_stop_snapshot(
            TrailingStopSnapshotRecord.from_stop_update(
                symbol=symbol,
                update=terminate_update,
                trailing_state=terminated_record.trailing_state.value,
                evaluated_at=terminated_record.updated_at,
            )
        )
        await self._persistence_repository.append_position_risk_audit(
            PositionRiskLedgerAuditRecord.from_records(
                operation="TERMINATE",
                current_record=previous_record,
                next_record=terminated_record,
                reason="Трейлинг завершён перед освобождением риска позиции",
            )
        )

    async def _persist_trailing_update_if_enabled(
        self,
        *,
        symbol: str,
        previous_record: PositionRiskRecord,
        refreshed_record: PositionRiskRecord,
        update: StopUpdate,
    ) -> None:
        """Сохранить audit trailing evaluation и актуальный snapshot, если repository подключён."""
        if self._persistence_repository is None:
            return

        await self._persistence_repository.append_trailing_stop_movement(
            TrailingStopMovementRecord.from_stop_update(
                symbol=symbol,
                update=update,
            )
        )
        await self._persistence_repository.upsert_trailing_stop_snapshot(
            TrailingStopSnapshotRecord.from_stop_update(
                symbol=symbol,
                update=update,
                trailing_state=refreshed_record.trailing_state.value,
                evaluated_at=refreshed_record.updated_at,
            )
        )

        if (
            previous_record.current_stop != refreshed_record.current_stop
            or previous_record.current_risk_r != refreshed_record.current_risk_r
            or previous_record.trailing_state != refreshed_record.trailing_state
        ):
            operation = (
                "UPDATE"
                if previous_record.current_stop != refreshed_record.current_stop
                else "STATE_SYNC"
            )
            reason = (
                "Движение стопа синхронизировано с RiskLedger"
                if update.should_execute
                else "Состояние trailing синхронизировано без движения стопа"
            )
            await self._persistence_repository.upsert_position_risk_record(refreshed_record)
            await self._persistence_repository.append_position_risk_audit(
                PositionRiskLedgerAuditRecord.from_records(
                    operation=operation,
                    current_record=previous_record,
                    next_record=refreshed_record,
                    reason=reason,
                )
            )

    @staticmethod
    def _calculate_unrealized_pnl_r(
        *,
        record: PositionRiskRecord,
        mark_price: Decimal,
    ) -> Decimal:
        """Рассчитать нереализованный PnL позиции в R."""
        if record.side is PositionSide.LONG:
            pnl_usd = (mark_price - record.entry_price) * record.quantity
        else:
            pnl_usd = (record.entry_price - mark_price) * record.quantity
        if record.initial_risk_usd <= 0:
            return Decimal("0")
        return pnl_usd / record.initial_risk_usd
