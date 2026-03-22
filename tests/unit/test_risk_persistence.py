from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cryptotechnolog.core.state_machine_enums import SystemState
from cryptotechnolog.risk.models import (
    Order,
    OrderSide,
    PositionRiskRecord,
    PositionSide,
    RejectReason,
    RiskCheckResult,
    StopUpdate,
    TrailingEvaluationType,
    TrailingMode,
    TrailingState,
    TrailingTier,
)
from cryptotechnolog.risk.persistence import (
    PositionRiskLedgerAuditRecord,
    RiskCheckAuditRecord,
    RiskPersistenceRepository,
    TrailingStopMovementRecord,
    TrailingStopSnapshotRecord,
)


class FakeConnection:
    """Фиктивное соединение, которое запоминает все execute-вызовы."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, query: str, *args: object) -> str:
        self.calls.append((query, args))
        return "INSERT 1"


class FakePool:
    """Фиктивный asyncpg pool для unit-тестов repository-слоя."""

    def __init__(self) -> None:
        self.connection = FakeConnection()

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


def make_position_record() -> PositionRiskRecord:
    """Создать доменную запись позиции для persistence-тестов."""
    now = datetime(2026, 3, 19, tzinfo=UTC)
    return PositionRiskRecord(
        position_id="pos-1",
        symbol="BTC/USDT",
        side=PositionSide.LONG,
        entry_price=Decimal("100"),
        initial_stop=Decimal("95"),
        current_stop=Decimal("98"),
        quantity=Decimal("2"),
        risk_capital_usd=Decimal("10000"),
        initial_risk_usd=Decimal("10"),
        initial_risk_r=Decimal("0.001"),
        current_risk_usd=Decimal("4"),
        current_risk_r=Decimal("0.0004"),
        trailing_state=TrailingState.ACTIVE,
        opened_at=now,
        updated_at=now,
    )


def make_stop_update() -> StopUpdate:
    """Создать доменный результат trailing evaluation для persistence-тестов."""
    return StopUpdate(
        position_id="pos-1",
        old_stop=Decimal("95"),
        new_stop=Decimal("98"),
        pnl_r=Decimal("1.5"),
        evaluation_type=TrailingEvaluationType.MOVE,
        tier=TrailingTier.T1,
        mode=TrailingMode.NORMAL,
        state=SystemState.TRADING.value,
        risk_before=Decimal("0.001"),
        risk_after=Decimal("0.0004"),
        should_execute=True,
        reason="Стоп передвинут по правилам TrailingPolicy",
    )


class TestRiskPersistenceRepository:
    """Тесты persistence foundation нового risk-контура."""

    @pytest.mark.asyncio
    async def test_saves_risk_check_audit_record(self) -> None:
        """Pre-trade результат должен сохраняться как отдельная audit-запись."""
        pool = FakePool()
        repo = RiskPersistenceRepository(pool)  # type: ignore[arg-type]
        order = Order(
            order_id="ord-1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
        )
        result = RiskCheckResult(
            allowed=False,
            reason=RejectReason.MAX_TOTAL_R_EXCEEDED,
            risk_r=Decimal("0.01"),
            position_size_usd=Decimal("2000"),
            position_size_base=Decimal("20"),
            current_total_r=Decimal("0.09"),
            max_total_r=Decimal("0.10"),
            check_duration_ms=7,
            details={"projected_total_r": "0.11"},
        )
        record = RiskCheckAuditRecord.from_domain_result(
            order=order,
            result=result,
            system_state=SystemState.TRADING,
        )

        await repo.save_risk_check(record)

        query, args = pool.connection.calls[0]
        assert "INSERT INTO risk_checks" in query
        assert args[0] == "ord-1"
        assert args[2] == SystemState.TRADING.value
        assert args[3] == "REJECT"
        assert args[4] == RejectReason.MAX_TOTAL_R_EXCEEDED.value
        assert args[5] == Decimal("0.01")
        assert args[14] == {"projected_total_r": "0.11"}

    @pytest.mark.asyncio
    async def test_upserts_position_risk_record_with_new_domain_table(self) -> None:
        """Позиционный ledger должен писаться в новую таблицу, а не в legacy risk_ledger."""
        pool = FakePool()
        repo = RiskPersistenceRepository(pool)  # type: ignore[arg-type]
        record = make_position_record()

        await repo.upsert_position_risk_record(record)

        query, args = pool.connection.calls[0]
        assert "INSERT INTO position_risk_ledger" in query
        assert "ON CONFLICT (position_id) DO UPDATE" in query
        assert "INSERT INTO risk_ledger (" not in query
        assert args[0] == "pos-1"
        assert args[2] == PositionSide.LONG.value
        assert args[12] == TrailingState.ACTIVE.value

    @pytest.mark.asyncio
    async def test_appends_position_risk_audit_record(self) -> None:
        """Аудит ledger должен фиксироваться отдельной таблицей."""
        pool = FakePool()
        repo = RiskPersistenceRepository(pool)  # type: ignore[arg-type]
        old_record = make_position_record()
        new_record = replace(
            old_record,
            current_stop=Decimal("99"),
            current_risk_r=Decimal("0.0002"),
        )
        audit = PositionRiskLedgerAuditRecord.from_records(
            operation="UPDATE",
            current_record=old_record,
            next_record=new_record,
            reason="Стоп подтянут после trailing",
        )

        await repo.append_position_risk_audit(audit)

        query, args = pool.connection.calls[0]
        assert "INSERT INTO position_risk_ledger_audit" in query
        assert args[0] == "pos-1"
        assert args[2] == "UPDATE"
        assert args[3] == Decimal("98")
        assert args[4] == Decimal("99")

    @pytest.mark.asyncio
    async def test_upserts_trailing_stop_snapshot(self) -> None:
        """Текущий trailing snapshot должен сохраняться отдельно от истории движений."""
        pool = FakePool()
        repo = RiskPersistenceRepository(pool)  # type: ignore[arg-type]
        snapshot = TrailingStopSnapshotRecord.from_stop_update(
            symbol="BTC/USDT",
            update=make_stop_update(),
            trailing_state=TrailingState.ACTIVE.value,
            evaluated_at=datetime(2026, 3, 19, tzinfo=UTC),
        )

        await repo.upsert_trailing_stop_snapshot(snapshot)

        query, args = pool.connection.calls[0]
        assert "INSERT INTO trailing_stops" in query
        assert "ON CONFLICT (position_id) DO UPDATE" in query
        assert args[0] == "pos-1"
        assert args[4] == TrailingState.ACTIVE.value
        assert args[5] == TrailingEvaluationType.MOVE.value
        assert args[6] == TrailingTier.T1.value
        assert args[7] == TrailingMode.NORMAL.value

    @pytest.mark.asyncio
    async def test_appends_trailing_stop_movement_audit(self) -> None:
        """История trailing должна писаться отдельным audit trail."""
        pool = FakePool()
        repo = RiskPersistenceRepository(pool)  # type: ignore[arg-type]
        movement = TrailingStopMovementRecord.from_stop_update(
            symbol="BTC/USDT",
            update=make_stop_update(),
            created_at=datetime(2026, 3, 19, tzinfo=UTC),
        )

        await repo.append_trailing_stop_movement(movement)

        query, args = pool.connection.calls[0]
        assert "INSERT INTO trailing_stop_movements" in query
        assert args[0] == "pos-1"
        assert args[5] == TrailingEvaluationType.MOVE.value
        assert args[6] == TrailingTier.T1.value
        assert args[11] is True


class TestRiskPersistenceMigration:
    """Тесты структуры migration foundation для нового risk persistence слоя."""

    def test_migration_contains_new_risk_engine_tables(self) -> None:
        """Миграция должна создавать новые таблицы risk persistence foundation."""
        migration = Path("scripts/migrations/011_risk_engine_foundation.sql").read_text(
            encoding="utf-8"
        )

        assert "CREATE TABLE IF NOT EXISTS risk_checks" in migration
        assert "CREATE TABLE IF NOT EXISTS position_risk_ledger" in migration
        assert "CREATE TABLE IF NOT EXISTS position_risk_ledger_audit" in migration
        assert "CREATE TABLE IF NOT EXISTS trailing_stops" in migration
        assert "CREATE TABLE IF NOT EXISTS trailing_stop_movements" in migration

    def test_migration_uses_new_position_ledger_not_legacy_table(self) -> None:
        """Новый persistence foundation не должен объявлять legacy risk_ledger повторно."""
        migration = Path("scripts/migrations/011_risk_engine_foundation.sql").read_text(
            encoding="utf-8"
        )

        assert "CREATE TABLE IF NOT EXISTS risk_ledger (" not in migration
        assert "Новый позиционный ledger риска Фазы 5" in migration
