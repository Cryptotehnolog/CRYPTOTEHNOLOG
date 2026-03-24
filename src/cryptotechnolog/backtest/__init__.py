"""
Backtesting / Replay Foundation package.

Authoritative Phase 20 truth внутри этого package:
- narrow replay/backtest contracts;
- typed replay event vocabulary;
- explicit runtime boundary shape.

Legacy `ReplayEngine` / `EventRecorder` остаются только как compatibility contour
и не задают автоматически full scope `P_20`.
"""

from __future__ import annotations

# ==================== Authoritative Phase 20 exports ====================
from cryptotechnolog.backtest.events import (
    HistoricalInputPayload,
    ReplayCandidatePayload,
    ReplayEventSource,
    ReplayEventType,
    build_replay_event,
    default_priority_for_replay_event,
)
from cryptotechnolog.backtest.ingress import (
    BarStreamCsvIngressConfig,
    BarStreamIngressFormat,
    BarStreamRecord,
    HistoricalInputIngress,
    HistoricalInputInventoryEntry,
    IntegratedReplayIngressResult,
    LoadedHistoricalBarStream,
    ReplayIngressPath,
    ReplayIngressStateKey,
)
from cryptotechnolog.backtest.models import (
    HistoricalInputContract,
    HistoricalInputKind,
    ReplayCandidate,
    ReplayContext,
    ReplayCoverageWindow,
    ReplayDecision,
    ReplayFreshness,
    ReplayReasonCode,
    ReplayRecorderState,
    ReplaySource,
    ReplayStatus,
    ReplayValidity,
    ReplayValidityStatus,
)
from cryptotechnolog.backtest.runtime import (
    ReplayRuntime,
    ReplayRuntimeConfig,
    ReplayRuntimeDiagnostics,
    ReplayRuntimeLifecycleState,
    ReplayRuntimeUpdate,
    ReplayStateKey,
    create_replay_runtime,
)

__all__ = [
    "BarStreamCsvIngressConfig",
    "BarStreamIngressFormat",
    "BarStreamRecord",
    "HistoricalInputContract",
    "HistoricalInputIngress",
    "HistoricalInputInventoryEntry",
    "HistoricalInputKind",
    "HistoricalInputPayload",
    "IntegratedReplayIngressResult",
    "LoadedHistoricalBarStream",
    "ReplayCandidate",
    "ReplayCandidatePayload",
    "ReplayContext",
    "ReplayCoverageWindow",
    "ReplayDecision",
    "ReplayEventSource",
    "ReplayEventType",
    "ReplayFreshness",
    "ReplayIngressPath",
    "ReplayIngressStateKey",
    "ReplayReasonCode",
    "ReplayRecorderState",
    "ReplayRuntime",
    "ReplayRuntimeConfig",
    "ReplayRuntimeDiagnostics",
    "ReplayRuntimeLifecycleState",
    "ReplayRuntimeUpdate",
    "ReplaySource",
    "ReplayStateKey",
    "ReplayStatus",
    "ReplayValidity",
    "ReplayValidityStatus",
    "build_replay_event",
    "create_replay_runtime",
    "default_priority_for_replay_event",
]

# ==================== Legacy compatibility names ====================
# Эти имена остаются доступны по `cryptotechnolog.backtest.<name>` для
# обратной совместимости, но не входят в authoritative Phase 20 surface.

from cryptotechnolog.backtest.events import (
    BalanceUpdateEvent,
    EventType,
    OrderEvent,
    PositionUpdateEvent,
    TickEvent,
    TradeEvent,
)
from cryptotechnolog.backtest.recorder import EventRecorder
from cryptotechnolog.backtest.replay_engine import ReplayConfig, ReplayEngine
