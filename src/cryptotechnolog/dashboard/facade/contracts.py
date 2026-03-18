"""Typed snapshot contracts для dashboard facade layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PendingApprovalsSnapshot:
    """Стабильный snapshot pending approvals для dashboard layer."""

    pending_count: int
    total_requests: int
    request_timeout_minutes: int


@dataclass(frozen=True, slots=True)
class EventSummarySnapshot:
    """Стабильный snapshot event summary для dashboard layer."""

    total_published: int
    total_delivered: int
    total_dropped: int
    total_rate_limited: int
    subscriber_count: int
    persistence_enabled: bool
    backpressure_strategy: str


@dataclass(frozen=True, slots=True)
class CircuitBreakerSnapshot:
    """Стабильный snapshot circuit breaker summary для dashboard layer."""

    name: str
    state: str
    failure_count: int
    success_count: int
    failure_threshold: int
    recovery_timeout: int
