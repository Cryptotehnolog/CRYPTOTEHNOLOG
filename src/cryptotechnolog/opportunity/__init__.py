"""
Contract-first package boundary для Phase 11 Opportunity / Selection Foundation.

На шаге `Opportunity Contract Lock` здесь фиксируются:
- typed opportunity / selection contracts;
- validity / readiness semantics;
- event vocabulary;
- typed runtime boundary shape для следующего шага.
"""

from .events import (
    OpportunityEventSource,
    OpportunityEventType,
    OpportunitySelectionPayload,
    build_opportunity_event,
    default_priority_for_opportunity_event,
)
from .models import (
    OpportunityContext,
    OpportunityDirection,
    OpportunityFreshness,
    OpportunityReasonCode,
    OpportunitySelectionCandidate,
    OpportunitySource,
    OpportunityStatus,
    OpportunityValidity,
    OpportunityValidityStatus,
)
from .runtime import (
    OpportunityRuntime,
    OpportunityRuntimeConfig,
    OpportunityRuntimeDiagnostics,
    OpportunityRuntimeLifecycleState,
    OpportunityRuntimeUpdate,
    create_opportunity_runtime,
)

__all__ = [
    "OpportunityContext",
    "OpportunityDirection",
    "OpportunityEventSource",
    "OpportunityEventType",
    "OpportunityFreshness",
    "OpportunityReasonCode",
    "OpportunityRuntime",
    "OpportunityRuntimeConfig",
    "OpportunityRuntimeDiagnostics",
    "OpportunityRuntimeLifecycleState",
    "OpportunityRuntimeUpdate",
    "OpportunitySelectionCandidate",
    "OpportunitySelectionPayload",
    "OpportunitySource",
    "OpportunityStatus",
    "OpportunityValidity",
    "OpportunityValidityStatus",
    "build_opportunity_event",
    "create_opportunity_runtime",
    "default_priority_for_opportunity_event",
]
