from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from cryptotechnolog.live_feed import (
    FeedConnectionStatus,
    FeedConnectivityRuntime,
    FeedConnectivityRuntimeConfig,
    FeedSessionIdentity,
)


def _now() -> datetime:
    return datetime(2026, 3, 24, 15, 0, tzinfo=UTC)


def _session() -> FeedSessionIdentity:
    return FeedSessionIdentity(
        exchange="BINANCE",
        stream_kind="trade",
        subscription_scope=("BTCUSDT",),
    )


async def test_runtime_lifecycle_transitions_are_explicit_and_narrow() -> None:
    runtime = FeedConnectivityRuntime(session=_session())
    current_time = _now()

    started = await runtime.start(observed_at=current_time)
    assert runtime.is_started is True
    assert started.status == FeedConnectionStatus.DISCONNECTED

    connecting = runtime.begin_connecting(observed_at=current_time + timedelta(seconds=1))
    assert connecting.status == FeedConnectionStatus.CONNECTING

    connected = runtime.mark_connected(observed_at=current_time + timedelta(seconds=2))
    assert connected.status == FeedConnectionStatus.CONNECTED
    assert runtime.get_runtime_diagnostics()["ready"] is True

    stopped = await runtime.stop(observed_at=current_time + timedelta(seconds=3))
    assert stopped.status == FeedConnectionStatus.DISCONNECTED
    assert runtime.is_started is False


async def test_runtime_can_transition_to_degraded_and_expose_assessment() -> None:
    runtime = FeedConnectivityRuntime(session=_session())
    current_time = _now()
    await runtime.start(observed_at=current_time)
    runtime.begin_connecting(observed_at=current_time + timedelta(seconds=1))
    runtime.mark_connected(observed_at=current_time + timedelta(seconds=2))

    assessment = runtime.mark_degraded(
        observed_at=current_time + timedelta(seconds=10),
        reason="stale_feed",
        staleness_ms=2_000,
    )

    assert assessment.is_degraded is True
    assert assessment.degraded_reason == "stale_feed"
    assert runtime.get_connection_state().status == FeedConnectionStatus.DEGRADED
    assert runtime.get_runtime_diagnostics()["ready"] is False


async def test_runtime_disconnect_updates_retry_and_backoff_truth() -> None:
    runtime = FeedConnectivityRuntime(
        session=_session(),
        config=FeedConnectivityRuntimeConfig(default_retry_delay_seconds=7),
    )
    current_time = _now()
    await runtime.start(observed_at=current_time)

    disconnected = runtime.mark_disconnected(
        observed_at=current_time + timedelta(seconds=1),
        reason="transport_closed",
    )

    assert disconnected.status == FeedConnectionStatus.DISCONNECTED
    assert disconnected.retry_count == 1
    assert disconnected.next_retry_at == current_time + timedelta(seconds=8)
    assert runtime.get_runtime_diagnostics()["last_disconnect_reason"] == "transport_closed"


async def test_runtime_builds_ingest_handoff_without_market_data_ownership_drift() -> None:
    runtime = FeedConnectivityRuntime(session=_session())
    current_time = _now()
    await runtime.start(observed_at=current_time)
    runtime.begin_connecting(observed_at=current_time + timedelta(seconds=1))
    runtime.mark_connected(observed_at=current_time + timedelta(seconds=2))

    request = runtime.build_ingest_request(
        payload_kind="trade_tick",
        transport_payload={"price": "65000", "qty": "0.5"},
        ingested_at=current_time + timedelta(seconds=3),
        source_sequence=5,
    )

    assert request.envelope.payload_kind == "trade_tick"
    assert request.envelope.session.exchange == "BINANCE"
    assert runtime.get_connection_state().last_message_at == current_time + timedelta(seconds=3)
    assert not hasattr(request, "tick_contract")
    assert not hasattr(runtime, "order_router")


async def test_runtime_rejects_ingest_handoff_when_not_connected() -> None:
    runtime = FeedConnectivityRuntime(session=_session())
    current_time = _now()
    await runtime.start(observed_at=current_time)

    with pytest.raises(RuntimeError, match="CONNECTED/DEGRADED state"):
        runtime.build_ingest_request(
            payload_kind="trade_tick",
            transport_payload={"price": "65000"},
            ingested_at=current_time + timedelta(seconds=1),
        )
