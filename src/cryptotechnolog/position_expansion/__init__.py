"""
Contract-first package boundary для Phase 13 Position Expansion Foundation.

На шаге `Position Expansion Contract Lock` здесь фиксируются:
- typed position-expansion contracts;
- validity / readiness semantics;
- abstain / reject / no-expansion semantics;
- event vocabulary;
- typed runtime boundary shape для следующего шага.
"""

from .events import (
    PositionExpansionEventSource,
    PositionExpansionEventType,
    PositionExpansionPayload,
    build_position_expansion_event,
    default_priority_for_position_expansion_event,
)
from .models import (
    ExpansionContext,
    ExpansionDecision,
    ExpansionDirection,
    ExpansionFreshness,
    ExpansionReasonCode,
    ExpansionSource,
    ExpansionStatus,
    ExpansionValidity,
    ExpansionValidityStatus,
    PositionExpansionCandidate,
)
from .runtime import (
    PositionExpansionRuntime,
    PositionExpansionRuntimeConfig,
    PositionExpansionRuntimeDiagnostics,
    PositionExpansionRuntimeLifecycleState,
    PositionExpansionRuntimeUpdate,
    PositionExpansionStateKey,
    create_position_expansion_runtime,
)

__all__ = [
    "ExpansionContext",
    "ExpansionDecision",
    "ExpansionDirection",
    "ExpansionFreshness",
    "ExpansionReasonCode",
    "ExpansionSource",
    "ExpansionStatus",
    "ExpansionValidity",
    "ExpansionValidityStatus",
    "PositionExpansionCandidate",
    "PositionExpansionEventSource",
    "PositionExpansionEventType",
    "PositionExpansionPayload",
    "PositionExpansionRuntime",
    "PositionExpansionRuntimeConfig",
    "PositionExpansionRuntimeDiagnostics",
    "PositionExpansionRuntimeLifecycleState",
    "PositionExpansionRuntimeUpdate",
    "PositionExpansionStateKey",
    "build_position_expansion_event",
    "create_position_expansion_runtime",
    "default_priority_for_position_expansion_event",
]
