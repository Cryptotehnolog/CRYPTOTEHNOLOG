"""Typed snapshot contracts для dashboard facade layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class PendingApprovalsSnapshot:
    """Стабильный snapshot pending approvals для dashboard layer."""

    pending_count: int
    total_requests: int
    request_timeout_minutes: int


@dataclass(frozen=True, slots=True)
class EventSummarySnapshot:
    """Стабильный snapshot event summary для dashboard layer."""

    total_published: int
    total_delivered: int
    total_dropped: int
    total_rate_limited: int
    subscriber_count: int
    persistence_enabled: bool
    backpressure_strategy: str


@dataclass(frozen=True, slots=True)
class CircuitBreakerSnapshot:
    """Стабильный snapshot circuit breaker summary для dashboard layer."""

    name: str
    state: str
    failure_count: int
    success_count: int
    failure_threshold: int
    recovery_timeout: int


@dataclass(frozen=True, slots=True)
class RiskRuntimeSnapshot:
    """Стабильный runtime snapshot risk boundary для dashboard layer."""

    active_risk_path: str | None
    risk_multiplier: float
    allow_new_positions: bool
    allow_new_orders: bool
    max_positions: int
    max_order_size: float
    require_manual_approval: bool
    policy_description: str


@dataclass(frozen=True, slots=True)
class RiskConfigSnapshot:
    """Стабильный config snapshot risk limits для dashboard layer."""

    base_r_percent: float
    max_r_per_trade: float
    max_portfolio_r: float
    max_total_exposure_usd: float
    max_position_size_usd: float
    kill_switch_enabled: bool


@dataclass(frozen=True, slots=True)
class SignalSummarySnapshot:
    """Стабильный diagnostics snapshot signal runtime для dashboard layer."""

    started: bool
    ready: bool
    lifecycle_state: str
    tracked_signal_keys: int
    active_signal_keys: int
    invalidated_signal_keys: int
    expired_signal_keys: int
    last_context_at: str | None
    last_signal_id: str | None
    last_event_type: str | None
    last_failure_reason: str | None
    readiness_reasons: tuple[str, ...]
    degraded_reasons: tuple[str, ...]
    active_signal_path: str


@dataclass(frozen=True, slots=True)
class StrategySummarySnapshot:
    """Стабильный diagnostics snapshot strategy runtime для dashboard layer."""

    started: bool
    ready: bool
    lifecycle_state: str
    tracked_context_keys: int
    tracked_candidate_keys: int
    actionable_candidate_keys: int
    invalidated_candidate_keys: int
    expired_candidate_keys: int
    last_signal_id: str | None
    last_candidate_id: str | None
    last_event_type: str | None
    last_failure_reason: str | None
    readiness_reasons: tuple[str, ...]
    degraded_reasons: tuple[str, ...]
    active_strategy_path: str
    strategy_source: str


@dataclass(frozen=True, slots=True)
class ExecutionSummarySnapshot:
    """Стабильный diagnostics snapshot execution runtime для dashboard layer."""

    started: bool
    ready: bool
    lifecycle_state: str
    tracked_context_keys: int
    tracked_intent_keys: int
    executable_intent_keys: int
    invalidated_intent_keys: int
    expired_intent_keys: int
    last_candidate_id: str | None
    last_intent_id: str | None
    last_event_type: str | None
    last_failure_reason: str | None
    readiness_reasons: tuple[str, ...]
    degraded_reasons: tuple[str, ...]
    active_execution_path: str
    execution_source: str


@dataclass(frozen=True, slots=True)
class OpportunitySummarySnapshot:
    """Стабильный diagnostics snapshot opportunity runtime для dashboard layer."""

    started: bool
    ready: bool
    lifecycle_state: str
    tracked_context_keys: int
    tracked_selection_keys: int
    selected_keys: int
    invalidated_selection_keys: int
    expired_selection_keys: int
    last_intent_id: str | None
    last_selection_id: str | None
    last_event_type: str | None
    last_failure_reason: str | None
    readiness_reasons: tuple[str, ...]
    degraded_reasons: tuple[str, ...]
    active_opportunity_path: str
    opportunity_source: str


@dataclass(frozen=True, slots=True)
class OrchestrationSummarySnapshot:
    """Стабильный diagnostics snapshot orchestration runtime для dashboard layer."""

    started: bool
    ready: bool
    lifecycle_state: str
    tracked_context_keys: int
    tracked_decision_keys: int
    forwarded_keys: int
    abstained_keys: int
    invalidated_decision_keys: int
    expired_decision_keys: int
    last_selection_id: str | None
    last_decision_id: str | None
    last_event_type: str | None
    last_failure_reason: str | None
    readiness_reasons: tuple[str, ...]
    degraded_reasons: tuple[str, ...]
    active_orchestration_path: str
    orchestration_source: str


@dataclass(frozen=True, slots=True)
class PositionExpansionSummarySnapshot:
    """Стабильный diagnostics snapshot position-expansion runtime для dashboard layer."""

    started: bool
    ready: bool
    lifecycle_state: str
    tracked_context_keys: int
    tracked_expansion_keys: int
    expandable_keys: int
    abstained_keys: int
    rejected_keys: int
    invalidated_expansion_keys: int
    expired_expansion_keys: int
    last_decision_id: str | None
    last_expansion_id: str | None
    last_event_type: str | None
    last_failure_reason: str | None
    readiness_reasons: tuple[str, ...]
    degraded_reasons: tuple[str, ...]
    active_position_expansion_path: str
    position_expansion_source: str


@dataclass(frozen=True, slots=True)
class PortfolioGovernorSummarySnapshot:
    """Стабильный diagnostics snapshot portfolio-governor runtime для dashboard layer."""

    started: bool
    ready: bool
    lifecycle_state: str
    tracked_context_keys: int
    tracked_governor_keys: int
    approved_keys: int
    abstained_keys: int
    rejected_keys: int
    invalidated_governor_keys: int
    expired_governor_keys: int
    last_expansion_id: str | None
    last_governor_id: str | None
    last_event_type: str | None
    last_failure_reason: str | None
    readiness_reasons: tuple[str, ...]
    degraded_reasons: tuple[str, ...]
    active_portfolio_governor_path: str
    portfolio_governor_source: str


@dataclass(frozen=True, slots=True)
class OmsSummarySnapshot:
    """Стабильный diagnostics snapshot OMS runtime для dashboard layer."""

    started: bool
    ready: bool
    lifecycle_state: str
    tracked_contexts: int
    tracked_active_orders: int
    tracked_historical_orders: int
    last_intent_id: str | None
    last_order_id: str | None
    last_event_type: str | None
    last_failure_reason: str | None
    readiness_reasons: tuple[str, ...]
    degraded_reasons: tuple[str, ...]
    active_oms_path: str
    oms_source: str


@dataclass(frozen=True, slots=True)
class ManagerSummarySnapshot:
    """Стабильный diagnostics snapshot manager runtime для dashboard layer."""

    started: bool
    ready: bool
    lifecycle_state: str
    tracked_contexts: int
    tracked_active_workflows: int
    tracked_historical_workflows: int
    last_workflow_id: str | None
    last_event_type: str | None
    last_failure_reason: str | None
    readiness_reasons: tuple[str, ...]
    degraded_reasons: tuple[str, ...]
    active_manager_path: str
    manager_source: str


@dataclass(frozen=True, slots=True)
class ValidationSummarySnapshot:
    """Стабильный diagnostics snapshot validation runtime для dashboard layer."""

    started: bool
    ready: bool
    lifecycle_state: str
    tracked_contexts: int
    tracked_active_reviews: int
    tracked_historical_reviews: int
    last_review_id: str | None
    last_event_type: str | None
    last_failure_reason: str | None
    readiness_reasons: tuple[str, ...]
    degraded_reasons: tuple[str, ...]
    active_validation_path: str
    validation_source: str


@dataclass(frozen=True, slots=True)
class PaperSummarySnapshot:
    """Стабильный diagnostics snapshot paper runtime для dashboard layer."""

    started: bool
    ready: bool
    lifecycle_state: str
    tracked_contexts: int
    tracked_active_rehearsals: int
    tracked_historical_rehearsals: int
    last_rehearsal_id: str | None
    last_event_type: str | None
    last_failure_reason: str | None
    readiness_reasons: tuple[str, ...]
    degraded_reasons: tuple[str, ...]
    active_paper_path: str
    paper_source: str


@dataclass(frozen=True, slots=True)
class BacktestSummarySnapshot:
    """Стабильный diagnostics snapshot backtest runtime для dashboard layer."""

    started: bool
    ready: bool
    lifecycle_state: str
    tracked_inputs: int
    tracked_contexts: int
    tracked_active_replays: int
    tracked_historical_replays: int
    last_replay_id: str | None
    last_event_type: str | None
    last_failure_reason: str | None
    readiness_reasons: tuple[str, ...]
    degraded_reasons: tuple[str, ...]
    active_backtest_path: str
    backtest_source: str


@dataclass(frozen=True, slots=True)
class ReportingCatalogCountsSnapshot:
    """Стабильные агрегированные счётчики reporting artifact catalog."""

    total_artifacts: int
    total_bundles: int
    validation_artifacts: int
    paper_artifacts: int
    replay_artifacts: int


@dataclass(frozen=True, slots=True)
class ReportingLastArtifactSnapshot:
    """Последний surfaced reporting artifact для dashboard summary."""

    kind: str
    status: str
    source_layer: str
    generated_at: datetime
    source_reason_code: str | None


@dataclass(frozen=True, slots=True)
class ReportingLastBundleSnapshot:
    """Последний surfaced reporting bundle для dashboard summary."""

    reporting_name: str
    generated_at: datetime
    artifact_count: int


@dataclass(frozen=True, slots=True)
class ReportingSummarySnapshot:
    """Стабильный snapshot reporting artifact catalog summary для dashboard layer."""

    catalog_counts: ReportingCatalogCountsSnapshot
    last_artifact_snapshot: ReportingLastArtifactSnapshot | None
    last_bundle_snapshot: ReportingLastBundleSnapshot | None
