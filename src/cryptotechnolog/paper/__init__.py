"""
Phase 19 Paper Trading Foundation.

После шага `Paper Contract Lock` здесь собраны:
- typed paper contracts;
- typed paper event vocabulary;
- explicit runtime foundation.

На этом шаге пакет intentionally не включает:
- analytics / reporting platform;
- backtesting / replay semantics;
- dashboard / operator line;
- bootstrap wiring;
- bootstrap integration.
"""

from .events import (
    PaperEventSource,
    PaperEventType,
    PaperRehearsalPayload,
    build_paper_event,
    default_priority_for_paper_event,
)
from .models import (
    PaperContext,
    PaperDecision,
    PaperFreshness,
    PaperReasonCode,
    PaperRehearsalCandidate,
    PaperSource,
    PaperStatus,
    PaperValidity,
    PaperValidityStatus,
)
from .runtime import (
    PaperRuntime,
    PaperRuntimeConfig,
    PaperRuntimeDiagnostics,
    PaperRuntimeLifecycleState,
    PaperRuntimeUpdate,
    PaperStateKey,
    create_paper_runtime,
)

__all__ = [
    "PaperContext",
    "PaperDecision",
    "PaperEventSource",
    "PaperEventType",
    "PaperFreshness",
    "PaperReasonCode",
    "PaperRehearsalCandidate",
    "PaperRehearsalPayload",
    "PaperRuntime",
    "PaperRuntimeConfig",
    "PaperRuntimeDiagnostics",
    "PaperRuntimeLifecycleState",
    "PaperRuntimeUpdate",
    "PaperSource",
    "PaperStateKey",
    "PaperStatus",
    "PaperValidity",
    "PaperValidityStatus",
    "build_paper_event",
    "create_paper_runtime",
    "default_priority_for_paper_event",
]
