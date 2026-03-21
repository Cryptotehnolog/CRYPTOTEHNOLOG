"""
Contract-first package boundary для Phase 10 Execution Foundation.

На шаге `Execution Contract Lock` здесь фиксируются:
- typed execution contracts;
- execution validity / readiness semantics;
- execution event vocabulary;
- typed runtime boundary shape для следующего шага.
"""

from .events import (
    ExecutionEventSource,
    ExecutionEventType,
    ExecutionOrderIntentPayload,
    build_execution_event,
    default_priority_for_execution_event,
)
from .models import (
    ExecutionContext,
    ExecutionDirection,
    ExecutionFreshness,
    ExecutionOrderIntent,
    ExecutionReasonCode,
    ExecutionStatus,
    ExecutionValidity,
    ExecutionValidityStatus,
)
from .runtime import (
    ExecutionRuntime,
    ExecutionRuntimeConfig,
    ExecutionRuntimeDiagnostics,
    ExecutionRuntimeLifecycleState,
    ExecutionRuntimeUpdate,
    create_execution_runtime,
)

__all__ = [
    "ExecutionContext",
    "ExecutionDirection",
    "ExecutionEventSource",
    "ExecutionEventType",
    "ExecutionFreshness",
    "ExecutionOrderIntent",
    "ExecutionOrderIntentPayload",
    "ExecutionReasonCode",
    "ExecutionRuntime",
    "ExecutionRuntimeConfig",
    "ExecutionRuntimeDiagnostics",
    "ExecutionRuntimeLifecycleState",
    "ExecutionRuntimeUpdate",
    "ExecutionStatus",
    "ExecutionValidity",
    "ExecutionValidityStatus",
    "build_execution_event",
    "create_execution_runtime",
    "default_priority_for_execution_event",
]
