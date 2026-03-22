from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from cryptotechnolog.core.event import Event
from cryptotechnolog.core.listeners.audit import AuditListener
from cryptotechnolog.core.listeners.metrics import MetricsListener
from cryptotechnolog.risk.engine import RiskEngineEventType


@pytest.mark.asyncio
class TestRiskEventDownstreamListeners:
    """Минимальные регрессии downstream listeners для Step 6 vocabulary."""

    async def test_audit_listener_preserves_risk_engine_state_transition_contract(self) -> None:
        """Audit listener должен маппить from_state/to_state в structured audit state."""
        listener = AuditListener()
        listener._record_audit_event = AsyncMock()  # type: ignore[method-assign]

        event = Event.new(
            RiskEngineEventType.RISK_ENGINE_STATE_UPDATED,
            "RISK_ENGINE",
            {
                "from_state": "trading",
                "to_state": "survival",
                "risk_engine_state": "survival",
            },
        )

        await listener.handle(event)

        listener._record_audit_event.assert_awaited_once()
        kwargs = listener._record_audit_event.await_args.kwargs
        assert kwargs["old_state"] == {"risk_engine_state": "trading"}
        assert kwargs["new_state"] == {"risk_engine_state": "survival"}
        assert kwargs["event_type"] == RiskEngineEventType.RISK_ENGINE_STATE_UPDATED
        assert kwargs["entity_type"] == "risk"
        assert kwargs["severity"] == "WARNING"

    async def test_metrics_listener_counts_drawdown_alert_as_risk_violation_metric(self) -> None:
        """Metrics listener должен учитывать DRAWDOWN_ALERT как новый critical risk signal."""
        listener = MetricsListener()
        listener._record_performance_metric = AsyncMock()  # type: ignore[method-assign]

        event = Event.new(
            RiskEngineEventType.DRAWDOWN_ALERT,
            "RISK_ENGINE",
            {
                "symbol": "BTC/USDT",
                "reason": "drawdown_hard_limit_exceeded",
            },
        )

        await listener.handle(event)

        listener._record_performance_metric.assert_awaited_once_with(
            metric_category="error_rate",
            metric_name="risk_violations_total",
            value=1,
            tags={"symbol": "BTC/USDT", "violation_type": RiskEngineEventType.DRAWDOWN_ALERT},
        )

    async def test_metrics_listener_counts_velocity_killswitch_as_risk_violation_metric(
        self,
    ) -> None:
        """Metrics listener должен учитывать VELOCITY_KILLSWITCH_TRIGGERED как critical signal."""
        listener = MetricsListener()
        listener._record_performance_metric = AsyncMock()  # type: ignore[method-assign]

        event = Event.new(
            RiskEngineEventType.VELOCITY_KILLSWITCH_TRIGGERED,
            "RISK_ENGINE",
            {
                "symbol": "ETH/USDT",
                "reason": "velocity_drawdown_triggered",
            },
        )

        await listener.handle(event)

        listener._record_performance_metric.assert_awaited_once_with(
            metric_category="error_rate",
            metric_name="risk_violations_total",
            value=1,
            tags={
                "symbol": "ETH/USDT",
                "violation_type": RiskEngineEventType.VELOCITY_KILLSWITCH_TRIGGERED,
            },
        )
