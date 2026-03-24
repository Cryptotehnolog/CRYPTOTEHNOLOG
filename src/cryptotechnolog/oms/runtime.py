"""
Узкий explicit runtime foundation для Phase 16 OMS Foundation.

Этот runtime:
- стартует и останавливается явно;
- не делает hidden bootstrap;
- собирает typed OMS context из execution truth;
- поддерживает один минимальный deterministic order-state contour;
- хранит query/state-first truth и operator-visible diagnostics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

from cryptotechnolog.execution import ExecutionOrderIntent, ExecutionStatus
from cryptotechnolog.market_data import MarketDataTimeframe

from .events import OmsEventType, OmsOrderPayload
from .models import (
    OmsContext,
    OmsFreshness,
    OmsLifecycleStatus,
    OmsOrderLocator,
    OmsOrderRecord,
    OmsQueryScope,
    OmsReasonCode,
    OmsSource,
    OmsValidity,
    OmsValidityStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID


type OmsStateKey = tuple[str, str, MarketDataTimeframe, str, str, str]


class OmsRuntimeLifecycleState(StrEnum):
    """Lifecycle-состояние OMS runtime."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class OmsRuntimeConfig:
    """Typed runtime-конфигурация OMS foundation."""

    contour_name: str = "phase16_oms_contour"
    oms_name: str = "phase16_oms"
    max_order_age_seconds: int = 86400
    history_retention_limit: int = 10000
    partial_fill_threshold: Decimal = Decimal("0.0001")

    def __post_init__(self) -> None:
        if self.max_order_age_seconds <= 0:
            raise ValueError("max_order_age_seconds должен быть положительным")
        if self.history_retention_limit <= 0:
            raise ValueError("history_retention_limit должен быть положительным")
        if self.partial_fill_threshold < Decimal("0"):
            raise ValueError("partial_fill_threshold не может быть отрицательным")


@dataclass(slots=True)
class OmsRuntimeDiagnostics:
    """Operator-visible diagnostics contract OMS runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: OmsRuntimeLifecycleState = OmsRuntimeLifecycleState.NOT_STARTED
    tracked_contexts: int = 0
    tracked_active_orders: int = 0
    tracked_historical_orders: int = 0
    last_intent_id: str | None = None
    last_order_id: str | None = None
    last_event_type: str | None = None
    last_failure_reason: str | None = None
    readiness_reasons: list[str] = field(default_factory=list)
    degraded_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Преобразовать diagnostics в operator-facing словарь."""
        return {
            "started": self.started,
            "ready": self.ready,
            "lifecycle_state": self.lifecycle_state.value,
            "tracked_contexts": self.tracked_contexts,
            "tracked_active_orders": self.tracked_active_orders,
            "tracked_historical_orders": self.tracked_historical_orders,
            "last_intent_id": self.last_intent_id,
            "last_order_id": self.last_order_id,
            "last_event_type": self.last_event_type,
            "last_failure_reason": self.last_failure_reason,
            "readiness_reasons": list(self.readiness_reasons),
            "degraded_reasons": list(self.degraded_reasons),
        }


@dataclass(slots=True, frozen=True)
class OmsRuntimeUpdate:
    """Typed update contract OMS runtime foundation."""

    context: OmsContext
    order_record: OmsOrderRecord | None
    event_type: OmsEventType | None
    emitted_payload: OmsOrderPayload | None = None


class OmsRuntime:
    """Explicit runtime foundation для OMS layer Phase 16."""

    _TERMINAL_STATUSES: ClassVar[set[OmsLifecycleStatus]] = {
        OmsLifecycleStatus.FILLED,
        OmsLifecycleStatus.CANCELLED,
        OmsLifecycleStatus.REJECTED,
        OmsLifecycleStatus.EXPIRED,
    }
    _ALLOWED_TRANSITIONS: ClassVar[dict[OmsLifecycleStatus, set[OmsLifecycleStatus]]] = {
        OmsLifecycleStatus.REGISTERED: {
            OmsLifecycleStatus.SUBMITTED,
            OmsLifecycleStatus.CANCELLED,
            OmsLifecycleStatus.REJECTED,
            OmsLifecycleStatus.EXPIRED,
        },
        OmsLifecycleStatus.SUBMITTED: {
            OmsLifecycleStatus.ACCEPTED,
            OmsLifecycleStatus.CANCELLED,
            OmsLifecycleStatus.REJECTED,
            OmsLifecycleStatus.EXPIRED,
        },
        OmsLifecycleStatus.ACCEPTED: {
            OmsLifecycleStatus.PARTIALLY_FILLED,
            OmsLifecycleStatus.FILLED,
            OmsLifecycleStatus.CANCELLED,
            OmsLifecycleStatus.REJECTED,
            OmsLifecycleStatus.EXPIRED,
        },
        OmsLifecycleStatus.PARTIALLY_FILLED: {
            OmsLifecycleStatus.PARTIALLY_FILLED,
            OmsLifecycleStatus.FILLED,
            OmsLifecycleStatus.CANCELLED,
            OmsLifecycleStatus.EXPIRED,
        },
        OmsLifecycleStatus.FILLED: set(),
        OmsLifecycleStatus.CANCELLED: set(),
        OmsLifecycleStatus.REJECTED: set(),
        OmsLifecycleStatus.EXPIRED: set(),
    }
    _REASON_BY_STATUS: ClassVar[dict[OmsLifecycleStatus, OmsReasonCode]] = {
        OmsLifecycleStatus.REGISTERED: OmsReasonCode.ORDER_REGISTERED,
        OmsLifecycleStatus.SUBMITTED: OmsReasonCode.ORDER_SUBMITTED,
        OmsLifecycleStatus.ACCEPTED: OmsReasonCode.ORDER_ACCEPTED,
        OmsLifecycleStatus.PARTIALLY_FILLED: OmsReasonCode.ORDER_PARTIALLY_FILLED,
        OmsLifecycleStatus.FILLED: OmsReasonCode.ORDER_FILLED,
        OmsLifecycleStatus.CANCELLED: OmsReasonCode.ORDER_CANCELLED,
        OmsLifecycleStatus.REJECTED: OmsReasonCode.ORDER_REJECTED,
        OmsLifecycleStatus.EXPIRED: OmsReasonCode.ORDER_EXPIRED,
    }
    _EVENT_BY_STATUS: ClassVar[dict[OmsLifecycleStatus, OmsEventType]] = {
        OmsLifecycleStatus.REGISTERED: OmsEventType.OMS_ORDER_REGISTERED,
        OmsLifecycleStatus.SUBMITTED: OmsEventType.OMS_ORDER_SUBMITTED,
        OmsLifecycleStatus.ACCEPTED: OmsEventType.OMS_ORDER_ACCEPTED,
        OmsLifecycleStatus.PARTIALLY_FILLED: OmsEventType.OMS_ORDER_PARTIALLY_FILLED,
        OmsLifecycleStatus.FILLED: OmsEventType.OMS_ORDER_FILLED,
        OmsLifecycleStatus.CANCELLED: OmsEventType.OMS_ORDER_CANCELLED,
        OmsLifecycleStatus.REJECTED: OmsEventType.OMS_ORDER_REJECTED,
        OmsLifecycleStatus.EXPIRED: OmsEventType.OMS_ORDER_EXPIRED,
    }

    def __init__(
        self,
        config: OmsRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or OmsRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = OmsRuntimeDiagnostics()
        self._started = False
        self._contexts: dict[OmsStateKey, OmsContext] = {}
        self._order_key_by_id: dict[UUID, OmsStateKey] = {}
        self._order_key_by_intent_id: dict[UUID, OmsStateKey] = {}
        self._active_orders: dict[OmsStateKey, OmsOrderRecord] = {}
        self._historical_orders: dict[OmsStateKey, OmsOrderRecord] = {}
        self._push_diagnostics()

    @property
    def is_started(self) -> bool:
        """Проверить, активирован ли runtime."""
        return self._started

    async def start(self) -> None:
        """Поднять runtime без hidden bootstrap."""
        if self._started:
            return
        self._started = True
        self._refresh_diagnostics(
            lifecycle_state=OmsRuntimeLifecycleState.WARMING,
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_execution_intent_processed",),
            degraded_reasons=(),
        )

    async def stop(self) -> None:
        """Остановить runtime и очистить operator-visible state."""
        if not self._started:
            return
        self._started = False
        self._contexts = {}
        self._order_key_by_id = {}
        self._order_key_by_intent_id = {}
        self._active_orders = {}
        self._historical_orders = {}
        self._refresh_diagnostics(
            lifecycle_state=OmsRuntimeLifecycleState.STOPPED,
            ready=False,
            tracked_contexts=0,
            tracked_active_orders=0,
            tracked_historical_orders=0,
            last_intent_id=None,
            last_order_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def ingest_intent(
        self,
        *,
        intent: ExecutionOrderIntent,
        reference_time: datetime,
        metadata: dict[str, object] | None = None,
    ) -> OmsRuntimeUpdate:
        """Принять execution truth, собрать OMS context и обновить order-state."""
        self._ensure_started("ingest_intent")
        context = self._assemble_oms_context(
            intent=intent,
            reference_time=reference_time,
            metadata=metadata,
        )
        key = self._build_state_key_from_context(context)
        self._contexts[key] = context

        if context.validity.status == OmsValidityStatus.INVALID:
            self._refresh_diagnostics_for_context(
                context=context,
                order_record=self._active_orders.get(key) or self._historical_orders.get(key),
                event_type=None,
                lifecycle_state=OmsRuntimeLifecycleState.DEGRADED,
                ready=False,
                readiness_reasons=("execution_intent_invalid",),
                degraded_reasons=(context.validity.invalid_reason or "execution_intent_invalid",),
                last_failure_reason=context.validity.invalid_reason or "execution_intent_invalid",
            )
            return OmsRuntimeUpdate(
                context=context,
                order_record=None,
                event_type=None,
                emitted_payload=None,
            )

        if context.validity.is_warming:
            self._refresh_diagnostics_for_context(
                context=context,
                order_record=self._active_orders.get(key) or self._historical_orders.get(key),
                event_type=None,
                lifecycle_state=OmsRuntimeLifecycleState.WARMING,
                ready=False,
                readiness_reasons=tuple(context.validity.missing_inputs)
                or ("execution_intent_not_executable",),
                degraded_reasons=(),
            )
            return OmsRuntimeUpdate(
                context=context,
                order_record=None,
                event_type=None,
                emitted_payload=None,
            )

        existing = self._active_orders.get(key) or self._historical_orders.get(key)
        if existing is not None:
            self._refresh_diagnostics_for_context(
                context=context,
                order_record=existing,
                event_type=None,
                lifecycle_state=OmsRuntimeLifecycleState.READY,
                ready=True,
                readiness_reasons=(),
                degraded_reasons=tuple(self._diagnostics.degraded_reasons),
            )
            return OmsRuntimeUpdate(
                context=context,
                order_record=existing,
                event_type=None,
                emitted_payload=None,
            )

        record = OmsOrderRecord.registered(
            contour_name=self.config.contour_name,
            oms_name=self.config.oms_name,
            symbol=context.symbol,
            exchange=context.exchange,
            timeframe=context.timeframe,
            freshness=self._build_record_freshness(intent=intent, reference_time=reference_time),
            validity=context.validity,
            originating_intent_id=context.intent.intent_id,
            reason_code=OmsReasonCode.ORDER_REGISTERED,
            query_scope=OmsQueryScope.ACTIVE,
            metadata=context.metadata,
        )
        self._register_active_record(key=key, record=record)
        event_type = OmsEventType.OMS_ORDER_REGISTERED
        payload = OmsOrderPayload.from_record(record)
        self._refresh_diagnostics_for_context(
            context=context,
            order_record=record,
            event_type=event_type,
            lifecycle_state=OmsRuntimeLifecycleState.READY,
            ready=True,
            readiness_reasons=(),
            degraded_reasons=tuple(self._diagnostics.degraded_reasons),
        )
        return OmsRuntimeUpdate(
            context=context,
            order_record=record,
            event_type=event_type,
            emitted_payload=payload,
        )

    def advance_order(
        self,
        *,
        oms_order_id: UUID,
        target_status: OmsLifecycleStatus,
        reference_time: datetime,
        reason_code: OmsReasonCode | None = None,
        client_order_id: str | None = None,
        external_order_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> OmsRuntimeUpdate:
        """Детерминированно продвинуть lifecycle state уже зарегистрированного order-state."""
        self._ensure_started("advance_order")
        key = self._order_key_by_id.get(oms_order_id)
        if key is None:
            raise KeyError(f"OMS order {oms_order_id} не найден")

        record = self._active_orders.get(key) or self._historical_orders.get(key)
        assert record is not None
        self._validate_transition(current=record.lifecycle_status, target=target_status)

        if target_status == OmsLifecycleStatus.PARTIALLY_FILLED:
            metadata = {
                "partial_fill_threshold": str(self.config.partial_fill_threshold),
                **(metadata or {}),
            }

        updated = self._build_transitioned_record(
            record=record,
            target_status=target_status,
            reference_time=reference_time,
            reason_code=reason_code or self._REASON_BY_STATUS[target_status],
            client_order_id=client_order_id,
            external_order_id=external_order_id,
            metadata=metadata,
        )
        self._store_transitioned_record(key=key, record=updated)
        context = self._contexts[key]
        event_type = self._EVENT_BY_STATUS[target_status]
        payload = OmsOrderPayload.from_record(updated)
        self._refresh_diagnostics_for_context(
            context=context,
            order_record=updated,
            event_type=event_type,
            lifecycle_state=OmsRuntimeLifecycleState.READY,
            ready=True,
            readiness_reasons=(),
            degraded_reasons=tuple(self._diagnostics.degraded_reasons),
        )
        return OmsRuntimeUpdate(
            context=context,
            order_record=updated,
            event_type=event_type,
            emitted_payload=payload,
        )

    def expire_orders(
        self,
        *,
        reference_time: datetime,
    ) -> tuple[OmsRuntimeUpdate, ...]:
        """Переоценить lifecycle truth относительно reference time."""
        self._ensure_started("expire_orders")
        updates: list[OmsRuntimeUpdate] = []
        for key, record in tuple(self._active_orders.items()):
            if not record.freshness.is_expired_at(reference_time):
                continue
            expired_record = self._build_transitioned_record(
                record=record,
                target_status=OmsLifecycleStatus.EXPIRED,
                reference_time=reference_time,
                reason_code=OmsReasonCode.ORDER_EXPIRED,
            )
            self._store_transitioned_record(key=key, record=expired_record)
            context = self._contexts[key]
            payload = OmsOrderPayload.from_record(expired_record)
            self._refresh_diagnostics_for_context(
                context=context,
                order_record=expired_record,
                event_type=OmsEventType.OMS_ORDER_EXPIRED,
                lifecycle_state=OmsRuntimeLifecycleState.READY,
                ready=True,
                readiness_reasons=(),
                degraded_reasons=tuple(self._diagnostics.degraded_reasons),
            )
            updates.append(
                OmsRuntimeUpdate(
                    context=context,
                    order_record=expired_record,
                    event_type=OmsEventType.OMS_ORDER_EXPIRED,
                    emitted_payload=payload,
                )
            )
        return tuple(updates)

    def mark_degraded(self, reason: str) -> None:
        """Зафиксировать деградацию ingest/runtime path."""
        self._refresh_diagnostics(
            lifecycle_state=OmsRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=reason,
            degraded_reasons=(reason,),
            readiness_reasons=("runtime_degraded",),
        )

    def get_context(self, *, intent_id: UUID) -> OmsContext | None:
        """Вернуть последний assembled OMS context по execution intent."""
        key = self._order_key_by_intent_id.get(intent_id)
        if key is None:
            return None
        return self._contexts.get(key)

    def get_active_order(self, *, oms_order_id: UUID) -> OmsOrderRecord | None:
        """Вернуть текущий active OMS order-state."""
        key = self._order_key_by_id.get(oms_order_id)
        if key is None:
            return None
        return self._active_orders.get(key)

    def get_historical_order(self, *, oms_order_id: UUID) -> OmsOrderRecord | None:
        """Вернуть historical OMS order-state."""
        key = self._order_key_by_id.get(oms_order_id)
        if key is None:
            return None
        return self._historical_orders.get(key)

    def get_order_by_intent(
        self,
        *,
        intent_id: UUID,
        query_scope: OmsQueryScope = OmsQueryScope.ALL,
    ) -> OmsOrderRecord | None:
        """Вернуть OMS order-state по upstream execution intent."""
        key = self._order_key_by_intent_id.get(intent_id)
        if key is None:
            return None
        if query_scope in {OmsQueryScope.ACTIVE, OmsQueryScope.ALL}:
            active = self._active_orders.get(key)
            if active is not None:
                return active
        if query_scope in {OmsQueryScope.HISTORICAL, OmsQueryScope.ALL}:
            historical = self._historical_orders.get(key)
            if historical is not None:
                return historical
        return None

    def list_active_orders(self) -> tuple[OmsOrderRecord, ...]:
        """Вернуть active order-state truth."""
        return tuple(self._active_orders.values())

    def list_historical_orders(self) -> tuple[OmsOrderRecord, ...]:
        """Вернуть historical order-state truth."""
        return tuple(self._historical_orders.values())

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-visible diagnostics."""
        return self._diagnostics.to_dict()

    def _assemble_oms_context(
        self,
        *,
        intent: ExecutionOrderIntent,
        reference_time: datetime,
        metadata: dict[str, object] | None,
    ) -> OmsContext:
        observed_inputs = 1
        required_inputs = 1
        missing_inputs: list[str] = []
        invalid_reason: str | None = None

        if (
            intent.freshness.is_expired_at(reference_time)
            or intent.status == ExecutionStatus.EXPIRED
        ):
            invalid_reason = "execution_intent_expired"
        elif intent.status == ExecutionStatus.INVALIDATED:
            invalid_reason = "execution_intent_invalidated"
        elif intent.is_executable:
            pass
        else:
            missing_inputs.append("executable_execution_intent")

        if invalid_reason is not None:
            validity = OmsValidity(
                status=OmsValidityStatus.INVALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
                invalid_reason=invalid_reason,
            )
        elif missing_inputs:
            validity = OmsValidity(
                status=OmsValidityStatus.WARMING,
                observed_inputs=observed_inputs - len(missing_inputs),
                required_inputs=required_inputs,
                missing_inputs=tuple(missing_inputs),
            )
        else:
            validity = OmsValidity(
                status=OmsValidityStatus.VALID,
                observed_inputs=observed_inputs,
                required_inputs=required_inputs,
            )

        context_metadata: dict[str, object] = {
            "execution_status": intent.status.value,
            "execution_name": intent.execution_name,
        }
        if metadata:
            context_metadata.update(metadata)

        return OmsContext(
            oms_name=self.config.oms_name,
            contour_name=self.config.contour_name,
            symbol=intent.symbol,
            exchange=intent.exchange,
            timeframe=intent.timeframe,
            observed_at=reference_time,
            source=OmsSource.EXECUTION,
            intent=intent,
            validity=validity,
            metadata=context_metadata,
        )

    def _build_record_freshness(
        self,
        *,
        intent: ExecutionOrderIntent,
        reference_time: datetime,
    ) -> OmsFreshness:
        bounded_expires_at = reference_time + timedelta(seconds=self.config.max_order_age_seconds)
        if intent.freshness.expires_at is None:
            expires_at = bounded_expires_at
        else:
            expires_at = min(intent.freshness.expires_at, bounded_expires_at)
        return OmsFreshness(
            generated_at=reference_time,
            expires_at=expires_at,
        )

    def _build_state_key_from_context(self, context: OmsContext) -> OmsStateKey:
        return (
            context.exchange,
            context.symbol,
            context.timeframe,
            self.config.contour_name,
            self.config.oms_name,
            str(context.intent.intent_id),
        )

    def _register_active_record(self, *, key: OmsStateKey, record: OmsOrderRecord) -> None:
        self._active_orders[key] = record
        self._order_key_by_id[record.oms_order_id] = key
        assert record.originating_intent_id is not None
        self._order_key_by_intent_id[record.originating_intent_id] = key

    def _store_transitioned_record(self, *, key: OmsStateKey, record: OmsOrderRecord) -> None:
        self._order_key_by_id[record.oms_order_id] = key
        assert record.originating_intent_id is not None
        self._order_key_by_intent_id[record.originating_intent_id] = key
        if record.is_active:
            self._historical_orders.pop(key, None)
            self._active_orders[key] = record
            return
        self._active_orders.pop(key, None)
        self._historical_orders[key] = record
        self._trim_history_if_needed()

    def _build_transitioned_record(
        self,
        *,
        record: OmsOrderRecord,
        target_status: OmsLifecycleStatus,
        reference_time: datetime,
        reason_code: OmsReasonCode,
        client_order_id: str | None = None,
        external_order_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> OmsOrderRecord:
        locator = OmsOrderLocator(
            oms_order_id=record.oms_order_id,
            originating_intent_id=record.originating_intent_id,
            symbol=record.symbol,
            exchange=record.exchange,
            timeframe=record.timeframe,
            query_scope=(
                OmsQueryScope.HISTORICAL
                if target_status in self._TERMINAL_STATUSES
                else OmsQueryScope.ACTIVE
            ),
        )
        validity = record.validity
        if (
            target_status == OmsLifecycleStatus.EXPIRED
            and validity.status == OmsValidityStatus.VALID
        ):
            validity = OmsValidity(
                status=OmsValidityStatus.INVALID,
                observed_inputs=validity.observed_inputs,
                required_inputs=validity.required_inputs,
                missing_inputs=validity.missing_inputs,
                invalid_reason="oms_order_expired",
            )
        merged_metadata = record.metadata.copy()
        if metadata:
            merged_metadata.update(metadata)
        return replace(
            record,
            freshness=replace(
                record.freshness,
                generated_at=reference_time,
            ),
            validity=validity,
            lifecycle_status=target_status,
            locator=locator,
            client_order_id=client_order_id or record.client_order_id,
            external_order_id=external_order_id or record.external_order_id,
            reason_code=reason_code,
            state_version=record.state_version + 1,
            metadata=merged_metadata,
        )

    def _validate_transition(
        self,
        *,
        current: OmsLifecycleStatus,
        target: OmsLifecycleStatus,
    ) -> None:
        if target == current and target == OmsLifecycleStatus.PARTIALLY_FILLED:
            return
        if target not in self._ALLOWED_TRANSITIONS[current]:
            raise ValueError(f"Недопустимый OMS transition: {current.value} -> {target.value}")

    def _trim_history_if_needed(self) -> None:
        overflow = len(self._historical_orders) - self.config.history_retention_limit
        if overflow <= 0:
            return
        keys_to_remove = tuple(self._historical_orders.keys())[:overflow]
        for key in keys_to_remove:
            record = self._historical_orders.pop(key)
            self._order_key_by_id.pop(record.oms_order_id, None)
            if record.originating_intent_id is not None:
                self._order_key_by_intent_id.pop(record.originating_intent_id, None)
            self._contexts.pop(key, None)

    def _refresh_diagnostics_for_context(
        self,
        *,
        context: OmsContext,
        order_record: OmsOrderRecord | None,
        event_type: OmsEventType | None,
        lifecycle_state: OmsRuntimeLifecycleState,
        ready: bool,
        readiness_reasons: tuple[str, ...],
        degraded_reasons: tuple[str, ...],
        last_failure_reason: str | None = None,
    ) -> None:
        self._refresh_diagnostics(
            lifecycle_state=lifecycle_state,
            ready=ready,
            tracked_contexts=len(self._contexts),
            tracked_active_orders=len(self._active_orders),
            tracked_historical_orders=len(self._historical_orders),
            last_intent_id=str(context.intent.intent_id),
            last_order_id=str(order_record.oms_order_id) if order_record is not None else None,
            last_event_type=event_type.value if event_type is not None else None,
            last_failure_reason=last_failure_reason,
            readiness_reasons=readiness_reasons,
            degraded_reasons=degraded_reasons,
        )

    def _ensure_started(self, operation: str) -> None:
        if not self._started:
            raise RuntimeError(
                f"OmsRuntime не запущен. Операция {operation} недоступна до start()."
            )

    def _refresh_diagnostics(self, **updates: object) -> None:
        current = asdict(self._diagnostics)
        current.update(updates)
        self._diagnostics = OmsRuntimeDiagnostics(
            started=self._started,
            ready=bool(current["ready"]),
            lifecycle_state=OmsRuntimeLifecycleState(current["lifecycle_state"]),
            tracked_contexts=int(current["tracked_contexts"]),
            tracked_active_orders=int(current["tracked_active_orders"]),
            tracked_historical_orders=int(current["tracked_historical_orders"]),
            last_intent_id=current["last_intent_id"],
            last_order_id=current["last_order_id"],
            last_event_type=current["last_event_type"],
            last_failure_reason=current["last_failure_reason"],
            readiness_reasons=list(current["readiness_reasons"]),
            degraded_reasons=list(current["degraded_reasons"]),
        )
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self._diagnostics.to_dict())


def create_oms_runtime(
    config: OmsRuntimeConfig | None = None,
    *,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> OmsRuntime:
    """Фабрика explicit runtime foundation OMS layer."""
    return OmsRuntime(
        config=config,
        diagnostics_sink=diagnostics_sink,
    )


__all__ = [
    "OmsRuntime",
    "OmsRuntimeConfig",
    "OmsRuntimeDiagnostics",
    "OmsRuntimeLifecycleState",
    "OmsRuntimeUpdate",
    "OmsStateKey",
    "create_oms_runtime",
]
