"""
Phase 18 Validation Foundation.

После шагов `Validation Contract Lock` и `Validation Runtime Foundation`
здесь собраны:
- typed validation contracts;
- typed validation event vocabulary;
- explicit validation runtime foundation.

На этом шаге пакет intentionally не включает:
- analytics / reporting platform;
- backtesting / paper-trading semantics;
- bootstrap wiring;
- runtime implementation beyond boundary shape.
"""

from .events import (
    ValidationEventSource,
    ValidationEventType,
    ValidationReviewPayload,
    build_validation_event,
    default_priority_for_validation_event,
)
from .models import (
    ValidationContext,
    ValidationDecision,
    ValidationFreshness,
    ValidationReasonCode,
    ValidationReviewCandidate,
    ValidationSource,
    ValidationStatus,
    ValidationValidity,
    ValidationValidityStatus,
)
from .runtime import (
    ValidationRuntime,
    ValidationRuntimeConfig,
    ValidationRuntimeDiagnostics,
    ValidationRuntimeLifecycleState,
    ValidationRuntimeUpdate,
    ValidationStateKey,
    create_validation_runtime,
)

__all__ = [
    "ValidationContext",
    "ValidationDecision",
    "ValidationEventSource",
    "ValidationEventType",
    "ValidationFreshness",
    "ValidationReasonCode",
    "ValidationReviewCandidate",
    "ValidationReviewPayload",
    "ValidationRuntime",
    "ValidationRuntimeConfig",
    "ValidationRuntimeDiagnostics",
    "ValidationRuntimeLifecycleState",
    "ValidationRuntimeUpdate",
    "ValidationSource",
    "ValidationStateKey",
    "ValidationStatus",
    "ValidationValidity",
    "ValidationValidityStatus",
    "build_validation_event",
    "create_validation_runtime",
    "default_priority_for_validation_event",
]
