"""
Contract-first package boundary для Phase 17 Strategy Manager / Workflow Foundation.

После шагов `Manager Contract Lock` и `Manager Runtime Foundation` здесь собраны:
- typed manager / workflow contracts;
- validity / readiness semantics;
- event vocabulary;
- explicit manager runtime foundation.
"""

from .events import (
    ManagerEventSource,
    ManagerEventType,
    ManagerWorkflowPayload,
    build_manager_event,
    default_priority_for_manager_event,
)
from .models import (
    ManagerContext,
    ManagerDecision,
    ManagerFreshness,
    ManagerReasonCode,
    ManagerSource,
    ManagerStatus,
    ManagerValidity,
    ManagerValidityStatus,
    ManagerWorkflowCandidate,
)
from .runtime import (
    ManagerRuntime,
    ManagerRuntimeConfig,
    ManagerRuntimeDiagnostics,
    ManagerRuntimeLifecycleState,
    ManagerRuntimeUpdate,
    ManagerStateKey,
    create_manager_runtime,
)

__all__ = [
    "ManagerContext",
    "ManagerDecision",
    "ManagerEventSource",
    "ManagerEventType",
    "ManagerFreshness",
    "ManagerReasonCode",
    "ManagerRuntime",
    "ManagerRuntimeConfig",
    "ManagerRuntimeDiagnostics",
    "ManagerRuntimeLifecycleState",
    "ManagerRuntimeUpdate",
    "ManagerSource",
    "ManagerStateKey",
    "ManagerStatus",
    "ManagerValidity",
    "ManagerValidityStatus",
    "ManagerWorkflowCandidate",
    "ManagerWorkflowPayload",
    "build_manager_event",
    "create_manager_runtime",
    "default_priority_for_manager_event",
]
