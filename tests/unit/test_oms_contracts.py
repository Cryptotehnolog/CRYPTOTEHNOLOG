from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from cryptotechnolog.core.event import Priority
from cryptotechnolog.execution import (
    ExecutionDirection,
    ExecutionFreshness,
    ExecutionOrderIntent,
    ExecutionReasonCode,
    ExecutionStatus,
    ExecutionValidity,
    ExecutionValidityStatus,
)
from cryptotechnolog.market_data import MarketDataTimeframe
from cryptotechnolog.oms import (
    OmsContext,
    OmsEventType,
    OmsFreshness,
    OmsLifecycleStatus,
    OmsOrderPayload,
    OmsOrderRecord,
    OmsQueryScope,
    OmsReasonCode,
    OmsRuntime,
    OmsRuntimeConfig,
    OmsRuntimeDiagnostics,
    OmsRuntimeLifecycleState,
    OmsRuntimeUpdate,
    OmsSource,
    OmsValidity,
    OmsValidityStatus,
    build_oms_event,
    create_oms_runtime,
    default_priority_for_oms_event,
)


def _build_executable_intent() -> ExecutionOrderIntent:
    now = datetime.now(UTC)
    return ExecutionOrderIntent(
        intent_id=uuid4(),
        contour_name="phase10_execution_contour",
        execution_name="phase10_execution",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
        freshness=ExecutionFreshness(
            generated_at=now,
            expires_at=now + timedelta(minutes=5),
        ),
        validity=ExecutionValidity(
            status=ExecutionValidityStatus.VALID,
            observed_inputs=1,
            required_inputs=1,
        ),
        status=ExecutionStatus.EXECUTABLE,
        direction=ExecutionDirection.BUY,
        originating_candidate_id=uuid4(),
        confidence=Decimal("0.8600"),
        reason_code=ExecutionReasonCode.CONTEXT_READY,
    )


class TestOmsContracts:
    def test_oms_validity_readiness_ratio_is_normalized(self) -> None:
        validity = OmsValidity(
            status=OmsValidityStatus.WARMING,
            observed_inputs=1,
            required_inputs=3,
            missing_inputs=("execution_intent", "registry_policy"),
        )

        assert validity.is_valid is False
        assert validity.is_warming is True
        assert validity.missing_inputs_count == 2
        assert validity.readiness_ratio == Decimal("0.3333")

    def test_oms_freshness_requires_reference_time_for_expiry(self) -> None:
        now = datetime.now(UTC)
        freshness = OmsFreshness(
            generated_at=now,
            expires_at=now + timedelta(minutes=1),
        )

        assert freshness.has_structurally_valid_expiry_window is True
        assert freshness.is_expired_at(now + timedelta(minutes=2)) is True
        assert freshness.is_expired_at(now + timedelta(seconds=30)) is False

    def test_valid_oms_context_requires_executable_execution_intent(self) -> None:
        intent = _build_executable_intent()
        context = OmsContext(
            oms_name="phase16_oms",
            contour_name="phase16_oms_contour",
            symbol="BTCUSDT",
            exchange="BINANCE",
            timeframe=MarketDataTimeframe.M5,
            observed_at=datetime.now(UTC),
            source=OmsSource.EXECUTION,
            intent=intent,
            validity=OmsValidity(
                status=OmsValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
        )

        assert context.validity.is_valid is True
        assert context.intent.is_executable is True

    def test_registered_record_exposes_active_order_truth(self) -> None:
        intent = _build_executable_intent()
        record = OmsOrderRecord.registered(
            contour_name="phase16_oms_contour",
            oms_name="phase16_oms",
            symbol=intent.symbol,
            exchange=intent.exchange,
            timeframe=intent.timeframe,
            freshness=OmsFreshness(
                generated_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            ),
            validity=OmsValidity(
                status=OmsValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            originating_intent_id=intent.intent_id,
            reason_code=OmsReasonCode.ORDER_REGISTERED,
            query_scope=OmsQueryScope.ACTIVE,
        )

        assert record.lifecycle_status == OmsLifecycleStatus.REGISTERED
        assert record.is_active is True
        assert record.is_terminal is False
        assert record.locator.query_scope == OmsQueryScope.ACTIVE

    def test_terminal_record_query_truth_is_supported(self) -> None:
        intent = _build_executable_intent()
        historical_locator = OmsOrderRecord.registered(
            contour_name="phase16_oms_contour",
            oms_name="phase16_oms",
            symbol=intent.symbol,
            exchange=intent.exchange,
            timeframe=intent.timeframe,
            freshness=OmsFreshness(generated_at=datetime.now(UTC)),
            validity=OmsValidity(
                status=OmsValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            originating_intent_id=intent.intent_id,
            query_scope=OmsQueryScope.HISTORICAL,
        ).locator
        record = OmsOrderRecord(
            oms_order_id=historical_locator.oms_order_id,
            contour_name="phase16_oms_contour",
            oms_name="phase16_oms",
            symbol=intent.symbol,
            exchange=intent.exchange,
            timeframe=intent.timeframe,
            source=OmsSource.EXECUTION,
            freshness=OmsFreshness(generated_at=datetime.now(UTC)),
            validity=OmsValidity(
                status=OmsValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            lifecycle_status=OmsLifecycleStatus.FILLED,
            originating_intent_id=intent.intent_id,
            locator=historical_locator,
            reason_code=OmsReasonCode.ORDER_FILLED,
        )

        assert record.is_active is False
        assert record.is_terminal is True
        assert record.locator.query_scope == OmsQueryScope.HISTORICAL

    def test_order_locator_must_match_registry_truth(self) -> None:
        intent = _build_executable_intent()
        mismatched_locator = OmsOrderRecord.registered(
            contour_name="phase16_oms_contour",
            oms_name="phase16_oms",
            symbol=intent.symbol,
            exchange=intent.exchange,
            timeframe=intent.timeframe,
            freshness=OmsFreshness(generated_at=datetime.now(UTC)),
            validity=OmsValidity(
                status=OmsValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            originating_intent_id=intent.intent_id,
        ).locator

        with pytest.raises(ValueError, match="OmsOrderLocator oms_order_id должен совпадать"):
            OmsOrderRecord(
                oms_order_id=uuid4(),
                contour_name="phase16_oms_contour",
                oms_name="phase16_oms",
                symbol=intent.symbol,
                exchange=intent.exchange,
                timeframe=intent.timeframe,
                source=OmsSource.EXECUTION,
                freshness=OmsFreshness(generated_at=datetime.now(UTC)),
                validity=OmsValidity(
                    status=OmsValidityStatus.VALID,
                    observed_inputs=1,
                    required_inputs=1,
                ),
                lifecycle_status=OmsLifecycleStatus.REGISTERED,
                originating_intent_id=intent.intent_id,
                locator=mismatched_locator,
            )

    def test_oms_event_payload_is_transport_compatible(self) -> None:
        intent = _build_executable_intent()
        record = OmsOrderRecord.registered(
            contour_name="phase16_oms_contour",
            oms_name="phase16_oms",
            symbol=intent.symbol,
            exchange=intent.exchange,
            timeframe=intent.timeframe,
            freshness=OmsFreshness(generated_at=datetime.now(UTC)),
            validity=OmsValidity(
                status=OmsValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            originating_intent_id=intent.intent_id,
            reason_code=OmsReasonCode.ORDER_REGISTERED,
        )
        payload = OmsOrderPayload.from_record(record)
        event = build_oms_event(
            event_type=OmsEventType.OMS_ORDER_REGISTERED,
            payload=payload,
        )

        assert event.event_type == OmsEventType.OMS_ORDER_REGISTERED.value
        assert event.payload["oms_order_id"] == str(record.oms_order_id)
        assert event.payload["originating_intent_id"] == str(intent.intent_id)
        assert event.payload["query_scope"] == OmsQueryScope.ACTIVE.value

    def test_default_priority_for_oms_event_is_narrow_and_predictable(self) -> None:
        assert default_priority_for_oms_event(OmsEventType.OMS_ORDER_REGISTERED) == Priority.NORMAL
        assert default_priority_for_oms_event(OmsEventType.OMS_ORDER_SUBMITTED) == Priority.NORMAL
        assert default_priority_for_oms_event(OmsEventType.OMS_ORDER_ACCEPTED) == Priority.NORMAL
        assert default_priority_for_oms_event(OmsEventType.OMS_ORDER_PARTIALLY_FILLED) == (
            Priority.NORMAL
        )
        assert default_priority_for_oms_event(OmsEventType.OMS_ORDER_FILLED) == Priority.HIGH
        assert default_priority_for_oms_event(OmsEventType.OMS_ORDER_CANCELLED) == Priority.HIGH
        assert default_priority_for_oms_event(OmsEventType.OMS_ORDER_REJECTED) == Priority.HIGH
        assert default_priority_for_oms_event(OmsEventType.OMS_ORDER_EXPIRED) == Priority.HIGH

    def test_runtime_boundary_types_are_instantiable_for_next_step(self) -> None:
        config = OmsRuntimeConfig(
            contour_name="phase16_oms_contour",
            oms_name="phase16_oms",
        )
        diagnostics = OmsRuntimeDiagnostics()
        update = OmsRuntimeUpdate(
            context=OmsContext(
                oms_name="phase16_oms",
                contour_name="phase16_oms_contour",
                symbol="BTCUSDT",
                exchange="BINANCE",
                timeframe=MarketDataTimeframe.M5,
                observed_at=datetime.now(UTC),
                source=OmsSource.EXECUTION,
                intent=_build_executable_intent(),
                validity=OmsValidity(
                    status=OmsValidityStatus.WARMING,
                    observed_inputs=0,
                    required_inputs=1,
                    missing_inputs=("execution_intent",),
                ),
            ),
            order_record=None,
            event_type=OmsEventType.OMS_ORDER_REGISTERED,
            emitted_payload=None,
        )

        assert config.contour_name == "phase16_oms_contour"
        assert diagnostics.lifecycle_state == OmsRuntimeLifecycleState.NOT_STARTED
        assert update.order_record is None

    def test_create_oms_runtime_returns_explicit_runtime_boundary(self) -> None:
        runtime = create_oms_runtime()

        assert isinstance(runtime, OmsRuntime)
        assert runtime.get_runtime_diagnostics()["started"] is False
