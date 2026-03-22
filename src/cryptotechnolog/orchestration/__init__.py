"""
Contract-first package boundary для Phase 12 Strategy Orchestration / Meta Layer.

На шаге `Orchestration Contract Lock` здесь фиксируются:
- typed orchestration / meta contracts;
- validity / readiness semantics;
- abstain / no-decision semantics;
- event vocabulary;
- typed runtime boundary shape для следующего шага.
"""

from .events import (
    OrchestrationDecisionPayload,
    OrchestrationEventSource,
    OrchestrationEventType,
    build_orchestration_event,
    default_priority_for_orchestration_event,
)
from .models import (
    OrchestrationContext,
    OrchestrationDecision,
    OrchestrationDecisionCandidate,
    OrchestrationFreshness,
    OrchestrationReasonCode,
    OrchestrationSource,
    OrchestrationStatus,
    OrchestrationValidity,
    OrchestrationValidityStatus,
)
from .runtime import (
    OrchestrationRuntime,
    OrchestrationRuntimeConfig,
    OrchestrationRuntimeDiagnostics,
    OrchestrationRuntimeLifecycleState,
    OrchestrationRuntimeUpdate,
    OrchestrationStateKey,
    create_orchestration_runtime,
)

__all__ = [
    "OrchestrationContext",
    "OrchestrationDecision",
    "OrchestrationDecisionCandidate",
    "OrchestrationDecisionPayload",
    "OrchestrationEventSource",
    "OrchestrationEventType",
    "OrchestrationFreshness",
    "OrchestrationReasonCode",
    "OrchestrationRuntime",
    "OrchestrationRuntimeConfig",
    "OrchestrationRuntimeDiagnostics",
    "OrchestrationRuntimeLifecycleState",
    "OrchestrationRuntimeUpdate",
    "OrchestrationSource",
    "OrchestrationStateKey",
    "OrchestrationStatus",
    "OrchestrationValidity",
    "OrchestrationValidityStatus",
    "build_orchestration_event",
    "create_orchestration_runtime",
    "default_priority_for_orchestration_event",
]
