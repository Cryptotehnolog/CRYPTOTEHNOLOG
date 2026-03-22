from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

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
    OmsLifecycleStatus,
    OmsQueryScope,
    OmsReasonCode,
    OmsRuntime,
    OmsRuntimeConfig,
    OmsRuntimeLifecycleState,
    create_oms_runtime,
)


def _make_execution_intent(
    *,
    status: ExecutionStatus = ExecutionStatus.EXECUTABLE,
    validity_status: ExecutionValidityStatus = ExecutionValidityStatus.VALID,
    generated_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> ExecutionOrderIntent:
    now = generated_at or datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    return ExecutionOrderIntent(
        intent_id=uuid4(),
        contour_name="phase10_execution_contour",
        execution_name="phase10_execution",
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe=MarketDataTimeframe.M5,
        freshness=ExecutionFreshness(
            generated_at=now,
            expires_at=expires_at or (now + timedelta(minutes=5)),
        ),
        validity=ExecutionValidity(
            status=validity_status,
            observed_inputs=1 if validity_status == ExecutionValidityStatus.VALID else 0,
            required_inputs=1,
            missing_inputs=()
            if validity_status == ExecutionValidityStatus.VALID
            else ("execution_context",),
            invalid_reason=(
                None
                if validity_status != ExecutionValidityStatus.INVALID
                else "execution_intent_invalid"
            ),
        ),
        status=status,
        direction=ExecutionDirection.BUY if status == ExecutionStatus.EXECUTABLE else None,
        originating_candidate_id=uuid4() if status == ExecutionStatus.EXECUTABLE else None,
        confidence=Decimal("0.8700") if status == ExecutionStatus.EXECUTABLE else None,
        reason_code=(
            ExecutionReasonCode.CONTEXT_READY
            if status == ExecutionStatus.EXECUTABLE
            else ExecutionReasonCode.CONTEXT_INCOMPLETE
        ),
    )


def test_oms_runtime_requires_explicit_start() -> None:
    runtime = create_oms_runtime()

    with pytest.raises(RuntimeError, match="не запущен"):
        runtime.ingest_intent(
            intent=_make_execution_intent(),
            reference_time=datetime(2026, 3, 23, 12, 1, tzinfo=UTC),
        )


def test_oms_runtime_start_and_stop_reset_operator_state() -> None:
    runtime = create_oms_runtime()

    asyncio.run(runtime.start())
    runtime.mark_degraded("oms_ingest_failed")
    update = runtime.ingest_intent(
        intent=_make_execution_intent(),
        reference_time=datetime(2026, 3, 23, 12, 1, tzinfo=UTC),
    )
    assert update.order_record is not None

    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is True
    assert diagnostics["tracked_active_orders"] == 1

    asyncio.run(runtime.stop())
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["started"] is False
    assert diagnostics["tracked_contexts"] == 0
    assert diagnostics["tracked_active_orders"] == 0
    assert diagnostics["tracked_historical_orders"] == 0
    assert diagnostics["last_intent_id"] is None
    assert diagnostics["last_order_id"] is None
    assert diagnostics["last_event_type"] is None
    assert diagnostics["last_failure_reason"] is None
    assert diagnostics["lifecycle_state"] == OmsRuntimeLifecycleState.STOPPED.value
    assert diagnostics["readiness_reasons"] == ["runtime_stopped"]


def test_oms_runtime_registers_order_state_from_executable_intent() -> None:
    runtime = create_oms_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_intent(
        intent=_make_execution_intent(),
        reference_time=datetime(2026, 3, 23, 12, 1, tzinfo=UTC),
    )

    assert update.order_record is not None
    assert update.order_record.lifecycle_status == OmsLifecycleStatus.REGISTERED
    assert update.order_record.locator.query_scope == OmsQueryScope.ACTIVE
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is True
    assert diagnostics["lifecycle_state"] == OmsRuntimeLifecycleState.READY.value
    assert diagnostics["tracked_active_orders"] == 1


def test_oms_runtime_advances_active_order_into_historical_terminal_truth() -> None:
    runtime = create_oms_runtime()
    asyncio.run(runtime.start())

    registered = runtime.ingest_intent(
        intent=_make_execution_intent(),
        reference_time=datetime(2026, 3, 23, 12, 1, tzinfo=UTC),
    )
    assert registered.order_record is not None

    submitted = runtime.advance_order(
        oms_order_id=registered.order_record.oms_order_id,
        target_status=OmsLifecycleStatus.SUBMITTED,
        reference_time=datetime(2026, 3, 23, 12, 2, tzinfo=UTC),
    )
    accepted = runtime.advance_order(
        oms_order_id=registered.order_record.oms_order_id,
        target_status=OmsLifecycleStatus.ACCEPTED,
        reference_time=datetime(2026, 3, 23, 12, 3, tzinfo=UTC),
    )
    filled = runtime.advance_order(
        oms_order_id=registered.order_record.oms_order_id,
        target_status=OmsLifecycleStatus.FILLED,
        reference_time=datetime(2026, 3, 23, 12, 4, tzinfo=UTC),
    )

    assert submitted.order_record is not None
    assert accepted.order_record is not None
    assert filled.order_record is not None
    assert filled.order_record.lifecycle_status == OmsLifecycleStatus.FILLED
    assert filled.order_record.locator.query_scope == OmsQueryScope.HISTORICAL
    assert runtime.get_active_order(oms_order_id=filled.order_record.oms_order_id) is None
    assert runtime.get_historical_order(oms_order_id=filled.order_record.oms_order_id) is not None
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["tracked_active_orders"] == 0
    assert diagnostics["tracked_historical_orders"] == 1


def test_oms_runtime_supports_partial_fill_progression() -> None:
    runtime = create_oms_runtime(config=OmsRuntimeConfig(partial_fill_threshold=Decimal("0.0050")))
    asyncio.run(runtime.start())

    registered = runtime.ingest_intent(
        intent=_make_execution_intent(),
        reference_time=datetime(2026, 3, 23, 12, 1, tzinfo=UTC),
    )
    assert registered.order_record is not None

    runtime.advance_order(
        oms_order_id=registered.order_record.oms_order_id,
        target_status=OmsLifecycleStatus.SUBMITTED,
        reference_time=datetime(2026, 3, 23, 12, 2, tzinfo=UTC),
    )
    runtime.advance_order(
        oms_order_id=registered.order_record.oms_order_id,
        target_status=OmsLifecycleStatus.ACCEPTED,
        reference_time=datetime(2026, 3, 23, 12, 3, tzinfo=UTC),
    )
    partial = runtime.advance_order(
        oms_order_id=registered.order_record.oms_order_id,
        target_status=OmsLifecycleStatus.PARTIALLY_FILLED,
        reference_time=datetime(2026, 3, 23, 12, 4, tzinfo=UTC),
    )

    assert partial.order_record is not None
    assert partial.order_record.lifecycle_status == OmsLifecycleStatus.PARTIALLY_FILLED
    assert partial.order_record.metadata["partial_fill_threshold"] == "0.0050"
    assert partial.order_record.locator.query_scope == OmsQueryScope.ACTIVE


def test_oms_runtime_expires_active_order_only_against_reference_time() -> None:
    runtime = create_oms_runtime(
        config=OmsRuntimeConfig(max_order_age_seconds=60),
    )
    asyncio.run(runtime.start())

    generated_at = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    update = runtime.ingest_intent(
        intent=_make_execution_intent(
            generated_at=generated_at,
            expires_at=generated_at + timedelta(minutes=5),
        ),
        reference_time=generated_at,
    )
    assert update.order_record is not None

    active = runtime.get_active_order(oms_order_id=update.order_record.oms_order_id)
    assert active is not None
    assert active.lifecycle_status == OmsLifecycleStatus.REGISTERED

    expired = runtime.expire_orders(reference_time=generated_at + timedelta(seconds=60))
    assert len(expired) == 1
    assert expired[0].order_record is not None
    assert expired[0].order_record.lifecycle_status == OmsLifecycleStatus.EXPIRED
    assert expired[0].order_record.reason_code == OmsReasonCode.ORDER_EXPIRED
    assert runtime.get_historical_order(oms_order_id=update.order_record.oms_order_id) is not None


def test_oms_runtime_exposes_warming_behavior_for_non_executable_intent() -> None:
    runtime = create_oms_runtime()
    asyncio.run(runtime.start())

    update = runtime.ingest_intent(
        intent=_make_execution_intent(
            status=ExecutionStatus.CANDIDATE,
            validity_status=ExecutionValidityStatus.WARMING,
        ),
        reference_time=datetime(2026, 3, 23, 12, 1, tzinfo=UTC),
    )

    assert update.order_record is None
    assert update.event_type is None
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == OmsRuntimeLifecycleState.WARMING.value
    assert diagnostics["readiness_reasons"] == ["executable_execution_intent"]


def test_oms_runtime_marks_degraded_for_invalid_execution_truth() -> None:
    runtime = OmsRuntime()

    asyncio.run(runtime.start())
    update = runtime.ingest_intent(
        intent=_make_execution_intent(
            status=ExecutionStatus.INVALIDATED,
            validity_status=ExecutionValidityStatus.INVALID,
        ),
        reference_time=datetime(2026, 3, 23, 12, 1, tzinfo=UTC),
    )

    assert update.order_record is None
    diagnostics = runtime.get_runtime_diagnostics()
    assert diagnostics["ready"] is False
    assert diagnostics["lifecycle_state"] == OmsRuntimeLifecycleState.DEGRADED.value
    assert diagnostics["last_failure_reason"] == "execution_intent_invalidated"


def test_oms_runtime_query_surface_uses_intent_and_order_identifiers() -> None:
    runtime = create_oms_runtime()
    asyncio.run(runtime.start())

    intent = _make_execution_intent()
    update = runtime.ingest_intent(
        intent=intent,
        reference_time=datetime(2026, 3, 23, 12, 1, tzinfo=UTC),
    )
    assert update.order_record is not None

    context = runtime.get_context(intent_id=intent.intent_id)
    from_intent = runtime.get_order_by_intent(intent_id=intent.intent_id)
    from_active = runtime.get_active_order(oms_order_id=update.order_record.oms_order_id)

    assert context is not None
    assert from_intent is not None
    assert from_active is not None
    assert from_intent.oms_order_id == update.order_record.oms_order_id
    assert from_active.oms_order_id == update.order_record.oms_order_id


def test_oms_runtime_uses_runtime_config_in_state_keying() -> None:
    runtime = create_oms_runtime(
        config=OmsRuntimeConfig(
            contour_name="custom_oms_contour",
            oms_name="custom_oms",
        )
    )
    asyncio.run(runtime.start())

    intent = _make_execution_intent()
    update = runtime.ingest_intent(
        intent=intent,
        reference_time=datetime(2026, 3, 23, 12, 1, tzinfo=UTC),
    )

    assert update.order_record is not None
    assert update.order_record.contour_name == "custom_oms_contour"
    assert update.order_record.oms_name == "custom_oms"
    context = runtime.get_context(intent_id=intent.intent_id)
    assert context is not None
    assert context.contour_name == "custom_oms_contour"
    assert context.oms_name == "custom_oms"
