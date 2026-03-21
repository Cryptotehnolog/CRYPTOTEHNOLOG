"""
Contract-first package boundary для Phase 9 Strategy Foundation.

На шаге `Strategy Contract Lock` здесь фиксируются:
- typed strategy contracts;
- strategy validity / readiness semantics;
- strategy event vocabulary;
- typed runtime boundary shape для следующего шага.
"""

from .events import (
    StrategyActionCandidatePayload,
    StrategyEventSource,
    StrategyEventType,
    build_strategy_event,
    default_priority_for_strategy_event,
)
from .models import (
    StrategyActionCandidate,
    StrategyContext,
    StrategyDirection,
    StrategyFreshness,
    StrategyReasonCode,
    StrategyStatus,
    StrategyValidity,
    StrategyValidityStatus,
)
from .runtime import (
    StrategyRuntime,
    StrategyRuntimeConfig,
    StrategyRuntimeDiagnostics,
    StrategyRuntimeLifecycleState,
    StrategyRuntimeUpdate,
    create_strategy_runtime,
)

__all__ = [
    "StrategyActionCandidate",
    "StrategyActionCandidatePayload",
    "StrategyContext",
    "StrategyDirection",
    "StrategyEventSource",
    "StrategyEventType",
    "StrategyFreshness",
    "StrategyReasonCode",
    "StrategyRuntime",
    "StrategyRuntimeConfig",
    "StrategyRuntimeDiagnostics",
    "StrategyRuntimeLifecycleState",
    "StrategyRuntimeUpdate",
    "StrategyStatus",
    "StrategyValidity",
    "StrategyValidityStatus",
    "build_strategy_event",
    "create_strategy_runtime",
    "default_priority_for_strategy_event",
]
