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
    RiskEngine,
    RiskEngineEventType,
    StateTransitionInput,
)
from .models import MarketSnapshot, PositionSide

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
            bar_result = await self._risk_engine.handle_bar_completed(
                self._parse_bar_completed(event.payload)
            )
            for update in bar_result.updates:
                await self._publish_result_event(
                    event_type=(
                        RiskEngineEventType.TRAILING_STOP_MOVED
                        if update.should_execute
                        else RiskEngineEventType.TRAILING_STOP_BLOCKED
                    ),
                    payload={
                        "position_id": update.position_id,
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
