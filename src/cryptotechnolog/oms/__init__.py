"""
Contract-first package boundary для Phase 16 OMS Foundation.

После шагов `OMS Contract Lock` и `OMS Runtime Foundation` здесь собраны:
- typed order-lifecycle contracts;
- centralized order-state / registry semantics;
- event vocabulary;
- explicit OMS runtime foundation.
"""

from .events import (
    OmsEventSource,
    OmsEventType,
    OmsOrderPayload,
    build_oms_event,
    default_priority_for_oms_event,
)
from .models import (
    OmsContext,
    OmsFreshness,
    OmsLifecycleStatus,
    OmsOrderLocator,
    OmsOrderRecord,
    OmsQueryScope,
    OmsReasonCode,
    OmsSource,
    OmsValidity,
    OmsValidityStatus,
)
from .runtime import (
    OmsRuntime,
    OmsRuntimeConfig,
    OmsRuntimeDiagnostics,
    OmsRuntimeLifecycleState,
    OmsRuntimeUpdate,
    OmsStateKey,
    create_oms_runtime,
)

__all__ = [
    "OmsContext",
    "OmsEventSource",
    "OmsEventType",
    "OmsFreshness",
    "OmsLifecycleStatus",
    "OmsOrderLocator",
    "OmsOrderPayload",
    "OmsOrderRecord",
    "OmsQueryScope",
    "OmsReasonCode",
    "OmsRuntime",
    "OmsRuntimeConfig",
    "OmsRuntimeDiagnostics",
    "OmsRuntimeLifecycleState",
    "OmsRuntimeUpdate",
    "OmsSource",
    "OmsStateKey",
    "OmsValidity",
    "OmsValidityStatus",
    "build_oms_event",
    "create_oms_runtime",
    "default_priority_for_oms_event",
]
