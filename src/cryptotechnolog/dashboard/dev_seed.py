"""Controlled dev/test seed data for dashboard positions endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import os

from cryptotechnolog.risk.models import PositionRiskRecord, PositionSide, TrailingState
from cryptotechnolog.risk.persistence_contracts import (
    ClosedPositionHistoryRecord,
    IRiskPersistenceRepository,
    PositionRiskLedgerAuditRecord,
    RiskCheckAuditRecord,
    TrailingStopMovementRecord,
    TrailingStopSnapshotRecord,
)
from cryptotechnolog.risk.portfolio_state import PortfolioState

DASHBOARD_DEV_SEED_ENV_VAR = "CRYPTOTEHNOLOG_DASHBOARD_DEV_SEED"
POSITIONS_DEV_SEED_NAME = "positions"


@dataclass(slots=True)
class DashboardDevSeedBundle:
    """Bundled seeded sources for dashboard read-only positions surfaces."""

    portfolio_state: PortfolioState
    risk_persistence_repository: IRiskPersistenceRepository


class InMemorySeedRiskRepository:
    """Minimal in-memory repository for dashboard dev/test position history seed."""

    def __init__(self, history: tuple[ClosedPositionHistoryRecord, ...]) -> None:
        self._history = history

    async def save_risk_check(self, record: RiskCheckAuditRecord) -> None:
        return None

    async def upsert_position_risk_record(self, record: PositionRiskRecord) -> None:
        return None

    async def append_position_risk_audit(self, record: PositionRiskLedgerAuditRecord) -> None:
        return None

    async def upsert_trailing_stop_snapshot(self, record: TrailingStopSnapshotRecord) -> None:
        return None

    async def append_trailing_stop_movement(self, record: TrailingStopMovementRecord) -> None:
        return None

    async def append_closed_position_history(self, record: ClosedPositionHistoryRecord) -> None:
        self._history = (record, *self._history)

    async def list_closed_position_history(
        self,
        *,
        limit: int | None = None,
    ) -> tuple[ClosedPositionHistoryRecord, ...]:
        if limit is None:
            return self._history
        return self._history[:limit]

    async def delete_position_risk_record(self, position_id: str) -> None:
        return None

    async def delete_trailing_stop_snapshot(self, position_id: str) -> None:
        return None


def maybe_build_dashboard_dev_seed() -> DashboardDevSeedBundle | None:
    """Build controlled dev/test seed only when explicit env flag is enabled."""
    seed_name = os.getenv(DASHBOARD_DEV_SEED_ENV_VAR, "").strip().lower()
    if seed_name != POSITIONS_DEV_SEED_NAME:
        return None
    return build_positions_dev_seed_bundle()


def build_positions_dev_seed_bundle() -> DashboardDevSeedBundle:
    """Build meaningful seeded open/history positions for local UI verification."""
    portfolio_state = PortfolioState(positions=_build_open_position_records())
    repository = InMemorySeedRiskRepository(history=_build_closed_position_history_records())
    return DashboardDevSeedBundle(
        portfolio_state=portfolio_state,
        risk_persistence_repository=repository,
    )


def _build_open_position_records() -> tuple[PositionRiskRecord, ...]:
    return (
        PositionRiskRecord(
            position_id="open-btc-okx-001",
            symbol="BTC/USDT",
            exchange_id="OKX",
            strategy_id="breakout-trend",
            side=PositionSide.LONG,
            entry_price=Decimal("67420"),
            initial_stop=Decimal("66200"),
            current_stop=Decimal("66880"),
            quantity=Decimal("0.35"),
            risk_capital_usd=Decimal("10000"),
            initial_risk_usd=Decimal("427"),
            initial_risk_r=Decimal("0.04"),
            current_risk_usd=Decimal("189"),
            current_risk_r=Decimal("0.02"),
            current_price=Decimal("68125"),
            unrealized_pnl_usd=Decimal("246.75"),
            unrealized_pnl_percent=Decimal("1.0466"),
            trailing_state=TrailingState.ARMED,
            opened_at=_dt("2026-03-29T08:15:00+00:00"),
            updated_at=_dt("2026-03-30T09:42:00+00:00"),
        ),
        PositionRiskRecord(
            position_id="open-eth-bybit-002",
            symbol="ETH/USDT",
            exchange_id="Bybit",
            strategy_id="mean-reversion-short",
            side=PositionSide.SHORT,
            entry_price=Decimal("3540"),
            initial_stop=Decimal("3624"),
            current_stop=Decimal("3588"),
            quantity=Decimal("4.5"),
            risk_capital_usd=Decimal("10000"),
            initial_risk_usd=Decimal("378"),
            initial_risk_r=Decimal("0.04"),
            current_risk_usd=Decimal("216"),
            current_risk_r=Decimal("0.02"),
            current_price=Decimal("3462"),
            unrealized_pnl_usd=Decimal("351.00"),
            unrealized_pnl_percent=Decimal("2.2034"),
            trailing_state=TrailingState.ACTIVE,
            opened_at=_dt("2026-03-29T13:05:00+00:00"),
            updated_at=_dt("2026-03-30T10:18:00+00:00"),
        ),
        PositionRiskRecord(
            position_id="open-sol-binance-003",
            symbol="SOL/USDT",
            exchange_id="Binance",
            strategy_id="range-continuation",
            side=PositionSide.LONG,
            entry_price=Decimal("178.4"),
            initial_stop=Decimal("170.8"),
            current_stop=Decimal("174.2"),
            quantity=Decimal("120"),
            risk_capital_usd=Decimal("10000"),
            initial_risk_usd=Decimal("912"),
            initial_risk_r=Decimal("0.09"),
            current_risk_usd=Decimal("504"),
            current_risk_r=Decimal("0.05"),
            current_price=Decimal("175.9"),
            unrealized_pnl_usd=Decimal("-300.00"),
            unrealized_pnl_percent=Decimal("-1.4013"),
            trailing_state=TrailingState.INACTIVE,
            opened_at=_dt("2026-03-30T06:50:00+00:00"),
            updated_at=_dt("2026-03-30T08:04:00+00:00"),
        ),
    )


def _build_closed_position_history_records() -> tuple[ClosedPositionHistoryRecord, ...]:
    return (
        ClosedPositionHistoryRecord(
            position_id="hist-btc-okx-101",
            symbol="BTC/USDT",
            exchange_id="OKX",
            strategy_id="breakout-trend",
            side="long",
            entry_price=Decimal("66280"),
            quantity=Decimal("0.28"),
            initial_stop=Decimal("65120"),
            current_stop=Decimal("66940"),
            trailing_state="terminated",
            opened_at=_dt("2026-03-26T07:20:00+00:00"),
            closed_at=_dt("2026-03-29T11:40:00+00:00"),
            exit_price=Decimal("67960"),
            exit_reason="take_profit",
            realized_pnl_r=Decimal("2.40"),
            realized_pnl_usd=Decimal("470.40"),
            realized_pnl_percent=Decimal("2.5313"),
        ),
        ClosedPositionHistoryRecord(
            position_id="hist-eth-bybit-102",
            symbol="ETH/USDT",
            exchange_id="Bybit",
            strategy_id="mean-reversion-short",
            side="short",
            entry_price=Decimal("3488"),
            quantity=Decimal("3.2"),
            initial_stop=Decimal("3562"),
            current_stop=Decimal("3444"),
            trailing_state="terminated",
            opened_at=_dt("2026-03-27T10:10:00+00:00"),
            closed_at=_dt("2026-03-30T09:55:00+00:00"),
            exit_price=Decimal("3444"),
            exit_reason="trailing_stop",
            realized_pnl_r=Decimal("1.35"),
            realized_pnl_usd=Decimal("140.80"),
            realized_pnl_percent=Decimal("1.2560"),
        ),
        ClosedPositionHistoryRecord(
            position_id="hist-sol-binance-103",
            symbol="SOL/USDT",
            exchange_id="Binance",
            strategy_id="range-continuation",
            side="long",
            entry_price=Decimal("171.6"),
            quantity=Decimal("90"),
            initial_stop=Decimal("166.2"),
            current_stop=Decimal("169.8"),
            trailing_state="terminated",
            opened_at=_dt("2026-03-25T09:00:00+00:00"),
            closed_at=_dt("2026-03-28T14:25:00+00:00"),
            exit_price=Decimal("169.8"),
            exit_reason="stop_loss",
            realized_pnl_r=Decimal("-0.65"),
            realized_pnl_usd=Decimal("-162.00"),
            realized_pnl_percent=Decimal("-1.0490"),
        ),
        ClosedPositionHistoryRecord(
            position_id="hist-bnb-okx-104",
            symbol="BNB/USDT",
            exchange_id="OKX",
            strategy_id="funding-rotation",
            side="short",
            entry_price=Decimal("618.5"),
            quantity=Decimal("35"),
            initial_stop=Decimal("629.4"),
            current_stop=Decimal("614.2"),
            trailing_state="terminated",
            opened_at=_dt("2026-03-24T12:15:00+00:00"),
            closed_at=_dt("2026-03-27T18:05:00+00:00"),
            exit_price=Decimal("614.2"),
            exit_reason="manual_close",
            realized_pnl_r=Decimal("0.80"),
            realized_pnl_usd=Decimal("150.50"),
            realized_pnl_percent=Decimal("0.6944"),
        ),
    )


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)
