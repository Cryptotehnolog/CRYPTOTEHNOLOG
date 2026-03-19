from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.core.event import Event, SystemEventType
from cryptotechnolog.core.state_machine_enums import SystemState
from cryptotechnolog.risk.correlation import CorrelationEvaluator
from cryptotechnolog.risk.drawdown_monitor import DrawdownMonitor
from cryptotechnolog.risk.engine import PreTradeContext, RiskEngine, RiskEngineConfig
from cryptotechnolog.risk.listeners import RiskEngineListener, RiskEngineListenerConfig
from cryptotechnolog.risk.models import Order, OrderSide
from cryptotechnolog.risk.portfolio_state import PortfolioState
from cryptotechnolog.risk.position_sizing import PositionSizer
from cryptotechnolog.risk.risk_ledger import RiskLedger
from cryptotechnolog.risk.trailing_policy import TrailingPolicy

if TYPE_CHECKING:
    from cryptotechnolog.risk.persistence_contracts import (
        PositionRiskLedgerAuditRecord,
        RiskCheckAuditRecord,
        TrailingStopMovementRecord,
        TrailingStopSnapshotRecord,
    )


class InMemoryRiskRepository:
    """Памятный repository для тестов optional persistence integration."""

    def __init__(self) -> None:
        self.risk_checks: list[RiskCheckAuditRecord] = []
        self.position_snapshots: dict[str, object] = {}
        self.position_audits: list[PositionRiskLedgerAuditRecord] = []
        self.trailing_snapshots: dict[str, TrailingStopSnapshotRecord] = {}
        self.trailing_movements: list[TrailingStopMovementRecord] = []
        self.deleted_positions: list[str] = []
        self.deleted_trailing_snapshots: list[str] = []

    async def save_risk_check(self, record: RiskCheckAuditRecord) -> None:
        self.risk_checks.append(record)

    async def upsert_position_risk_record(self, record: object) -> None:
        position_id = record.position_id  # type: ignore[attr-defined]
        self.position_snapshots[position_id] = record

    async def append_position_risk_audit(self, record: PositionRiskLedgerAuditRecord) -> None:
        self.position_audits.append(record)

    async def upsert_trailing_stop_snapshot(self, record: TrailingStopSnapshotRecord) -> None:
        self.trailing_snapshots[record.position_id] = record

    async def append_trailing_stop_movement(self, record: TrailingStopMovementRecord) -> None:
        self.trailing_movements.append(record)

    async def delete_position_risk_record(self, position_id: str) -> None:
        self.deleted_positions.append(position_id)
        self.position_snapshots.pop(position_id, None)

    async def delete_trailing_stop_snapshot(self, position_id: str) -> None:
        self.deleted_trailing_snapshots.append(position_id)
        self.trailing_snapshots.pop(position_id, None)


class BrokenUpdateLedger(RiskLedger):
    """Тестовый ledger, который блокирует синхронизацию stop move."""

    def update_position_risk(self, **kwargs):  # type: ignore[override]
        new_stop = kwargs["new_stop"]
        position_id = kwargs["position_id"]
        current_record = self.get_position_record(position_id)
        if new_stop != current_record.current_stop:
            raise RuntimeError("simulated ledger sync failure")
        return super().update_position_risk(**kwargs)


def make_engine(
    *,
    repository: InMemoryRiskRepository | None = None,
    ledger: RiskLedger | None = None,
) -> RiskEngine:
    """Собрать RiskEngine с optional repository integration для тестов."""
    resolved_ledger = ledger or RiskLedger()
    return RiskEngine(
        config=RiskEngineConfig(
            base_r_percent=Decimal("0.01"),
            max_r_per_trade=Decimal("0.02"),
            max_total_r=Decimal("0.10"),
            max_total_exposure_usd=Decimal("100000"),
            max_position_size=Decimal("100000"),
            quantity_step=Decimal("0.01"),
            price_precision=Decimal("0.01"),
            risk_precision=Decimal("0.00000001"),
        ),
        correlation_evaluator=CorrelationEvaluator(),
        position_sizer=PositionSizer(),
        portfolio_state=PortfolioState(),
        drawdown_monitor=DrawdownMonitor(starting_equity=Decimal("10000")),
        risk_ledger=resolved_ledger,
        trailing_policy=TrailingPolicy(resolved_ledger),
        persistence_repository=repository,
    )


def make_order() -> Order:
    """Создать валидный ордер для pre-trade проверки."""
    return Order(
        order_id="ord-1",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
    )


def make_order_filled_event() -> Event:
    """Создать ORDER_FILLED с достаточным payload."""
    return Event.new(
        SystemEventType.ORDER_FILLED,
        "EXECUTION_CORE",
        {
            "position_id": "pos-1",
            "symbol": "BTC/USDT",
            "side": "buy",
            "filled_qty": "2",
            "avg_price": "100",
            "stop_loss": "95",
            "risk_capital_usd": "10000",
        },
    )


def make_position_closed_event() -> Event:
    """Создать POSITION_CLOSED с достаточным payload."""
    return Event.new(
        "POSITION_CLOSED",
        "EXECUTION_CORE",
        {
            "position_id": "pos-1",
            "symbol": "BTC/USDT",
            "realized_pnl_r": "1.2",
            "current_equity": "10120",
        },
    )


def make_bar_completed_event() -> Event:
    """Создать BAR_COMPLETED для trailing evaluation."""
    return Event.new(
        "BAR_COMPLETED",
        "MARKET_DATA",
        {
            "symbol": "BTC/USDT",
            "mark_price": "110",
            "best_bid": "109.8",
            "best_ask": "110.2",
            "atr": "2",
            "adx": "20",
            "confirmed_highs": 0,
            "confirmed_lows": 0,
            "is_stale": False,
        },
    )


@pytest.mark.asyncio
class TestRiskEnginePersistenceIntegration:
    """Тесты optional repository integration для основного risk loop."""

    async def test_check_trade_with_audit_persists_pre_trade_record(self) -> None:
        """Pre-trade path должен писать audit при подключённом repository."""
        repository = InMemoryRiskRepository()
        engine = make_engine(repository=repository)

        result = await engine.check_trade_with_audit(
            make_order(),
            PreTradeContext(
                system_state=SystemState.TRADING,
                current_equity=Decimal("10000"),
            ),
        )

        assert result.allowed is True
        assert len(repository.risk_checks) == 1
        audit_record = repository.risk_checks[0]
        assert audit_record.order_id == "ord-1"
        assert audit_record.decision == "ALLOW"
        assert audit_record.system_state == SystemState.TRADING.value

    async def test_check_trade_without_repository_remains_valid(self) -> None:
        """RiskEngine должен продолжать работать без persistence repository."""
        engine = make_engine(repository=None)

        result = await engine.check_trade_with_audit(
            make_order(),
            PreTradeContext(
                system_state=SystemState.TRADING,
                current_equity=Decimal("10000"),
            ),
        )

        assert result.allowed is True
        assert engine.has_persistence_repository is False

    async def test_order_filled_persists_position_snapshot_and_register_audit(self) -> None:
        """ORDER_FILLED должен писать snapshot и audit регистрации позиции."""
        repository = InMemoryRiskRepository()
        engine = make_engine(repository=repository)
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        listener = RiskEngineListener(
            risk_engine=engine,
            publisher=bus.publish,
            config=RiskEngineListenerConfig(name="risk_listener_repo_order"),
        )
        bus.register_listener(listener)

        await bus.publish(make_order_filled_event())

        assert "pos-1" in repository.position_snapshots
        assert len(repository.position_audits) == 1
        assert repository.position_audits[0].operation == "REGISTER"

        bus.unregister_listener(listener.name)
        await bus.shutdown()

    async def test_position_closed_persists_release_audit_and_cleans_snapshots(self) -> None:
        """POSITION_CLOSED должен писать release audit и удалять active snapshots."""
        repository = InMemoryRiskRepository()
        engine = make_engine(repository=repository)
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        listener = RiskEngineListener(
            risk_engine=engine,
            publisher=bus.publish,
            config=RiskEngineListenerConfig(name="risk_listener_repo_close"),
        )
        bus.register_listener(listener)

        await bus.publish(make_order_filled_event())
        await bus.publish(make_bar_completed_event())
        await bus.publish(make_position_closed_event())

        assert any(audit.operation == "TERMINATE" for audit in repository.position_audits)
        assert repository.position_audits[-1].operation == "RELEASE"
        assert "pos-1" in repository.deleted_positions
        assert "pos-1" in repository.deleted_trailing_snapshots

        bus.unregister_listener(listener.name)
        await bus.shutdown()

    async def test_bar_completed_persists_successful_trailing_audit(self) -> None:
        """Успешный trailing move должен писать movement, snapshot и ledger audit."""
        repository = InMemoryRiskRepository()
        engine = make_engine(repository=repository)
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        listener = RiskEngineListener(
            risk_engine=engine,
            publisher=bus.publish,
            config=RiskEngineListenerConfig(name="risk_listener_repo_bar"),
        )
        bus.register_listener(listener)

        await bus.publish(make_order_filled_event())
        await bus.publish(make_bar_completed_event())

        assert len(repository.trailing_movements) == 1
        assert repository.trailing_movements[0].should_execute is True
        assert repository.trailing_movements[0].evaluation_type == "MOVE"
        assert repository.trailing_movements[0].new_stop == Decimal("107.0")
        assert repository.trailing_snapshots["pos-1"].current_stop == Decimal("107.0")
        assert repository.trailing_snapshots["pos-1"].last_evaluation_type == "MOVE"
        assert repository.position_audits[-1].operation == "UPDATE"

        bus.unregister_listener(listener.name)
        await bus.shutdown()

    async def test_bar_completed_persists_blocked_trailing_audit(self) -> None:
        """Заблокированный trailing move должен всё равно попадать в trailing audit."""
        repository = InMemoryRiskRepository()
        engine = make_engine(repository=repository, ledger=BrokenUpdateLedger())
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        listener = RiskEngineListener(
            risk_engine=engine,
            publisher=bus.publish,
            config=RiskEngineListenerConfig(name="risk_listener_repo_blocked"),
        )
        bus.register_listener(listener)

        await bus.publish(make_order_filled_event())
        await bus.publish(make_bar_completed_event())

        assert len(repository.trailing_movements) == 1
        assert repository.trailing_movements[0].should_execute is False
        assert repository.trailing_movements[0].evaluation_type == "BLOCKED"
        assert "ошибка синхронизации" in repository.trailing_movements[0].reason
        assert repository.trailing_snapshots["pos-1"].current_stop == Decimal("95")
        assert repository.trailing_snapshots["pos-1"].last_evaluation_type == "BLOCKED"
        assert len(repository.position_audits) == 1
        assert repository.position_audits[0].operation == "REGISTER"

        bus.unregister_listener(listener.name)
        await bus.shutdown()
