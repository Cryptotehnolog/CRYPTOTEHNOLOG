"""
Contract-first модели Phase 22 для narrow live feed connectivity layer.

Этот модуль фиксирует минимальный opening scope:
- typed connection status/state truth;
- typed session identity truth;
- typed feed-health/readiness/degraded semantics;
- typed ingress handoff truth.

Live feed layer intentionally не включает:
- market-data domain models;
- exchange adapter hierarchy;
- execution / OMS / routing / reconciliation semantics;
- runtime/service/platform behavior beyond narrow contract truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from datetime import datetime


class FeedConnectionStatus(StrEnum):
    """Минимальный lifecycle status для live feed connectivity truth."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"


class FeedSubscriptionRecoveryStatus(StrEnum):
    """Минимальный recovery/resubscribe lifecycle без platform semantics."""

    IDLE = "idle"
    RECOVERY_REQUIRED = "recovery_required"
    RESUBSCRIBING = "resubscribing"
    RECOVERED = "recovered"
    RECOVERY_BLOCKED = "recovery_blocked"


class FeedRecoveryIngestMode(StrEnum):
    """Recovery-aware ingest implication без market_data ownership drift."""

    NORMAL = "normal"
    RECOVERY_RESET_REQUIRED = "recovery_reset_required"
    RECOVERY_RESYNC = "recovery_resync"


@dataclass(slots=True, frozen=True)
class FeedSessionIdentity:
    """Typed identity конкретной live feed session без adapter hierarchy semantics."""

    exchange: str
    stream_kind: str
    subscription_scope: tuple[str, ...]
    session_id: UUID = field(default_factory=uuid4)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.exchange.strip():
            raise ValueError("FeedSessionIdentity требует non-empty exchange")
        if not self.stream_kind.strip():
            raise ValueError("FeedSessionIdentity требует non-empty stream_kind")
        if not self.subscription_scope:
            raise ValueError("FeedSessionIdentity требует non-empty subscription_scope")
        if len(self.subscription_scope) != len(set(self.subscription_scope)):
            raise ValueError("FeedSessionIdentity не допускает duplicate subscription scope")


@dataclass(slots=True, frozen=True)
class FeedConnectionState:
    """Typed runtime-time truth для текущего состояния live feed session."""

    session: FeedSessionIdentity
    status: FeedConnectionStatus
    observed_at: datetime
    connected_at: datetime | None = None
    last_message_at: datetime | None = None
    degraded_reason: str | None = None
    retry_count: int = 0
    next_retry_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.retry_count < 0:
            raise ValueError("FeedConnectionState retry_count не может быть отрицательным")
        if self.connected_at is not None and self.connected_at > self.observed_at:
            raise ValueError("connected_at не может быть позже observed_at")
        if self.last_message_at is not None and self.last_message_at > self.observed_at:
            raise ValueError("last_message_at не может быть позже observed_at")
        if (
            self.connected_at is not None
            and self.last_message_at is not None
            and self.last_message_at < self.connected_at
        ):
            raise ValueError("last_message_at не может быть раньше connected_at")
        if (
            self.status
            in (
                FeedConnectionStatus.CONNECTED,
                FeedConnectionStatus.DEGRADED,
            )
            and self.connected_at is None
        ):
            raise ValueError("CONNECTED/DEGRADED state требует connected_at")
        if self.status == FeedConnectionStatus.DEGRADED and not self.degraded_reason:
            raise ValueError("DEGRADED state требует degraded_reason")
        if self.next_retry_at is not None and self.next_retry_at < self.observed_at:
            raise ValueError("next_retry_at не может быть раньше observed_at")


@dataclass(slots=True, frozen=True)
class FeedSubscriptionRecoveryState:
    """Typed recovery/resubscribe truth для конкретной live feed session."""

    session: FeedSessionIdentity
    status: FeedSubscriptionRecoveryStatus
    observed_at: datetime
    recovery_required_at: datetime | None = None
    last_resubscribe_at: datetime | None = None
    last_recovery_reason: str | None = None
    reset_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            self.status
            in (
                FeedSubscriptionRecoveryStatus.RECOVERY_REQUIRED,
                FeedSubscriptionRecoveryStatus.RESUBSCRIBING,
                FeedSubscriptionRecoveryStatus.RECOVERY_BLOCKED,
            )
            and self.recovery_required_at is None
        ):
            raise ValueError("Recovery state требует recovery_required_at")
        if (
            self.status
            in (
                FeedSubscriptionRecoveryStatus.RECOVERY_REQUIRED,
                FeedSubscriptionRecoveryStatus.RESUBSCRIBING,
                FeedSubscriptionRecoveryStatus.RECOVERY_BLOCKED,
            )
            and not self.last_recovery_reason
        ):
            raise ValueError("Recovery-required states требуют last_recovery_reason")
        if (
            self.status == FeedSubscriptionRecoveryStatus.RECOVERED
            and self.last_resubscribe_at is None
        ):
            raise ValueError("RECOVERED state требует last_resubscribe_at")
        if self.recovery_required_at is not None and self.recovery_required_at > self.observed_at:
            raise ValueError("recovery_required_at не может быть позже observed_at")
        if self.last_resubscribe_at is not None and self.last_resubscribe_at > self.observed_at:
            raise ValueError("last_resubscribe_at не может быть позже observed_at")
        if (
            self.recovery_required_at is not None
            and self.last_resubscribe_at is not None
            and self.last_resubscribe_at < self.recovery_required_at
        ):
            raise ValueError("last_resubscribe_at не может быть раньше recovery_required_at")
        if self.status == FeedSubscriptionRecoveryStatus.IDLE and self.reset_required:
            raise ValueError("IDLE state не допускает reset_required")


@dataclass(slots=True, frozen=True)
class FeedConnectivityAssessment:
    """Typed ready/degraded truth поверх session/connectivity state."""

    session: FeedSessionIdentity
    status: FeedConnectionStatus
    observed_at: datetime
    is_ready: bool
    is_degraded: bool
    degraded_reason: str | None = None
    staleness_ms: int | None = None
    blocked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.is_ready and self.is_degraded:
            raise ValueError(
                "FeedConnectivityAssessment не может быть ready и degraded одновременно"
            )
        if self.is_ready and self.status not in (
            FeedConnectionStatus.CONNECTED,
            FeedConnectionStatus.DEGRADED,
        ):
            raise ValueError("ready assessment требует CONNECTED или DEGRADED status")
        if self.is_degraded and not self.degraded_reason:
            raise ValueError("degraded assessment требует degraded_reason")
        if self.status == FeedConnectionStatus.DEGRADED and not self.is_degraded:
            raise ValueError("DEGRADED status требует degraded assessment truth")
        if self.status == FeedConnectionStatus.CONNECTED and not (
            self.is_ready or self.is_degraded
        ):
            raise ValueError("CONNECTED status требует ready или degraded assessment truth")
        if self.staleness_ms is not None and self.staleness_ms < 0:
            raise ValueError("staleness_ms не может быть отрицательным")


@dataclass(slots=True, frozen=True)
class FeedResubscribeRequest:
    """Typed resubscribe intent без client hierarchy и connector ecosystem."""

    session: FeedSessionIdentity
    requested_at: datetime
    recovery_reason: str
    subscription_scope: tuple[str, ...]
    ingest_mode: FeedRecoveryIngestMode = FeedRecoveryIngestMode.RECOVERY_RESET_REQUIRED
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.recovery_reason.strip():
            raise ValueError("FeedResubscribeRequest требует non-empty recovery_reason")
        if not self.subscription_scope:
            raise ValueError("FeedResubscribeRequest требует non-empty subscription_scope")
        if len(self.subscription_scope) != len(set(self.subscription_scope)):
            raise ValueError("FeedResubscribeRequest не допускает duplicate subscription_scope")
        if tuple(self.subscription_scope) != self.session.subscription_scope:
            raise ValueError(
                "FeedResubscribeRequest должен соответствовать session subscription_scope"
            )


@dataclass(slots=True, frozen=True)
class FeedRecoveryAssessment:
    """Typed recovery judgment между reconnect truth и normal ingest."""

    session: FeedSessionIdentity
    status: FeedSubscriptionRecoveryStatus
    observed_at: datetime
    ingest_mode: FeedRecoveryIngestMode
    is_recovered: bool
    reset_required: bool
    blocked: bool = False
    recovery_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.is_recovered and self.blocked:
            raise ValueError("Recovery assessment не может быть recovered и blocked одновременно")
        if self.status == FeedSubscriptionRecoveryStatus.RECOVERED and not self.is_recovered:
            raise ValueError("RECOVERED status требует is_recovered")
        if self.status == FeedSubscriptionRecoveryStatus.RECOVERY_BLOCKED and not self.blocked:
            raise ValueError("RECOVERY_BLOCKED status требует blocked assessment")
        if self.reset_required and self.ingest_mode == FeedRecoveryIngestMode.NORMAL:
            raise ValueError("reset_required incompatible с NORMAL ingest mode")
        if (
            self.status
            in (
                FeedSubscriptionRecoveryStatus.RECOVERY_REQUIRED,
                FeedSubscriptionRecoveryStatus.RESUBSCRIBING,
                FeedSubscriptionRecoveryStatus.RECOVERY_BLOCKED,
            )
            and not self.recovery_reason
        ):
            raise ValueError("Recovery-required assessment требует recovery_reason")
        if (
            self.status == FeedSubscriptionRecoveryStatus.IDLE
            and self.ingest_mode != FeedRecoveryIngestMode.NORMAL
        ):
            raise ValueError("IDLE assessment требует NORMAL ingest mode")


@dataclass(slots=True, frozen=True)
class FeedIngressEnvelope:
    """Typed handoff между live feed connectivity line и existing market_data layer."""

    session: FeedSessionIdentity
    payload_kind: str
    ingested_at: datetime
    transport_payload: dict[str, Any]
    source_sequence: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.payload_kind.strip():
            raise ValueError("FeedIngressEnvelope требует non-empty payload_kind")
        if self.source_sequence is not None and self.source_sequence < 0:
            raise ValueError("source_sequence не может быть отрицательной")


@dataclass(slots=True, frozen=True)
class FeedIngestRequest:
    """Narrow ingest contract для передачи envelope в existing market_data layer."""

    envelope: FeedIngressEnvelope
    requested_at: datetime
    source_contract: str = "live_feed_connectivity"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.requested_at < self.envelope.ingested_at:
            raise ValueError(
                "FeedIngestRequest requested_at не может быть раньше envelope.ingested_at"
            )
        if not self.source_contract.strip():
            raise ValueError("FeedIngestRequest требует non-empty source_contract")
