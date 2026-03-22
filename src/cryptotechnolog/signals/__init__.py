"""
Contract-first package boundary для Phase 8 Signal Generation Foundation.

На шаге `Signal Contract Lock` здесь фиксируются:
- typed signal contracts;
- signal validity / readiness semantics;
- signal event vocabulary;
- typed runtime boundary shape и узкий runtime foundation.
"""

from .events import (
    SignalEventSource,
    SignalEventType,
    SignalSnapshotPayload,
    build_signal_event,
    default_priority_for_signal_event,
)
from .models import (
    SignalContext,
    SignalDirection,
    SignalFreshness,
    SignalReasonCode,
    SignalSnapshot,
    SignalStatus,
    SignalValidity,
    SignalValidityStatus,
)
from .runtime import (
    SignalRuntime,
    SignalRuntimeConfig,
    SignalRuntimeDiagnostics,
    SignalRuntimeLifecycleState,
    SignalRuntimeUpdate,
    create_signal_runtime,
)

__all__ = [
    "SignalContext",
    "SignalDirection",
    "SignalEventSource",
    "SignalEventType",
    "SignalFreshness",
    "SignalReasonCode",
    "SignalRuntime",
    "SignalRuntimeConfig",
    "SignalRuntimeDiagnostics",
    "SignalRuntimeLifecycleState",
    "SignalRuntimeUpdate",
    "SignalSnapshot",
    "SignalSnapshotPayload",
    "SignalStatus",
    "SignalValidity",
    "SignalValidityStatus",
    "build_signal_event",
    "create_signal_runtime",
    "default_priority_for_signal_event",
]
