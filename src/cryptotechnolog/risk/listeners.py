"""
Event-driven integration layer для RiskEngine.

Listener остаётся тонким адаптером:
- преобразует transport event в типизированный вход RiskEngine;
- вызывает доменные методы orchestration-слоя;
- публикует стандартизированные risk-события;
- не содержит собственной бизнес-логики риска.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from cryptotechnolog.core.event import Event, Priority, SystemEventSource, SystemEventType
from cryptotechnolog.core.listeners.base import BaseListener, ListenerConfig
from cryptotechnolog.core.state_machine_enums import SystemState

from .engine import (
    BarCompletedInput,
    ClosedPositionInput,
    FilledPositionInput,
    PreTradeContext,
    RiskEngine,
    RiskEngineEventType,
    StateTransitionInput,
)
from .models import MarketSnapshot, Order, OrderSide, PositionSide, RejectReason, RiskCheckResult

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class RiskEngineListenerError(Exception):
    """Базовая ошибка listener-адаптера RiskEngine."""


@dataclass(slots=True, frozen=True)
class RiskEngineListenerConfig:
    """Конфигурация адаптерного listener для event-driven RiskEngine."""

    name: str = "risk_engine_listener"
    priority: int = 95
    max_retries: int = 3
    retry_delay: float = 0.2


class RiskEngineListener(BaseListener):
    """
    Тонкий listener для связывания Event Bus и доменного RiskEngine.

    Здесь нет доменных решений по риску:
    listener только адаптирует payload и публикует результат обработки.
    """

    def __init__(
        self,
        *,
        risk_engine: RiskEngine,
        publisher: Callable[[Event], Awaitable[bool]],
        config: RiskEngineListenerConfig | None = None,
    ) -> None:
        listener_config = config or RiskEngineListenerConfig()
        super().__init__(
            ListenerConfig(
                name=listener_config.name,
                event_types=[
                    SystemEventType.ORDER_SUBMITTED,
                    SystemEventType.ORDER_FILLED,
                    "POSITION_CLOSED",
                    "BAR_COMPLETED",
                    SystemEventType.STATE_TRANSITION,
                ],
                priority=listener_config.priority,
                max_retries=listener_config.max_retries,
                retry_delay=listener_config.retry_delay,
            )
        )
        self._risk_engine = risk_engine
        self._publisher = publisher

    async def _process_event(self, event: Event) -> None:
        """Обработать входящее событие через соответствующий доменный path RiskEngine."""
        if event.event_type == SystemEventType.ORDER_SUBMITTED:
            result = await self._risk_engine.check_trade_with_audit(
                self._parse_order_submitted(event.payload),
                self._parse_pre_trade_context(event.payload),
            )
            if not result.allowed:
                await self._publish_pre_trade_reject_events(result=result, source_event=event)
            return

        if event.event_type == SystemEventType.ORDER_FILLED:
            register_result = await self._risk_engine.handle_order_filled(
                self._parse_order_filled(event.payload)
            )
            await self._publish_result_event(
                event_type=RiskEngineEventType.RISK_POSITION_REGISTERED,
                payload={
                    "position_id": register_result.record.position_id,
                    "symbol": register_result.record.symbol,
                    "side": register_result.record.side.value,
                    "current_stop": str(register_result.record.current_stop),
                    "current_risk_r": str(register_result.record.current_risk_r),
                    "trailing_state": register_result.record.trailing_state.value,
                },
                priority=Priority.NORMAL,
                source_event=event,
            )
            return

        if event.event_type == "POSITION_CLOSED":
            release_result = await self._risk_engine.handle_position_closed(
                self._parse_position_closed(event.payload)
            )
            await self._publish_result_event(
                event_type=RiskEngineEventType.RISK_POSITION_RELEASED,
                payload={
                    "position_id": release_result.record.position_id,
                    "symbol": release_result.record.symbol,
                    "released_risk_r": str(release_result.record.current_risk_r),
                    "trailing_state": release_result.record.trailing_state.value,
                },
                priority=Priority.NORMAL,
                source_event=event,
            )
            return

        if event.event_type == "BAR_COMPLETED":
            bar_input = self._parse_bar_completed(event.payload)
            bar_result = await self._risk_engine.handle_bar_completed(bar_input)
            for update in bar_result.updates:
                await self._publish_result_event(
                    event_type=(
                        RiskEngineEventType.TRAILING_STOP_MOVED
                        if update.should_execute
                        else RiskEngineEventType.TRAILING_STOP_BLOCKED
                    ),
                    payload={
                        "position_id": update.position_id,
                        "symbol": bar_input.symbol,
                        "old_stop": str(update.old_stop),
                        "new_stop": str(update.new_stop),
                        "pnl_r": str(update.pnl_r),
                        "evaluation_type": update.evaluation_type.value,
                        "tier": update.tier.value,
                        "mode": update.mode.value,
                        "state": update.state,
                        "risk_before": str(update.risk_before),
                        "risk_after": str(update.risk_after),
                        "reason": update.reason,
                        "should_execute": update.should_execute,
                    },
                    priority=Priority.HIGH if not update.should_execute else Priority.NORMAL,
                    source_event=event,
                )
            return

        if event.event_type == SystemEventType.STATE_TRANSITION:
            transition_result = await self._risk_engine.handle_state_transition(
                self._parse_state_transition(event.payload)
            )
            await self._publish_result_event(
                event_type=RiskEngineEventType.RISK_ENGINE_STATE_UPDATED,
                payload={
                    "from_state": (
                        transition_result.from_state.value
                        if transition_result.from_state is not None
                        else None
                    ),
                    "to_state": transition_result.to_state.value,
                    "risk_engine_state": transition_result.to_state.value,
                },
                priority=Priority.NORMAL,
                source_event=event,
            )
            return

        raise RiskEngineListenerError(f"Событие {event.event_type} не поддерживается listener")

    async def _publish_result_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        priority: Priority,
        source_event: Event,
    ) -> None:
        """Опубликовать стандартизированное risk-событие с сохранением correlation chain."""
        published = Event.new(
            event_type=event_type,
            source=SystemEventSource.RISK_ENGINE,
            payload=payload,
        )
        published.priority = priority
        if source_event.correlation_id is not None:
            published.correlation_id = source_event.correlation_id
        await self._publisher(published)

    async def _publish_pre_trade_reject_events(
        self,
        *,
        result: RiskCheckResult,
        source_event: Event,
    ) -> None:
        """Опубликовать стабильный reject/violation contract для production risk path."""
        order_payload = source_event.payload
        reject_reason = (
            result.reason.value if isinstance(result.reason, RejectReason) else str(result.reason)
        )
        violation_priority = self._get_violation_priority(result)
        reject_payload = {
            "order_id": order_payload.get("order_id"),
            "symbol": order_payload.get("symbol"),
            "side": order_payload.get("side"),
            "price": str(order_payload.get("entry_price") or order_payload.get("price") or ""),
            "stop_loss": str(order_payload.get("stop_loss") or ""),
            "reason": reject_reason,
            "reject_reason": reject_reason,
            "system_state": str(
                order_payload.get("system_state")
                or order_payload.get("current_state")
                or self._risk_engine.current_system_state.value
            ),
            "current_equity": str(
                order_payload.get("current_equity")
                or order_payload.get("equity")
                or self._risk_engine._drawdown_monitor.get_current_equity()
            ),
            "current_total_r": str(result.current_total_r),
            "max_total_r": str(result.max_total_r),
            "check_duration_ms": result.check_duration_ms,
            "details": result.details,
        }
        await self._publish_result_event(
            event_type=RiskEngineEventType.ORDER_REJECTED,
            payload=reject_payload,
            priority=violation_priority,
            source_event=source_event,
        )

        current_value, max_value = self._extract_violation_values(result)
        await self._publish_result_event(
            event_type=RiskEngineEventType.RISK_VIOLATION,
            payload={
                "order_id": order_payload.get("order_id"),
                "symbol": order_payload.get("symbol"),
                "side": order_payload.get("side"),
                "price": str(order_payload.get("entry_price") or order_payload.get("price") or ""),
                "reason": reject_reason,
                "limit_type": self._map_reject_reason_to_limit_type(result),
                "current_value": current_value,
                "max_value": max_value,
                "current_total_r": str(result.current_total_r),
                "max_total_r": str(result.max_total_r),
                "violation_type": reject_reason,
                "details": result.details,
            },
            priority=violation_priority,
            source_event=source_event,
        )

        if result.reason is RejectReason.DRAWDOWN_HARD_LIMIT_EXCEEDED:
            await self._publish_result_event(
                event_type=RiskEngineEventType.DRAWDOWN_ALERT,
                payload={
                    "order_id": order_payload.get("order_id"),
                    "symbol": order_payload.get("symbol"),
                    "reason": reject_reason,
                    "drawdown_level": result.details.get("level"),
                    "drawdown_percent": result.details.get("drawdown_percent"),
                    "hard_limit": result.details.get("hard_limit"),
                    "current_total_r": str(result.current_total_r),
                    "max_total_r": str(result.max_total_r),
                },
                priority=Priority.HIGH,
                source_event=source_event,
            )

        if result.reason is RejectReason.VELOCITY_DRAWDOWN_TRIGGERED:
            await self._publish_result_event(
                event_type=RiskEngineEventType.VELOCITY_KILLSWITCH_TRIGGERED,
                payload={
                    "order_id": order_payload.get("order_id"),
                    "symbol": order_payload.get("symbol"),
                    "reason": reject_reason,
                    "drawdown_level": "velocity",
                    "recent_losses_r": result.details.get("recent_losses_r"),
                    "velocity_limit_r": result.details.get("velocity_limit_r"),
                    "window_trades": result.details.get("window_trades"),
                    "current_total_r": str(result.current_total_r),
                    "max_total_r": str(result.max_total_r),
                },
                priority=Priority.CRITICAL,
                source_event=source_event,
            )

    @staticmethod
    def _parse_order_filled(payload: dict[str, Any]) -> FilledPositionInput:
        """Преобразовать payload ORDER_FILLED в типизированный вход."""
        return FilledPositionInput(
            position_id=RiskEngineListener._require_str(payload, "position_id"),
            symbol=RiskEngineListener._require_str(payload, "symbol"),
            side=RiskEngineListener._parse_position_side(
                RiskEngineListener._require_str(payload, "side")
            ),
            entry_price=RiskEngineListener._require_decimal(payload, "avg_price", "price"),
            stop_loss=RiskEngineListener._require_decimal(payload, "stop_loss"),
            quantity=RiskEngineListener._require_decimal(
                payload,
                "filled_qty",
                "filled_size",
                "quantity",
            ),
            risk_capital_usd=RiskEngineListener._optional_decimal(payload, "risk_capital_usd"),
        )

    @staticmethod
    def _parse_position_closed(payload: dict[str, Any]) -> ClosedPositionInput:
        """Преобразовать payload POSITION_CLOSED в типизированный вход."""
        return ClosedPositionInput(
            position_id=RiskEngineListener._require_str(payload, "position_id"),
            realized_pnl_r=RiskEngineListener._optional_decimal(payload, "realized_pnl_r"),
            current_equity=RiskEngineListener._optional_decimal(payload, "current_equity"),
        )

    @staticmethod
    def _parse_bar_completed(payload: dict[str, Any]) -> BarCompletedInput:
        """Преобразовать payload BAR_COMPLETED в типизированный вход."""
        mark_price = RiskEngineListener._require_decimal(payload, "mark_price", "close")
        return BarCompletedInput(
            symbol=RiskEngineListener._require_str(payload, "symbol"),
            market=MarketSnapshot(
                mark_price=mark_price,
                atr=RiskEngineListener._require_decimal(payload, "atr"),
                best_bid=RiskEngineListener._require_decimal(payload, "best_bid"),
                best_ask=RiskEngineListener._require_decimal(payload, "best_ask"),
                adx=RiskEngineListener._require_decimal(payload, "adx"),
                confirmed_highs=RiskEngineListener._coerce_int(payload.get("confirmed_highs", 0)),
                confirmed_lows=RiskEngineListener._coerce_int(payload.get("confirmed_lows", 0)),
                structural_stop=RiskEngineListener._optional_decimal(payload, "structural_stop"),
                is_stale=bool(payload.get("is_stale", False)),
            ),
        )

    @staticmethod
    def _parse_state_transition(payload: dict[str, Any]) -> StateTransitionInput:
        """Преобразовать payload STATE_TRANSITION в типизированный вход."""
        from_state_raw = payload.get("from_state")
        return StateTransitionInput(
            from_state=(
                RiskEngineListener._parse_system_state(from_state_raw)
                if from_state_raw is not None
                else None
            ),
            to_state=RiskEngineListener._parse_system_state(payload.get("to_state")),
        )

    @staticmethod
    def _parse_position_side(raw_value: str) -> PositionSide:
        """Нормализовать сторону исполненного ордера в сторону позиции."""
        normalized = raw_value.strip().lower()
        mapping = {
            "buy": PositionSide.LONG,
            "long": PositionSide.LONG,
            "sell": PositionSide.SHORT,
            "short": PositionSide.SHORT,
        }
        side = mapping.get(normalized)
        if side is None:
            raise RiskEngineListenerError(f"Неизвестное направление позиции: {raw_value}")
        return side

    @staticmethod
    def _parse_system_state(raw_value: Any) -> SystemState:
        """Нормализовать строку/enum в SystemState без двусмысленных fallback."""
        if isinstance(raw_value, SystemState):
            return raw_value
        if not isinstance(raw_value, str):
            raise RiskEngineListenerError("Системное состояние должно быть строкой")

        normalized = raw_value.strip()
        try:
            return SystemState(normalized.lower())
        except ValueError:
            try:
                return SystemState[normalized.upper()]
            except KeyError as error:
                raise RiskEngineListenerError(
                    f"Неизвестное системное состояние: {raw_value}"
                ) from error

    @staticmethod
    def _parse_order_submitted(payload: dict[str, Any]) -> Order:
        """Преобразовать payload ORDER_SUBMITTED в типизированный pre-trade order."""
        return Order(
            order_id=RiskEngineListener._require_str(payload, "order_id"),
            symbol=RiskEngineListener._require_str(payload, "symbol"),
            side=RiskEngineListener._parse_order_side(
                RiskEngineListener._require_str(payload, "side")
            ),
            entry_price=RiskEngineListener._require_decimal(payload, "entry_price", "price"),
            stop_loss=RiskEngineListener._require_decimal(payload, "stop_loss"),
            take_profit=RiskEngineListener._optional_decimal(payload, "take_profit"),
            quantity=RiskEngineListener._optional_decimal(payload, "quantity"),
            risk_usd=RiskEngineListener._optional_decimal(payload, "risk_usd"),
            strategy_id=RiskEngineListener._optional_str(payload, "strategy_id"),
            exchange_id=RiskEngineListener._optional_str(payload, "exchange_id") or "bybit",
        )

    def _parse_pre_trade_context(self, payload: dict[str, Any]) -> PreTradeContext:
        """Преобразовать payload ORDER_SUBMITTED в типизированный pre-trade context."""
        raw_state = payload.get("system_state") or payload.get("current_state")
        current_state = (
            self._parse_system_state(raw_state)
            if raw_state is not None
            else self._risk_engine.current_system_state
        )
        current_equity = (
            self._optional_decimal(payload, "current_equity")
            or self._optional_decimal(payload, "equity")
            or self._risk_engine._drawdown_monitor.get_current_equity()
        )
        return PreTradeContext(
            system_state=current_state,
            current_equity=current_equity,
        )

    @staticmethod
    def _parse_order_side(raw_value: str) -> OrderSide:
        """Нормализовать сторону pre-trade ордера в OrderSide."""
        normalized = raw_value.strip().lower()
        mapping = {
            "buy": OrderSide.BUY,
            "long": OrderSide.BUY,
            "sell": OrderSide.SELL,
            "short": OrderSide.SELL,
        }
        side = mapping.get(normalized)
        if side is None:
            raise RiskEngineListenerError(f"Неизвестное направление ордера: {raw_value}")
        return side

    @staticmethod
    def _optional_str(payload: dict[str, Any], key: str) -> str | None:
        """Извлечь необязательную строку из payload."""
        value = payload.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise RiskEngineListenerError(f"Поле {key} должно быть непустой строкой")
        return value

    @staticmethod
    def _map_reject_reason_to_limit_type(result: RiskCheckResult) -> str:
        """Стабилизировать тип нарушения для downstream listeners и audit semantics."""
        mapping = {
            RejectReason.DRAWDOWN_HARD_LIMIT_EXCEEDED: "drawdown_hard_limit",
            RejectReason.VELOCITY_DRAWDOWN_TRIGGERED: "velocity_drawdown",
            RejectReason.MAX_TOTAL_R_EXCEEDED: "max_total_r",
            RejectReason.MAX_TOTAL_EXPOSURE_EXCEEDED: "max_total_exposure",
            RejectReason.MAX_R_PER_TRADE_EXCEEDED: "max_r_per_trade",
            RejectReason.MAX_POSITION_SIZE_EXCEEDED: "max_position_size",
            RejectReason.CORRELATION_LIMIT_EXCEEDED: "correlation_limit",
            RejectReason.CORRELATION_GROUP_LIMIT_EXCEEDED: "correlation_limit",
            RejectReason.STATE_MACHINE_NOT_TRADING: "system_state",
        }
        if isinstance(result.reason, RejectReason):
            return mapping.get(result.reason, "risk_check")
        return "risk_check"

    @staticmethod
    def _extract_violation_values(result: RiskCheckResult) -> tuple[str, str]:
        """Извлечь current/max значения нарушения в предсказуемом текстовом виде."""
        if result.reason is RejectReason.DRAWDOWN_HARD_LIMIT_EXCEEDED:
            return (
                str(result.details.get("drawdown_percent", "")),
                str(result.details.get("hard_limit", "")),
            )
        if result.reason is RejectReason.VELOCITY_DRAWDOWN_TRIGGERED:
            return (
                str(result.details.get("recent_losses_r", "")),
                str(result.details.get("velocity_limit_r", "")),
            )
        if result.reason is RejectReason.MAX_TOTAL_EXPOSURE_EXCEEDED:
            return (
                str(result.details.get("projected_total_exposure_usd", "")),
                str(result.details.get("max_total_exposure_usd", "")),
            )
        if result.reason is RejectReason.MAX_TOTAL_R_EXCEEDED:
            return (
                str(result.details.get("projected_total_r", result.current_total_r)),
                str(result.max_total_r),
            )
        return (str(result.current_total_r), str(result.max_total_r))

    @staticmethod
    def _get_violation_priority(result: RiskCheckResult) -> Priority:
        """Определить severity-level приоритет для reject/violation signals."""
        if result.reason is RejectReason.VELOCITY_DRAWDOWN_TRIGGERED:
            return Priority.CRITICAL
        if result.reason in {
            RejectReason.DRAWDOWN_HARD_LIMIT_EXCEEDED,
            RejectReason.MAX_TOTAL_R_EXCEEDED,
            RejectReason.MAX_TOTAL_EXPOSURE_EXCEEDED,
            RejectReason.CORRELATION_LIMIT_EXCEEDED,
            RejectReason.CORRELATION_GROUP_LIMIT_EXCEEDED,
        }:
            return Priority.HIGH
        return Priority.NORMAL

    @staticmethod
    def _require_str(payload: dict[str, Any], key: str) -> str:
        """Извлечь обязательную строку из payload."""
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RiskEngineListenerError(f"Поле {key} обязательно и должно быть непустой строкой")
        return value

    @staticmethod
    def _require_decimal(payload: dict[str, Any], *keys: str) -> Decimal:
        """Извлечь обязательный Decimal из первого найденного ключа."""
        for key in keys:
            if key in payload and payload[key] is not None:
                return RiskEngineListener._coerce_decimal(payload[key], key)
        joined_keys = ", ".join(keys)
        raise RiskEngineListenerError(f"Одно из полей [{joined_keys}] обязательно для события")

    @staticmethod
    def _optional_decimal(payload: dict[str, Any], key: str) -> Decimal | None:
        """Извлечь необязательный Decimal из payload."""
        value = payload.get(key)
        if value is None:
            return None
        return RiskEngineListener._coerce_decimal(value, key)

    @staticmethod
    def _coerce_decimal(value: Any, field_name: str) -> Decimal:
        """Преобразовать значение к Decimal без использования float-математики."""
        try:
            return Decimal(str(value))
        except Exception as error:
            raise RiskEngineListenerError(
                f"Поле {field_name} не удалось преобразовать к Decimal: {value}"
            ) from error

    @staticmethod
    def _coerce_int(value: Any) -> int:
        """Преобразовать счётчик структурных подтверждений к int."""
        try:
            return int(value)
        except Exception as error:
            raise RiskEngineListenerError(
                f"Счётчик подтверждений должен быть целым числом: {value}"
            ) from error
