"""
Контракты persistence integration для Risk Engine.

Модуль намеренно не зависит от `asyncpg` и не содержит
конкретной инфраструктурной реализации repository.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from cryptotechnolog.core.state_machine_enums import SystemState

if TYPE_CHECKING:
    from decimal import Decimal

    from .models import Order, PositionRiskRecord, RiskCheckResult, StopUpdate


class IRiskPersistenceRepository(Protocol):
    """Протокол optional repository integration для RiskEngine."""

    async def save_risk_check(self, record: RiskCheckAuditRecord) -> None:
        """Сохранить audit-запись pre-trade проверки."""

    async def upsert_position_risk_record(self, record: PositionRiskRecord) -> None:
        """Сохранить или обновить snapshot позиционного risk ledger."""

    async def append_position_risk_audit(self, record: PositionRiskLedgerAuditRecord) -> None:
        """Добавить audit-запись изменения позиционного ledger."""

    async def upsert_trailing_stop_snapshot(self, record: TrailingStopSnapshotRecord) -> None:
        """Сохранить snapshot trailing stop."""

    async def append_trailing_stop_movement(self, record: TrailingStopMovementRecord) -> None:
        """Сохранить audit-запись оценки/движения trailing stop."""

    async def delete_position_risk_record(self, position_id: str) -> None:
        """Удалить snapshot закрытой позиции из position_risk_ledger."""

    async def delete_trailing_stop_snapshot(self, position_id: str) -> None:
        """Удалить trailing snapshot закрытой позиции."""


@dataclass(slots=True, frozen=True)
class RiskCheckAuditRecord:
    """Audit-запись результата pre-trade risk check."""

    order_id: str | None
    symbol: str | None
    system_state: str
    decision: str
    reason: str
    risk_r: Decimal
    position_size_usd: Decimal
    position_size_base: Decimal
    current_total_r: Decimal
    max_total_r: Decimal
    correlation_with_portfolio: Decimal | None
    recommended_exchange: str | None
    max_size: Decimal | None
    check_duration_ms: int
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_domain_result(
        cls,
        *,
        order: Order,
        result: RiskCheckResult,
        system_state: SystemState | str,
    ) -> RiskCheckAuditRecord:
        """Построить audit-запись из доменного результата pre-trade проверки."""
        state_value = system_state.value if isinstance(system_state, SystemState) else system_state
        decision = "ALLOW" if result.allowed else "REJECT"
        return cls(
            order_id=order.order_id,
            symbol=order.symbol,
            system_state=state_value,
            decision=decision,
            reason=result.reason.value if hasattr(result.reason, "value") else str(result.reason),
            risk_r=result.risk_r,
            position_size_usd=result.position_size_usd,
            position_size_base=result.position_size_base,
            current_total_r=result.current_total_r,
            max_total_r=result.max_total_r,
            correlation_with_portfolio=result.correlation_with_portfolio,
            recommended_exchange=result.recommended_exchange,
            max_size=result.max_size,
            check_duration_ms=result.check_duration_ms,
            details=dict(result.details),
        )


@dataclass(slots=True, frozen=True)
class PositionRiskLedgerAuditRecord:
    """Audit-запись изменения позиционного `position_risk_ledger`."""

    position_id: str
    symbol: str
    operation: str
    old_stop: Decimal | None
    new_stop: Decimal | None
    old_risk_r: Decimal | None
    new_risk_r: Decimal | None
    trailing_state: str | None
    reason: str | None
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_records(
        cls,
        *,
        operation: str,
        current_record: PositionRiskRecord | None,
        next_record: PositionRiskRecord | None,
        reason: str | None = None,
    ) -> PositionRiskLedgerAuditRecord:
        """Собрать audit-запись из перехода old -> new записи ledger."""
        record = next_record or current_record
        if record is None:
            raise ValueError("Для audit-записи ledger нужна хотя бы одна запись позиции")

        return cls(
            position_id=record.position_id,
            symbol=record.symbol,
            operation=operation,
            old_stop=current_record.current_stop if current_record is not None else None,
            new_stop=next_record.current_stop if next_record is not None else None,
            old_risk_r=current_record.current_risk_r if current_record is not None else None,
            new_risk_r=next_record.current_risk_r if next_record is not None else None,
            trailing_state=(
                next_record.trailing_state.value
                if next_record is not None
                else current_record.trailing_state.value
                if current_record is not None
                else None
            ),
            reason=reason,
        )


@dataclass(slots=True, frozen=True)
class TrailingStopSnapshotRecord:
    """Текущий snapshot trailing stop по позиции."""

    position_id: str
    symbol: str
    current_stop: Decimal
    previous_stop: Decimal
    trailing_state: str
    last_evaluation_type: str
    last_tier: str
    last_mode: str
    last_pnl_r: Decimal
    last_risk_before: Decimal
    last_risk_after: Decimal
    last_reason: str
    last_evaluated_at: datetime
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_stop_update(
        cls,
        *,
        symbol: str,
        update: StopUpdate,
        trailing_state: str,
        evaluated_at: datetime | None = None,
    ) -> TrailingStopSnapshotRecord:
        """Построить snapshot trailing stop из доменного `StopUpdate`."""
        timestamp = evaluated_at or datetime.now(UTC)
        return cls(
            position_id=update.position_id,
            symbol=symbol,
            current_stop=update.new_stop,
            previous_stop=update.old_stop,
            trailing_state=trailing_state,
            last_evaluation_type=update.evaluation_type.value,
            last_tier=update.tier.value,
            last_mode=update.mode.value,
            last_pnl_r=update.pnl_r,
            last_risk_before=update.risk_before,
            last_risk_after=update.risk_after,
            last_reason=update.reason,
            last_evaluated_at=timestamp,
            updated_at=timestamp,
        )


@dataclass(slots=True, frozen=True)
class TrailingStopMovementRecord:
    """Audit-запись отдельной оценки/движения trailing stop."""

    position_id: str
    symbol: str
    old_stop: Decimal
    new_stop: Decimal
    pnl_r: Decimal
    evaluation_type: str
    tier: str
    mode: str
    system_state: str
    risk_before: Decimal
    risk_after: Decimal
    should_execute: bool
    reason: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_stop_update(
        cls,
        *,
        symbol: str,
        update: StopUpdate,
        created_at: datetime | None = None,
    ) -> TrailingStopMovementRecord:
        """Построить audit-запись истории trailing из доменного `StopUpdate`."""
        return cls(
            position_id=update.position_id,
            symbol=symbol,
            old_stop=update.old_stop,
            new_stop=update.new_stop,
            pnl_r=update.pnl_r,
            evaluation_type=update.evaluation_type.value,
            tier=update.tier.value,
            mode=update.mode.value,
            system_state=update.state,
            risk_before=update.risk_before,
            risk_after=update.risk_after,
            should_execute=update.should_execute,
            reason=update.reason,
            created_at=created_at or datetime.now(UTC),
        )
