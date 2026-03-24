"""
Phase 22 Live Feed Connectivity Foundation.

На шаге `Connectivity Contract Lock` пакет intentionally включает только:
- typed connection/session contracts;
- typed feed-health/readiness/degraded truth;
- typed ingress handoff truth.

На этом шаге пакет intentionally не включает:
- connectivity runtime;
- adapter/client ecosystem;
- execution connectivity / routing / reconciliation;
- persistence / API / dashboard semantics.
"""

from .models import (
    FeedConnectionState,
    FeedConnectionStatus,
    FeedConnectivityAssessment,
    FeedIngestRequest,
    FeedIngressEnvelope,
    FeedSessionIdentity,
)

__all__ = [
    "FeedConnectionState",
    "FeedConnectionStatus",
    "FeedConnectivityAssessment",
    "FeedIngestRequest",
    "FeedIngressEnvelope",
    "FeedSessionIdentity",
]
