"""
Contract-first package boundary для Phase 14 Portfolio Governor Foundation.

На шаге `Portfolio Governor Contract Lock` здесь фиксируются:
- typed portfolio-governor contracts;
- capital-governance / portfolio-admission semantics;
- approve / abstain / reject semantics;
- event vocabulary;
- typed runtime boundary shape для следующего шага.
"""

from .events import (
    PortfolioGovernorEventSource,
    PortfolioGovernorEventType,
    PortfolioGovernorPayload,
    build_portfolio_governor_event,
    default_priority_for_portfolio_governor_event,
)
from .models import (
    GovernorContext,
    GovernorDecision,
    GovernorDirection,
    GovernorFreshness,
    GovernorReasonCode,
    GovernorSource,
    GovernorStatus,
    GovernorValidity,
    GovernorValidityStatus,
    PortfolioGovernorCandidate,
)
from .runtime import (
    PortfolioGovernorRuntime,
    PortfolioGovernorRuntimeConfig,
    PortfolioGovernorRuntimeDiagnostics,
    PortfolioGovernorRuntimeLifecycleState,
    PortfolioGovernorRuntimeUpdate,
    PortfolioGovernorStateKey,
    create_portfolio_governor_runtime,
)

__all__ = [
    "GovernorContext",
    "GovernorDecision",
    "GovernorDirection",
    "GovernorFreshness",
    "GovernorReasonCode",
    "GovernorSource",
    "GovernorStatus",
    "GovernorValidity",
    "GovernorValidityStatus",
    "PortfolioGovernorCandidate",
    "PortfolioGovernorEventSource",
    "PortfolioGovernorEventType",
    "PortfolioGovernorPayload",
    "PortfolioGovernorRuntime",
    "PortfolioGovernorRuntimeConfig",
    "PortfolioGovernorRuntimeDiagnostics",
    "PortfolioGovernorRuntimeLifecycleState",
    "PortfolioGovernorRuntimeUpdate",
    "PortfolioGovernorStateKey",
    "build_portfolio_governor_event",
    "create_portfolio_governor_runtime",
    "default_priority_for_portfolio_governor_event",
]
