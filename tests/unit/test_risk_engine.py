from datetime import UTC, datetime
from decimal import Decimal

from cryptotechnolog.core.state_machine_enums import SystemState
from cryptotechnolog.risk.correlation import (
    CorrelationConfig,
    CorrelationEvaluator,
    CorrelationGroup,
)
from cryptotechnolog.risk.drawdown_monitor import DrawdownMonitor
from cryptotechnolog.risk.engine import PreTradeContext, RiskEngine, RiskEngineConfig
from cryptotechnolog.risk.models import Order, OrderSide, Position, PositionSide, RejectReason
from cryptotechnolog.risk.portfolio_state import PortfolioState
from cryptotechnolog.risk.position_sizing import PositionSizer
from cryptotechnolog.risk.risk_ledger import RiskLedger
from cryptotechnolog.risk.trailing_policy import TrailingPolicy


def make_order(
    *,
    order_id: str = "ord-1",
    symbol: str = "BTC/USDT",
    entry_price: Decimal = Decimal("100"),
    stop_loss: Decimal | None = Decimal("95"),
) -> Order:
    return Order(
        order_id=order_id,
        symbol=symbol,
        side=OrderSide.BUY,
        entry_price=entry_price,
        stop_loss=stop_loss,  # type: ignore[arg-type]
    )


def make_position(
    *,
    position_id: str,
    symbol: str = "BTC/USDT",
    side: PositionSide,
    entry_price: Decimal,
    initial_stop: Decimal,
    current_stop: Decimal,
    quantity: Decimal,
) -> Position:
    now = datetime(2026, 3, 19, tzinfo=UTC)
    return Position(
        position_id=position_id,
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        initial_stop=initial_stop,
        current_stop=current_stop,
        quantity=quantity,
        risk_capital_usd=Decimal("10000"),
        opened_at=now,
        updated_at=now,
    )


def _make_engine(
    *,
    config: RiskEngineConfig | None = None,
    correlation_evaluator: CorrelationEvaluator | None = None,
    portfolio: PortfolioState | None = None,
    ledger: RiskLedger | None = None,
    drawdown: DrawdownMonitor | None = None,
) -> RiskEngine:
    resolved_ledger = ledger or RiskLedger()
    resolved_portfolio = portfolio or PortfolioState()
    resolved_drawdown = drawdown or DrawdownMonitor(starting_equity=Decimal("10000"))
    resolved_config = config or RiskEngineConfig(
        base_r_percent=Decimal("0.01"),
        max_r_per_trade=Decimal("0.02"),
        max_total_r=Decimal("0.03"),
        max_total_exposure_usd=Decimal("6000"),
        max_position_size=Decimal("5000"),
        quantity_step=Decimal("0.01"),
        price_precision=Decimal("0.01"),
        risk_precision=Decimal("0.00000001"),
    )
    return RiskEngine(
        config=resolved_config,
        correlation_evaluator=correlation_evaluator or CorrelationEvaluator(),
        position_sizer=PositionSizer(),
        portfolio_state=resolved_portfolio,
        drawdown_monitor=resolved_drawdown,
        risk_ledger=resolved_ledger,
        trailing_policy=TrailingPolicy(resolved_ledger),
    )


class TestRiskEngine:
    """Тесты первого pre-trade orchestration RiskEngine."""

    def setup_method(self) -> None:
        self.ledger = RiskLedger()
        self.portfolio = PortfolioState()
        self.drawdown = DrawdownMonitor(starting_equity=Decimal("10000"))
        self.engine = _make_engine(
            portfolio=self.portfolio,
            ledger=self.ledger,
            drawdown=self.drawdown,
        )

    def test_rejects_when_system_state_does_not_allow_trading(self) -> None:
        """Вне разрешённых состояний новая сделка должна отклоняться."""
        result = self.engine.check_trade(
            make_order(),
            PreTradeContext(
                system_state=SystemState.READY,
                current_equity=Decimal("10000"),
            ),
        )

        assert result.allowed is False
        assert result.reason is RejectReason.STATE_MACHINE_NOT_TRADING

    def test_requires_stop_loss(self) -> None:
        """Pre-trade gate должен требовать stop_loss до sizing."""
        result = self.engine.check_trade(
            make_order(stop_loss=None),
            PreTradeContext(
                system_state=SystemState.TRADING,
                current_equity=Decimal("10000"),
            ),
        )

        assert result.allowed is False
        assert result.reason is RejectReason.STOP_LOSS_REQUIRED

    def test_returns_typed_success_result_for_valid_trade(self) -> None:
        """В допустимом сценарии RiskEngine должен возвращать типизированный allow-result."""
        result = self.engine.check_trade(
            make_order(),
            PreTradeContext(
                system_state=SystemState.TRADING,
                current_equity=Decimal("10000"),
            ),
        )

        assert result.allowed is True
        assert result.reason == "within_limits"
        assert result.risk_r == Decimal("0.01000000")
        assert result.position_size_usd == Decimal("2000.00")
        assert result.position_size_base == Decimal("20.00")
        assert result.current_total_r == Decimal("0")

    def test_rejects_when_projected_total_r_exceeds_limit(self) -> None:
        """Aggregate risk должен блокировать сделку до исполнения."""
        record = self.ledger.register_position(
            make_position(
                position_id="pos-1",
                side=PositionSide.LONG,
                entry_price=Decimal("100"),
                initial_stop=Decimal("95"),
                current_stop=Decimal("89"),
                quantity=Decimal("20"),
            )
        )
        self.portfolio.upsert_position(record)

        result = self.engine.check_trade(
            make_order(order_id="ord-2", symbol="UNI/USDT"),
            PreTradeContext(
                system_state=SystemState.TRADING,
                current_equity=Decimal("10000"),
            ),
        )

        assert result.allowed is False
        assert result.reason is RejectReason.MAX_TOTAL_R_EXCEEDED

    def test_rejects_when_projected_exposure_exceeds_limit(self) -> None:
        """Aggregate exposure должен учитываться через PortfolioState."""
        record = self.ledger.register_position(
            make_position(
                position_id="pos-1",
                side=PositionSide.LONG,
                entry_price=Decimal("150"),
                initial_stop=Decimal("145"),
                current_stop=Decimal("147"),
                quantity=Decimal("30"),
            )
        )
        self.portfolio.upsert_position(record)

        result = self.engine.check_trade(
            make_order(order_id="ord-3", symbol="UNI/USDT"),
            PreTradeContext(
                system_state=SystemState.TRADING,
                current_equity=Decimal("10000"),
            ),
        )

        assert result.allowed is False
        assert result.reason is RejectReason.MAX_TOTAL_EXPOSURE_EXCEEDED

    def test_rejects_on_hard_drawdown(self) -> None:
        """Жёсткая просадка должна блокировать новую сделку."""
        result = self.engine.check_trade(
            make_order(order_id="ord-4"),
            PreTradeContext(
                system_state=SystemState.TRADING,
                current_equity=Decimal("8900"),
            ),
        )

        assert result.allowed is False
        assert result.reason is RejectReason.DRAWDOWN_HARD_LIMIT_EXCEEDED

    def test_rejects_on_velocity_drawdown(self) -> None:
        """Velocity drawdown должен блокировать новую сделку до исполнения."""
        self.drawdown.record_trade_result(Decimal("-1.2"))
        self.drawdown.record_trade_result(Decimal("-0.9"))

        result = self.engine.check_trade(
            make_order(order_id="ord-5"),
            PreTradeContext(
                system_state=SystemState.TRADING,
                current_equity=Decimal("10000"),
            ),
        )

        assert result.allowed is False
        assert result.reason is RejectReason.VELOCITY_DRAWDOWN_TRIGGERED

    def test_degraded_state_scales_risk_budget(self) -> None:
        """В DEGRADED effective risk budget должен ужиматься по state policy."""
        ledger = RiskLedger()
        engine = _make_engine(
            ledger=ledger,
            config=RiskEngineConfig(
                base_r_percent=Decimal("0.02"),
                max_r_per_trade=Decimal("0.02"),
                max_total_r=Decimal("0.10"),
                max_total_exposure_usd=Decimal("10000"),
                max_position_size=Decimal("10000"),
                quantity_step=Decimal("0.01"),
                price_precision=Decimal("0.01"),
                risk_precision=Decimal("0.00000001"),
            ),
        )

        result = engine.check_trade(
            make_order(order_id="ord-6"),
            PreTradeContext(
                system_state=SystemState.DEGRADED,
                current_equity=Decimal("10000"),
            ),
        )

        assert result.allowed is True
        assert result.risk_r == Decimal("0.01000000")
        assert result.details["effective_risk_per_trade"] == "0.010"

    def test_rejects_when_correlation_limit_is_exceeded(self) -> None:
        """RiskEngine должен отклонять сделку при чрезмерной корреляции с портфелем."""
        ledger = RiskLedger()
        portfolio = PortfolioState()
        record = ledger.register_position(
            make_position(
                position_id="pos-1",
                symbol="BTC/USDT",
                side=PositionSide.LONG,
                entry_price=Decimal("100"),
                initial_stop=Decimal("95"),
                current_stop=Decimal("95"),
                quantity=Decimal("2"),
            )
        )
        portfolio.upsert_position(record)
        engine = _make_engine(
            ledger=ledger,
            portfolio=portfolio,
            config=RiskEngineConfig(
                base_r_percent=Decimal("0.01"),
                max_r_per_trade=Decimal("0.02"),
                max_total_r=Decimal("0.10"),
                max_total_exposure_usd=Decimal("10000"),
                max_position_size=Decimal("5000"),
                quantity_step=Decimal("0.01"),
                price_precision=Decimal("0.01"),
                risk_precision=Decimal("0.00000001"),
            ),
            correlation_evaluator=CorrelationEvaluator(
                CorrelationConfig(
                    correlation_limit=Decimal("0.80"),
                    pair_overrides={frozenset({"BTC/USDT", "ETH/USDT"}): Decimal("0.91")},
                )
            ),
        )

        result = engine.check_trade(
            Order(
                order_id="ord-corr-1",
                symbol="ETH/USDT",
                side=OrderSide.BUY,
                entry_price=Decimal("100"),
                stop_loss=Decimal("95"),
            ),
            PreTradeContext(
                system_state=SystemState.TRADING,
                current_equity=Decimal("10000"),
            ),
        )

        assert result.allowed is False
        assert result.reason is RejectReason.CORRELATION_LIMIT_EXCEEDED

    def test_rejects_when_correlation_group_limit_is_exceeded(self) -> None:
        """RiskEngine должен учитывать group limit как отдельный reject path."""
        ledger = RiskLedger()
        portfolio = PortfolioState()
        first = ledger.register_position(
            make_position(
                position_id="pos-1",
                symbol="BTC/USDT",
                side=PositionSide.LONG,
                entry_price=Decimal("100"),
                initial_stop=Decimal("95"),
                current_stop=Decimal("95"),
                quantity=Decimal("2"),
            )
        )
        second = ledger.register_position(
            make_position(
                position_id="pos-2",
                symbol="ETH/USDT",
                side=PositionSide.LONG,
                entry_price=Decimal("100"),
                initial_stop=Decimal("95"),
                current_stop=Decimal("95"),
                quantity=Decimal("2"),
            )
        )
        portfolio.upsert_position(first)
        portfolio.upsert_position(second)
        engine = _make_engine(
            ledger=ledger,
            portfolio=portfolio,
            config=RiskEngineConfig(
                base_r_percent=Decimal("0.01"),
                max_r_per_trade=Decimal("0.02"),
                max_total_r=Decimal("0.10"),
                max_total_exposure_usd=Decimal("10000"),
                max_position_size=Decimal("5000"),
                quantity_step=Decimal("0.01"),
                price_precision=Decimal("0.01"),
                risk_precision=Decimal("0.00000001"),
            ),
            correlation_evaluator=CorrelationEvaluator(
                CorrelationConfig(
                    correlation_limit=Decimal("1.10"),
                    max_positions_per_group={
                        CorrelationGroup.MAJORS: 2,
                        CorrelationGroup.L1: 2,
                        CorrelationGroup.DEFI: 2,
                        CorrelationGroup.MEMES: 1,
                        CorrelationGroup.OTHER: 1,
                    },
                )
            ),
        )

        result = engine.check_trade(
            Order(
                order_id="ord-corr-2",
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                entry_price=Decimal("100"),
                stop_loss=Decimal("95"),
            ),
            PreTradeContext(
                system_state=SystemState.TRADING,
                current_equity=Decimal("10000"),
            ),
        )

        assert result.allowed is False
        assert result.reason is RejectReason.CORRELATION_GROUP_LIMIT_EXCEEDED
