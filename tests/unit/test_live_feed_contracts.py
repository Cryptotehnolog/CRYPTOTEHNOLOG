from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from cryptotechnolog.live_feed import (
    FeedConnectionState,
    FeedConnectionStatus,
    FeedConnectivityAssessment,
    FeedIngestRequest,
    FeedIngressEnvelope,
    FeedSessionIdentity,
)


def _now() -> datetime:
    return datetime(2026, 3, 24, 14, 0, tzinfo=UTC)


def _session() -> FeedSessionIdentity:
    return FeedSessionIdentity(
        exchange="BINANCE",
        stream_kind="trade",
        subscription_scope=("BTCUSDT",),
    )


def test_session_identity_requires_non_empty_unique_subscription_scope() -> None:
    with pytest.raises(ValueError, match="non-empty exchange"):
        FeedSessionIdentity(
            exchange="",
            stream_kind="trade",
            subscription_scope=("BTCUSDT",),
        )

    with pytest.raises(ValueError, match="non-empty stream_kind"):
        FeedSessionIdentity(
            exchange="BINANCE",
            stream_kind="",
            subscription_scope=("BTCUSDT",),
        )

    with pytest.raises(ValueError, match="non-empty subscription_scope"):
        FeedSessionIdentity(
            exchange="BINANCE",
            stream_kind="trade",
            subscription_scope=(),
        )

    with pytest.raises(ValueError, match="duplicate subscription scope"):
        FeedSessionIdentity(
            exchange="BINANCE",
            stream_kind="trade",
            subscription_scope=("BTCUSDT", "BTCUSDT"),
        )


def test_connection_state_enforces_status_and_timestamp_invariants() -> None:
    current_time = _now()
    session = _session()

    with pytest.raises(ValueError, match="retry_count"):
        FeedConnectionState(
            session=session,
            status=FeedConnectionStatus.CONNECTING,
            observed_at=current_time,
            retry_count=-1,
        )

    with pytest.raises(ValueError, match="CONNECTED/DEGRADED state требует connected_at"):
        FeedConnectionState(
            session=session,
            status=FeedConnectionStatus.CONNECTED,
            observed_at=current_time,
        )

    with pytest.raises(ValueError, match="DEGRADED state требует degraded_reason"):
        FeedConnectionState(
            session=session,
            status=FeedConnectionStatus.DEGRADED,
            observed_at=current_time,
            connected_at=current_time - timedelta(seconds=5),
        )

    with pytest.raises(ValueError, match="last_message_at не может быть раньше connected_at"):
        FeedConnectionState(
            session=session,
            status=FeedConnectionStatus.CONNECTED,
            observed_at=current_time,
            connected_at=current_time - timedelta(seconds=5),
            last_message_at=current_time - timedelta(seconds=10),
        )


def test_connectivity_assessment_keeps_ready_and_degraded_truth_narrow() -> None:
    current_time = _now()
    session = _session()

    ready = FeedConnectivityAssessment(
        session=session,
        status=FeedConnectionStatus.CONNECTED,
        observed_at=current_time,
        is_ready=True,
        is_degraded=False,
    )

    assert ready.is_ready is True
    assert ready.is_degraded is False

    degraded = FeedConnectivityAssessment(
        session=session,
        status=FeedConnectionStatus.DEGRADED,
        observed_at=current_time,
        is_ready=False,
        is_degraded=True,
        degraded_reason="stale_feed",
        staleness_ms=1_500,
    )

    assert degraded.degraded_reason == "stale_feed"
    assert degraded.staleness_ms == 1_500

    with pytest.raises(ValueError, match="ready и degraded одновременно"):
        FeedConnectivityAssessment(
            session=session,
            status=FeedConnectionStatus.CONNECTED,
            observed_at=current_time,
            is_ready=True,
            is_degraded=True,
        )

    with pytest.raises(ValueError, match="degraded assessment требует degraded_reason"):
        FeedConnectivityAssessment(
            session=session,
            status=FeedConnectionStatus.DEGRADED,
            observed_at=current_time,
            is_ready=False,
            is_degraded=True,
        )


def test_ingress_envelope_and_request_preserve_narrow_handoff_truth() -> None:
    current_time = _now()
    session = _session()
    envelope = FeedIngressEnvelope(
        session=session,
        payload_kind="trade_tick",
        ingested_at=current_time,
        transport_payload={"price": "65000", "qty": "0.1"},
        source_sequence=10,
    )

    request = FeedIngestRequest(
        envelope=envelope,
        requested_at=current_time + timedelta(milliseconds=5),
    )

    assert request.source_contract == "live_feed_connectivity"
    assert request.envelope.session == session
    assert not hasattr(request, "tick_contract")
    assert not hasattr(request, "orderbook_snapshot")

    with pytest.raises(ValueError, match="non-empty payload_kind"):
        FeedIngressEnvelope(
            session=session,
            payload_kind="",
            ingested_at=current_time,
            transport_payload={},
        )

    with pytest.raises(ValueError, match="requested_at не может быть раньше"):
        FeedIngestRequest(
            envelope=envelope,
            requested_at=current_time - timedelta(milliseconds=1),
        )
