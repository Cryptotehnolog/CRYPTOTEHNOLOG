"""
Contract-first package boundary для Phase 15 Protection / Supervisor Foundation.

На шаге `Protection Contract Lock` здесь фиксируются:
- typed protection / supervisor contracts;
- freeze / halt / protect semantics;
- event vocabulary;
- typed runtime boundary shape для следующего шага.
"""

from .events import (
    ProtectionEventSource,
    ProtectionEventType,
    ProtectionPayload,
    build_protection_event,
    default_priority_for_protection_event,
)
from .models import (
    ProtectionContext,
    ProtectionDecision,
    ProtectionFreshness,
    ProtectionReasonCode,
    ProtectionSource,
    ProtectionStatus,
    ProtectionSupervisorCandidate,
    ProtectionValidity,
    ProtectionValidityStatus,
)
from .runtime import (
    ProtectionRuntime,
    ProtectionRuntimeConfig,
    ProtectionRuntimeDiagnostics,
    ProtectionRuntimeLifecycleState,
    ProtectionRuntimeUpdate,
    ProtectionStateKey,
    create_protection_runtime,
)

__all__ = [
    "ProtectionContext",
    "ProtectionDecision",
    "ProtectionEventSource",
    "ProtectionEventType",
    "ProtectionFreshness",
    "ProtectionPayload",
    "ProtectionReasonCode",
    "ProtectionRuntime",
    "ProtectionRuntimeConfig",
    "ProtectionRuntimeDiagnostics",
    "ProtectionRuntimeLifecycleState",
    "ProtectionRuntimeUpdate",
    "ProtectionSource",
    "ProtectionStateKey",
    "ProtectionStatus",
    "ProtectionSupervisorCandidate",
    "ProtectionValidity",
    "ProtectionValidityStatus",
    "build_protection_event",
    "create_protection_runtime",
    "default_priority_for_protection_event",
]
