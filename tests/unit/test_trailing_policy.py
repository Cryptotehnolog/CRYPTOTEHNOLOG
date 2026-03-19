from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cryptotechnolog.core.state_machine_enums import SystemState
from cryptotechnolog.risk.models import (
    MarketSnapshot,
    Position,
    PositionSide,
    TrailingEvaluationType,
    TrailingMode,
    TrailingState,
    TrailingTier,
)
from cryptotechnolog.risk.risk_ledger import RiskLedger
from cryptotechnolog.risk.trailing_policy import (
    TrailingInputError,
    TrailingPolicy,
)


def make_position(
    *,
    position_id: str = "pos-1",
    side: PositionSide = PositionSide.LONG,
    entry_price: Decimal = Decimal("100"),
    initial_stop: Decimal = Decimal("95"),
    current_stop: Decimal = Decimal("95"),
    quantity: Decimal = Decimal("2"),
) -> Position:
    now = datetime(2026, 3, 19, tzinfo=UTC)
    return Position(
        position_id=position_id,
        symbol="BTC/USDT",
        side=side,
        entry_price=entry_price,
        initial_stop=initial_stop,
        current_stop=current_stop,
        quantity=quantity,
        risk_capital_usd=Decimal("10000"),
        trailing_state=TrailingState.INACTIVE,
        opened_at=now,
        updated_at=now,
    )


def make_market(
    *,
    mark_price: Decimal = Decimal("110"),
    atr: Decimal = Decimal("2"),
    best_bid: Decimal = Decimal("109.8"),
    best_ask: Decimal = Decimal("110.2"),
    adx: Decimal = Decimal("25"),
    confirmed_highs: int = 2,
    confirmed_lows: int = 2,
    structural_stop: Decimal | None = None,
    is_stale: bool = False,
) -> MarketSnapshot:
    return MarketSnapshot(
        mark_price=mark_price,
        atr=atr,
        best_bid=best_bid,
        best_ask=best_ask,
        adx=adx,
        confirmed_highs=confirmed_highs,
        confirmed_lows=confirmed_lows,
        structural_stop=structural_stop,
        is_stale=is_stale,
        timestamp=datetime(2026, 3, 19, tzinfo=UTC),
    )


class BrokenLedger(RiskLedger):
    """Тестовый ledger, который падает при update."""

    def update_position_risk(self, **kwargs):  # type: ignore[override]
        raise RuntimeError("ledger sync failed")


class TestTrailingPolicy:
    """Тесты доменной логики TrailingPolicy."""

    def setup_method(self) -> None:
        self.ledger = RiskLedger()
        self.policy = TrailingPolicy(self.ledger)

    def test_selects_tier_by_pnl_r(self) -> None:
        """Tier должен выбираться по pnl_r."""
        assert self.policy._select_tier(Decimal("1.2")) is TrailingTier.T1
        assert self.policy._select_tier(Decimal("2.0")) is TrailingTier.T2
        assert self.policy._select_tier(Decimal("4.0")) is TrailingTier.T3
        assert self.policy._select_tier(Decimal("5.0")) is TrailingTier.T3
        assert self.policy._select_tier(Decimal("6.0")) is TrailingTier.T4

    def test_moves_long_stop_monotonically_and_syncs_ledger(self) -> None:
        """LONG stop должен двигаться только вверх с sync в ledger."""
        self.ledger.register_position(make_position())

        update = self.policy.evaluate(
            position_id="pos-1",
            pnl_r=Decimal("2.3"),
            market=make_market(mark_price=Decimal("110"), atr=Decimal("2")),
            system_state=SystemState.TRADING,
        )

        assert update.should_execute is True
        assert update.evaluation_type is TrailingEvaluationType.MOVE
        assert update.mode is TrailingMode.NORMAL
        assert update.tier is TrailingTier.T2
        assert update.new_stop == Decimal("107.0")
        assert update.risk_after < update.risk_before
        assert self.ledger.get_position_record("pos-1").current_stop == Decimal("107.0")
        assert self.ledger.get_position_record("pos-1").trailing_state is TrailingState.ACTIVE

    def test_moves_short_stop_monotonically_and_syncs_ledger(self) -> None:
        """SHORT stop должен двигаться только вниз с корректной отдельной логикой."""
        self.ledger.register_position(
            make_position(
                side=PositionSide.SHORT,
                entry_price=Decimal("100"),
                initial_stop=Decimal("105"),
                current_stop=Decimal("105"),
            )
        )

        update = self.policy.evaluate(
            position_id="pos-1",
            pnl_r=Decimal("2.3"),
            market=make_market(mark_price=Decimal("90"), atr=Decimal("2")),
            system_state=SystemState.TRADING,
        )

        assert update.should_execute is True
        assert update.new_stop == Decimal("93.0")
        assert update.risk_after < update.risk_before
        assert self.ledger.get_position_record("pos-1").current_stop == Decimal("93.0")

    def test_uses_structural_mode_only_with_explicit_conditions(self) -> None:
        """Structural trailing должен включаться только по явным условиям."""
        self.ledger.register_position(make_position())

        update = self.policy.evaluate(
            position_id="pos-1",
            pnl_r=Decimal("2.5"),
            market=make_market(
                mark_price=Decimal("110"),
                atr=Decimal("2"),
                adx=Decimal("26"),
                confirmed_highs=3,
                structural_stop=Decimal("108"),
            ),
            system_state=SystemState.TRADING,
        )

        assert update.mode is TrailingMode.STRUCTURAL
        assert update.new_stop == Decimal("108")
        assert self.ledger.get_position_record("pos-1").current_stop == Decimal("108")

    def test_structural_mode_requires_adx_above_25_and_trading_state(self) -> None:
        """Soft HL должен работать только при ADX > 25 и состоянии TRADING."""
        self.ledger.register_position(make_position())

        update_at_threshold = self.policy.evaluate(
            position_id="pos-1",
            pnl_r=Decimal("2.5"),
            market=make_market(
                mark_price=Decimal("110"),
                atr=Decimal("2"),
                adx=Decimal("25"),
                confirmed_highs=3,
                structural_stop=Decimal("108"),
            ),
            system_state=SystemState.TRADING,
        )

        update_degraded = self.policy.evaluate(
            position_id="pos-1",
            pnl_r=Decimal("2.5"),
            market=make_market(
                mark_price=Decimal("112"),
                atr=Decimal("2"),
                adx=Decimal("30"),
                confirmed_highs=3,
                structural_stop=Decimal("111"),
            ),
            system_state=SystemState.DEGRADED,
        )

        assert update_at_threshold.mode is TrailingMode.NORMAL
        assert update_at_threshold.new_stop == Decimal("107.0")
        assert update_degraded.mode is TrailingMode.NORMAL
        assert update_degraded.new_stop == Decimal("109.0")

    def test_structural_mode_is_not_used_in_emergency(self) -> None:
        """Structural trailing не должен применяться в EMERGENCY."""
        self.ledger.register_position(make_position())

        update = self.policy.evaluate(
            position_id="pos-1",
            pnl_r=Decimal("3.0"),
            market=make_market(
                mark_price=Decimal("110"),
                atr=Decimal("2"),
                adx=Decimal("30"),
                confirmed_highs=3,
                structural_stop=Decimal("109"),
            ),
            system_state=SystemState.SURVIVAL,
        )

        assert update.mode is TrailingMode.EMERGENCY
        assert self.ledger.get_position_record("pos-1").trailing_state is TrailingState.EMERGENCY

    def test_blocks_move_in_halt_state(self) -> None:
        """В состоянии HALT движение стопа запрещено."""
        self.ledger.register_position(make_position())

        update = self.policy.evaluate(
            position_id="pos-1",
            pnl_r=Decimal("2.0"),
            market=make_market(),
            system_state=SystemState.HALT,
        )

        assert update.should_execute is False
        assert update.evaluation_type is TrailingEvaluationType.BLOCKED
        assert update.new_stop == update.old_stop
        assert "HALT" in update.reason

    def test_sub_arm_trailing_does_not_move_stop(self) -> None:
        """До arm threshold трейлинг не должен двигать стоп даже при лучшем candidate stop."""
        self.ledger.register_position(make_position())

        update = self.policy.evaluate(
            position_id="pos-1",
            pnl_r=Decimal("0.8"),
            market=make_market(mark_price=Decimal("120"), atr=Decimal("2")),
            system_state=SystemState.TRADING,
        )

        assert update.should_execute is False
        assert update.evaluation_type is TrailingEvaluationType.STATE_SYNC
        assert update.new_stop == Decimal("95")
        assert update.old_stop == Decimal("95")
        assert update.pnl_r == Decimal("0.8")
        assert "Arm threshold" in update.reason
        assert self.ledger.get_position_record("pos-1").current_stop == Decimal("95")
        assert self.ledger.get_position_record("pos-1").trailing_state is TrailingState.INACTIVE

    def test_emergency_mode_is_used_on_stale_market_data(self) -> None:
        """Устаревшие данные не должны приводить к рискованному move."""
        self.ledger.register_position(make_position())

        update = self.policy.evaluate(
            position_id="pos-1",
            pnl_r=Decimal("2.0"),
            market=make_market(is_stale=True),
            system_state=SystemState.TRADING,
        )

        assert update.should_execute is False
        assert update.evaluation_type is TrailingEvaluationType.STATE_SYNC
        assert update.mode is TrailingMode.EMERGENCY
        assert self.ledger.get_position_record("pos-1").trailing_state is TrailingState.EMERGENCY

    def test_repeated_evaluation_is_idempotent_for_same_state(self) -> None:
        """Повторная оценка не должна ломать инварианты и отдалять стоп."""
        self.ledger.register_position(make_position())

        first = self.policy.evaluate(
            position_id="pos-1",
            pnl_r=Decimal("2.3"),
            market=make_market(mark_price=Decimal("110"), atr=Decimal("2")),
            system_state=SystemState.TRADING,
        )
        second = self.policy.evaluate(
            position_id="pos-1",
            pnl_r=Decimal("2.3"),
            market=make_market(mark_price=Decimal("110"), atr=Decimal("2")),
            system_state=SystemState.TRADING,
        )

        assert first.new_stop == Decimal("107.0")
        assert second.should_execute is False
        assert second.new_stop == Decimal("107.0")
        assert self.ledger.get_position_record("pos-1").current_stop == Decimal("107.0")

    def test_blocks_stop_move_when_ledger_sync_fails(self) -> None:
        """No stop move without RiskLedger sync должен соблюдаться жёстко."""
        broken_ledger = BrokenLedger()
        broken_ledger.register_position(make_position())
        policy = TrailingPolicy(broken_ledger)

        update = policy.evaluate(
            position_id="pos-1",
            pnl_r=Decimal("2.3"),
            market=make_market(mark_price=Decimal("110"), atr=Decimal("2")),
            system_state=SystemState.TRADING,
        )

        assert update.should_execute is False
        assert update.evaluation_type is TrailingEvaluationType.BLOCKED
        assert update.new_stop == update.old_stop
        assert "RiskLedger" in update.reason
        assert broken_ledger.get_position_record("pos-1").current_stop == Decimal("95")

    def test_rejects_invalid_market_snapshot(self) -> None:
        """Некорректный market snapshot должен завершаться ошибкой."""
        self.ledger.register_position(make_position())

        with pytest.raises(TrailingInputError, match="best_bid"):
            self.policy.evaluate(
                position_id="pos-1",
                pnl_r=Decimal("2.0"),
                market=make_market(best_bid=Decimal("111"), best_ask=Decimal("110")),
                system_state=SystemState.TRADING,
            )

    def test_force_emergency_uses_separate_tighter_logic(self) -> None:
        """force_emergency должен использовать отдельную более жёсткую формулу."""
        self.ledger.register_position(make_position())

        update = self.policy.force_emergency(
            position_id="pos-1",
            pnl_r=Decimal("2.0"),
            market=make_market(mark_price=Decimal("110"), atr=Decimal("4"), best_bid=Decimal("109")),
            system_state=SystemState.DEGRADED,
        )

        assert update.should_execute is True
        assert update.evaluation_type is TrailingEvaluationType.MOVE
        assert update.mode is TrailingMode.EMERGENCY
        assert update.new_stop == Decimal("108.455")
        assert self.ledger.get_position_record("pos-1").trailing_state is TrailingState.EMERGENCY

    def test_terminate_uses_explicit_neutral_pnl_semantics(self) -> None:
        """Terminate snapshot не должен маскировать downside risk под pnl_r."""
        self.ledger.register_position(make_position())

        update = self.policy.terminate(
            position_id="pos-1",
            system_state=SystemState.TRADING,
        )

        assert update.should_execute is False
        assert update.evaluation_type is TrailingEvaluationType.TERMINATE
        assert update.pnl_r == Decimal("0")
        assert update.new_stop == Decimal("95")
        assert "pnl_r для terminate snapshot не применяется" in update.reason
        assert self.ledger.get_position_record("pos-1").trailing_state is TrailingState.TERMINATED
