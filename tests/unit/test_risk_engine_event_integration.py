from __future__ import annotations

from decimal import Decimal

import pytest

from cryptotechnolog.core.enhanced_event_bus import EnhancedEventBus
from cryptotechnolog.core.event import Event, SystemEventType
from cryptotechnolog.core.state_machine_enums import SystemState
from cryptotechnolog.risk.correlation import CorrelationEvaluator
from cryptotechnolog.risk.drawdown_monitor import DrawdownMonitor
from cryptotechnolog.risk.engine import RiskEngine, RiskEngineConfig, RiskEngineEventType
from cryptotechnolog.risk.listeners import RiskEngineListener, RiskEngineListenerConfig
from cryptotechnolog.risk.portfolio_state import PortfolioState
from cryptotechnolog.risk.position_sizing import PositionSizer
from cryptotechnolog.risk.risk_ledger import RiskLedger
from cryptotechnolog.risk.trailing_policy import TrailingPolicy


class BrokenUpdateLedger(RiskLedger):
    """Тестовый ledger, который блокирует синхронизацию движения стопа."""

    def update_position_risk(self, **kwargs):  # type: ignore[override]
        new_stop = kwargs["new_stop"]
        position_id = kwargs["position_id"]
        current_record = self.get_position_record(position_id)
        if new_stop != current_record.current_stop:
            raise RuntimeError("simulated ledger sync failure")
        return super().update_position_risk(**kwargs)


def make_engine(*, ledger: RiskLedger | None = None) -> RiskEngine:
    """Собрать тестовый RiskEngine для event-driven integration сценариев."""
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
    )


def make_order_filled_event() -> Event:
    """Создать ORDER_FILLED с доменно достаточным payload."""
    return Event.new(
        SystemEventType.ORDER_FILLED,
        "EXECUTION_CORE",
        {
            "position_id": "pos-1",
            "symbol": "BTC/USDT",
            "exchange": "okx",
            "side": "buy",
            "filled_qty": "2",
            "avg_price": "100",
            "stop_loss": "95",
            "risk_capital_usd": "10000",
        },
    )


def make_order_submitted_event(
    *,
    order_id: str = "ord-1",
    symbol: str = "BTC/USDT",
    side: str = "buy",
    price: str = "100",
    stop_loss: str = "95",
    current_equity: str = "10000",
    system_state: str = SystemState.TRADING.value,
) -> Event:
    """Создать ORDER_SUBMITTED для pre-trade проверки нового risk path."""
    return Event.new(
        SystemEventType.ORDER_SUBMITTED,
        "EXECUTION_CORE",
        {
            "order_id": order_id,
            "symbol": symbol,
            "exchange": "okx",
            "side": side,
            "price": price,
            "stop_loss": stop_loss,
            "current_equity": current_equity,
            "system_state": system_state,
        },
    )


def make_bar_completed_event(
    *,
    mark_price: str = "110",
    best_bid: str = "109.8",
    best_ask: str = "110.2",
    atr: str = "2",
    adx: str = "20",
    confirmed_highs: int = 0,
    confirmed_lows: int = 0,
    structural_stop: str | None = None,
    is_stale: bool = False,
) -> Event:
    """Создать RISK_BAR_COMPLETED с данными для trailing evaluation."""
    payload: dict[str, object] = {
        "symbol": "BTC/USDT",
        "mark_price": mark_price,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "atr": atr,
        "adx": adx,
        "confirmed_highs": confirmed_highs,
        "confirmed_lows": confirmed_lows,
        "is_stale": is_stale,
    }
    if structural_stop is not None:
        payload["structural_stop"] = structural_stop
    return Event.new(SystemEventType.RISK_BAR_COMPLETED, "RISK_ENGINE", payload)


def make_state_transition_event(*, to_state: SystemState, from_state: SystemState) -> Event:
    """Создать STATE_TRANSITION для RiskEngine."""
    return Event.new(
        SystemEventType.STATE_TRANSITION,
        "STATE_MACHINE",
        {
            "from_state": from_state.value,
            "to_state": to_state.value,
        },
    )


def make_position_closed_event() -> Event:
    """Создать POSITION_CLOSED с минимально нужным payload."""
    return Event.new(
        "POSITION_CLOSED",
        "EXECUTION_CORE",
        {
            "position_id": "pos-1",
            "symbol": "BTC/USDT",
            "exit_price": "107.50",
            "exit_reason": "take_profit",
            "realized_pnl_r": "1.5",
            "realized_pnl_usd": "150",
            "realized_pnl_percent": "3.0",
            "current_equity": "10150",
        },
    )


@pytest.mark.asyncio
class TestRiskEngineEventIntegration:
    """Integration-сценарии event-driven слоя RiskEngine поверх реального EventBus."""

    async def test_order_submitted_publishes_reject_and_violation_events(self) -> None:
        """Pre-trade reject должен публиковать ORDER_REJECTED и RISK_VIOLATION."""
        engine = make_engine()
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        rejected_events: list[Event] = []
        violation_events: list[Event] = []
        bus.on(RiskEngineEventType.ORDER_REJECTED, rejected_events.append)
        bus.on(RiskEngineEventType.RISK_VIOLATION, violation_events.append)
        listener = RiskEngineListener(
            risk_engine=engine,
            publisher=bus.publish,
            config=RiskEngineListenerConfig(name="risk_listener_order_submitted"),
        )
        bus.register_listener(listener)

        await bus.publish(make_order_submitted_event(stop_loss="100"))

        assert len(rejected_events) == 1
        assert rejected_events[0].payload["reject_reason"] == "entry_equals_stop"
        assert len(violation_events) == 1
        assert violation_events[0].payload["violation_type"] == "entry_equals_stop"
        assert violation_events[0].payload["limit_type"] == "risk_check"

        bus.unregister_listener(listener.name)
        await bus.shutdown()

    async def test_order_submitted_hard_drawdown_publishes_alert_contract(self) -> None:
        """Hard drawdown reject должен публиковать drawdown escalation event."""
        engine = make_engine()
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        drawdown_events: list[Event] = []
        bus.on(RiskEngineEventType.DRAWDOWN_ALERT, drawdown_events.append)
        listener = RiskEngineListener(
            risk_engine=engine,
            publisher=bus.publish,
            config=RiskEngineListenerConfig(name="risk_listener_drawdown_alert"),
        )
        bus.register_listener(listener)

        await bus.publish(make_order_submitted_event(order_id="ord-dd-1", current_equity="8900"))

        assert len(drawdown_events) == 1
        assert drawdown_events[0].payload["reason"] == "drawdown_hard_limit_exceeded"
        assert drawdown_events[0].payload["drawdown_level"] == "hard"

        bus.unregister_listener(listener.name)
        await bus.shutdown()

    async def test_order_submitted_velocity_drawdown_publishes_killswitch_event(self) -> None:
        """Velocity drawdown reject должен публиковать critical killswitch signal."""
        engine = make_engine()
        engine._drawdown_monitor.record_trade_result(Decimal("-1.2"))
        engine._drawdown_monitor.record_trade_result(Decimal("-0.9"))
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        critical_events: list[Event] = []
        bus.on(RiskEngineEventType.VELOCITY_KILLSWITCH_TRIGGERED, critical_events.append)
        listener = RiskEngineListener(
            risk_engine=engine,
            publisher=bus.publish,
            config=RiskEngineListenerConfig(name="risk_listener_velocity_killswitch"),
        )
        bus.register_listener(listener)

        await bus.publish(make_order_submitted_event(order_id="ord-vel-1"))

        assert len(critical_events) == 1
        assert critical_events[0].priority.value == "critical"
        assert critical_events[0].payload["reason"] == "velocity_drawdown_triggered"
        assert critical_events[0].payload["drawdown_level"] == "velocity"

        bus.unregister_listener(listener.name)
        await bus.shutdown()

    async def test_order_filled_registers_position_and_publishes_risk_event(self) -> None:
        """ORDER_FILLED должен регистрировать позицию и публиковать risk event."""
        engine = make_engine()
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        published_events: list[Event] = []
        bus.on(RiskEngineEventType.RISK_POSITION_REGISTERED, published_events.append)
        listener = RiskEngineListener(
            risk_engine=engine,
            publisher=bus.publish,
            config=RiskEngineListenerConfig(name="risk_listener_order_filled"),
        )
        bus.register_listener(listener)

        await bus.publish(make_order_filled_event())

        record = engine._risk_ledger.get_position_record("pos-1")
        portfolio_record = engine._portfolio_state.get_position("pos-1")

        assert record.position_id == "pos-1"
        assert portfolio_record.position_id == "pos-1"
        assert len(published_events) == 1
        assert published_events[0].event_type == RiskEngineEventType.RISK_POSITION_REGISTERED
        assert published_events[0].payload["position_id"] == "pos-1"

        bus.unregister_listener(listener.name)
        await bus.shutdown()

    async def test_position_closed_releases_risk_and_publishes_release_event(self) -> None:
        """POSITION_CLOSED должен освобождать риск и удалять позицию из snapshot."""
        engine = make_engine()
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        published_events: list[Event] = []
        bus.on(RiskEngineEventType.RISK_POSITION_RELEASED, published_events.append)
        listener = RiskEngineListener(
            risk_engine=engine,
            publisher=bus.publish,
            config=RiskEngineListenerConfig(name="risk_listener_position_closed"),
        )
        bus.register_listener(listener)

        await bus.publish(make_order_filled_event())
        await bus.publish(make_position_closed_event())

        assert engine._risk_ledger.get_total_risk_r() == Decimal("0")
        assert engine._portfolio_state.snapshot().position_count == 0
        assert len(published_events) == 1
        assert published_events[0].payload["position_id"] == "pos-1"

        bus.unregister_listener(listener.name)
        await bus.shutdown()

    async def test_bar_completed_triggers_trailing_and_publishes_stop_move(self) -> None:
        """RISK_BAR_COMPLETED должен запускать trailing evaluation для открытой позиции."""
        engine = make_engine()
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        published_events: list[Event] = []
        bus.on(RiskEngineEventType.TRAILING_STOP_MOVED, published_events.append)
        listener = RiskEngineListener(
            risk_engine=engine,
            publisher=bus.publish,
            config=RiskEngineListenerConfig(name="risk_listener_bar_completed"),
        )
        bus.register_listener(listener)

        await bus.publish(make_order_filled_event())
        await bus.publish(make_bar_completed_event())

        record = engine._risk_ledger.get_position_record("pos-1")
        portfolio_record = engine._portfolio_state.get_position("pos-1")

        assert record.current_stop == Decimal("107.0")
        assert portfolio_record.current_stop == Decimal("107.0")
        assert len(published_events) == 1
        assert published_events[0].payload["new_stop"] == "107.0"
        assert published_events[0].payload["mode"] == "NORMAL"

        bus.unregister_listener(listener.name)
        await bus.shutdown()

    async def test_market_data_bar_completed_boundary_does_not_trigger_risk_listener(self) -> None:
        """Сырой market-data BAR_COMPLETED не должен активировать risk trailing path."""
        engine = make_engine()
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        published_events: list[Event] = []
        bus.on(RiskEngineEventType.TRAILING_STOP_MOVED, published_events.append)
        listener = RiskEngineListener(
            risk_engine=engine,
            publisher=bus.publish,
            config=RiskEngineListenerConfig(name="risk_listener_market_data_boundary"),
        )
        bus.register_listener(listener)

        await bus.publish(make_order_filled_event())
        await bus.publish(
            Event.new(
                SystemEventType.BAR_COMPLETED,
                "MARKET_DATA",
                {
                    "symbol": "BTC/USDT",
                    "close": "110",
                    "open": "108",
                    "high": "111",
                    "low": "107",
                },
            )
        )

        record = engine._risk_ledger.get_position_record("pos-1")
        portfolio_record = engine._portfolio_state.get_position("pos-1")

        assert record.current_stop == Decimal("95")
        assert portfolio_record.current_stop == Decimal("95")
        assert published_events == []

        bus.unregister_listener(listener.name)
        await bus.shutdown()

    async def test_state_transition_changes_trailing_behavior_to_emergency(self) -> None:
        """STATE_TRANSITION в SURVIVAL должен переводить trailing в emergency path."""
        engine = make_engine()
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        state_events: list[Event] = []
        trailing_events: list[Event] = []
        bus.on(RiskEngineEventType.RISK_ENGINE_STATE_UPDATED, state_events.append)
        bus.on(RiskEngineEventType.TRAILING_STOP_MOVED, trailing_events.append)
        listener = RiskEngineListener(
            risk_engine=engine,
            publisher=bus.publish,
            config=RiskEngineListenerConfig(name="risk_listener_state_transition"),
        )
        bus.register_listener(listener)

        await engine.handle_order_filled(
            listener._parse_order_filled(make_order_filled_event().payload)
        )
        await bus.publish(
            make_state_transition_event(
                from_state=SystemState.TRADING,
                to_state=SystemState.SURVIVAL,
            )
        )
        await bus.publish(
            make_bar_completed_event(mark_price="110", best_bid="109", best_ask="111", atr="2")
        )

        record = engine._risk_ledger.get_position_record("pos-1")

        assert engine.current_system_state is SystemState.SURVIVAL
        assert len(state_events) == 1
        assert state_events[0].payload["to_state"] == SystemState.SURVIVAL.value
        assert state_events[0].payload["risk_engine_state"] == SystemState.SURVIVAL.value
        assert len(trailing_events) == 1
        assert trailing_events[0].payload["mode"] == "EMERGENCY"
        assert record.current_stop == Decimal("108.455")

        bus.unregister_listener(listener.name)
        await bus.shutdown()

    async def test_bar_completed_publishes_blocked_event_when_ledger_sync_fails(self) -> None:
        """При ошибке ledger sync движение стопа должно блокироваться и публиковаться отдельно."""
        engine = make_engine(ledger=BrokenUpdateLedger())
        bus = EnhancedEventBus(enable_persistence=False, redis_url=None, rate_limit=10000)
        blocked_events: list[Event] = []
        bus.on(RiskEngineEventType.TRAILING_STOP_BLOCKED, blocked_events.append)
        listener = RiskEngineListener(
            risk_engine=engine,
            publisher=bus.publish,
            config=RiskEngineListenerConfig(name="risk_listener_blocked"),
        )
        bus.register_listener(listener)

        await bus.publish(make_order_filled_event())
        await bus.publish(make_bar_completed_event())

        record = engine._risk_ledger.get_position_record("pos-1")

        assert record.current_stop == Decimal("95")
        assert len(blocked_events) == 1
        assert blocked_events[0].payload["position_id"] == "pos-1"
        assert blocked_events[0].payload["symbol"] == "BTC/USDT"
        assert blocked_events[0].payload["should_execute"] is False
        assert "RiskLedger" in blocked_events[0].payload["reason"]

        bus.unregister_listener(listener.name)
        await bus.shutdown()
