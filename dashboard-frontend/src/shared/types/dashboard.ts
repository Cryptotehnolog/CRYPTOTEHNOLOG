export type ModuleStatus = "inactive" | "read-only" | "active" | "restricted";

export type OverviewSnapshotResponse = {
  system_state: {
    is_running: boolean;
    is_shutting_down: boolean;
    current_state: string;
    startup_phase: string;
    shutdown_phase: string;
    uptime_seconds: number;
    trade_allowed: boolean;
    last_error: string | null;
  };
  health_summary: {
    overall_status: string;
    component_count: number;
    unhealthy_components: string[];
    timestamp: number | null;
  };
  pending_approvals: {
    pending_count: number;
    total_requests: number;
    request_timeout_minutes: number;
  };
  event_summary: {
    total_published: number;
    total_delivered: number;
    total_dropped: number;
    total_rate_limited: number;
    subscriber_count: number;
    persistence_enabled: boolean;
    backpressure_strategy: string;
  };
  circuit_breaker_summary: Array<{
    name: string;
    state: string;
    failure_count: number;
    success_count: number;
    failure_threshold: number;
    recovery_timeout: number;
  }>;
  module_availability: Array<{
    key: string;
    title: string;
    description: string;
    route: string;
    status: ModuleStatus;
    phase: string;
    status_reason: string | null;
  }>;
  alerts_summary: {
    connected: boolean;
    note: string;
  };
};

export type RiskConstraintResponse = {
  key: string;
  label: string;
  value: string;
  status: "blocked" | "limited" | "normal" | "warning" | "info";
  note: string | null;
};

export type RiskSummaryResponse = {
  module_status: ModuleStatus;
  current_state: string;
  global_status: "blocked" | "limited" | "normal";
  limiting_state: string;
  trading_blocked: boolean;
  active_risk_path: string | null;
  state_note: string;
  summary_reason: string | null;
  constraints: RiskConstraintResponse[];
};

export type SignalAvailabilityItemResponse = {
  key: string;
  label: string;
  value: string;
  status: "normal" | "warning" | "info";
  note: string | null;
};

export type SignalsSummaryResponse = {
  module_status: ModuleStatus;
  global_status: "inactive" | "warming" | "ready" | "degraded";
  lifecycle_state: string;
  started: boolean;
  ready: boolean;
  tracked_signal_keys: number;
  active_signal_keys: number;
  last_signal_id: string | null;
  last_event_type: string | null;
  last_context_at: string | null;
  active_signal_path: string;
  freshness_state: string;
  summary_note: string;
  summary_reason: string | null;
  availability: SignalAvailabilityItemResponse[];
};

export type StrategyAvailabilityItemResponse = {
  key: string;
  label: string;
  value: string;
  status: "normal" | "warning" | "info";
  note: string | null;
};

export type StrategySummaryResponse = {
  module_status: ModuleStatus;
  global_status: "inactive" | "warming" | "ready" | "degraded";
  lifecycle_state: string;
  started: boolean;
  ready: boolean;
  tracked_context_keys: number;
  tracked_candidate_keys: number;
  actionable_candidate_keys: number;
  last_signal_id: string | null;
  last_candidate_id: string | null;
  last_event_type: string | null;
  active_strategy_path: string;
  strategy_source: string;
  freshness_state: string;
  summary_note: string;
  summary_reason: string | null;
  availability: StrategyAvailabilityItemResponse[];
};

export type ExecutionAvailabilityItemResponse = {
  key: string;
  label: string;
  value: string;
  status: "normal" | "warning" | "info";
  note: string | null;
};

export type OpportunityAvailabilityItemResponse = {
  key: string;
  label: string;
  value: string;
  status: "normal" | "warning" | "info";
  note: string | null;
};

export type OpportunitySummaryResponse = {
  module_status: ModuleStatus;
  global_status: "inactive" | "warming" | "ready" | "degraded";
  lifecycle_state: string;
  started: boolean;
  ready: boolean;
  tracked_context_keys: number;
  tracked_selection_keys: number;
  selected_keys: number;
  last_intent_id: string | null;
  last_selection_id: string | null;
  last_event_type: string | null;
  active_opportunity_path: string;
  opportunity_source: string;
  freshness_state: string;
  summary_note: string;
  summary_reason: string | null;
  availability: OpportunityAvailabilityItemResponse[];
};

export type OrchestrationAvailabilityItemResponse = {
  key: string;
  label: string;
  value: string;
  status: "normal" | "warning" | "info";
  note: string | null;
};

export type OrchestrationSummaryResponse = {
  module_status: ModuleStatus;
  global_status: "inactive" | "warming" | "ready" | "degraded";
  lifecycle_state: string;
  started: boolean;
  ready: boolean;
  tracked_context_keys: number;
  tracked_decision_keys: number;
  forwarded_keys: number;
  abstained_keys: number;
  invalidated_decision_keys: number;
  expired_decision_keys: number;
  last_selection_id: string | null;
  last_decision_id: string | null;
  last_event_type: string | null;
  active_orchestration_path: string;
  orchestration_source: string;
  freshness_state: string;
  summary_note: string;
  summary_reason: string | null;
  availability: OrchestrationAvailabilityItemResponse[];
};

export type PositionExpansionAvailabilityItemResponse = {
  key: string;
  label: string;
  value: string;
  status: "normal" | "warning" | "info";
  note: string | null;
};

export type PositionExpansionSummaryResponse = {
  module_status: ModuleStatus;
  global_status: "inactive" | "warming" | "ready" | "degraded";
  lifecycle_state: string;
  started: boolean;
  ready: boolean;
  tracked_context_keys: number;
  tracked_expansion_keys: number;
  expandable_keys: number;
  abstained_keys: number;
  rejected_keys: number;
  invalidated_expansion_keys: number;
  expired_expansion_keys: number;
  last_decision_id: string | null;
  last_expansion_id: string | null;
  last_event_type: string | null;
  active_position_expansion_path: string;
  position_expansion_source: string;
  freshness_state: string;
  summary_note: string;
  summary_reason: string | null;
  availability: PositionExpansionAvailabilityItemResponse[];
};

export type PortfolioGovernorAvailabilityItemResponse = {
  key: string;
  label: string;
  value: string;
  status: "normal" | "warning" | "info";
  note: string | null;
};

export type PortfolioGovernorSummaryResponse = {
  module_status: ModuleStatus;
  global_status: "inactive" | "warming" | "ready" | "degraded";
  lifecycle_state: string;
  started: boolean;
  ready: boolean;
  tracked_context_keys: number;
  tracked_governor_keys: number;
  approved_keys: number;
  abstained_keys: number;
  rejected_keys: number;
  invalidated_governor_keys: number;
  expired_governor_keys: number;
  last_expansion_id: string | null;
  last_governor_id: string | null;
  last_event_type: string | null;
  active_portfolio_governor_path: string;
  portfolio_governor_source: string;
  freshness_state: string;
  summary_note: string;
  summary_reason: string | null;
  availability: PortfolioGovernorAvailabilityItemResponse[];
};

export type ExecutionSummaryResponse = {
  module_status: ModuleStatus;
  global_status: "inactive" | "warming" | "ready" | "degraded";
  lifecycle_state: string;
  started: boolean;
  ready: boolean;
  tracked_context_keys: number;
  tracked_intent_keys: number;
  executable_intent_keys: number;
  last_candidate_id: string | null;
  last_intent_id: string | null;
  last_event_type: string | null;
  active_execution_path: string;
  execution_source: string;
  freshness_state: string;
  summary_note: string;
  summary_reason: string | null;
  availability: ExecutionAvailabilityItemResponse[];
};

export type OmsAvailabilityItemResponse = {
  key: string;
  label: string;
  value: string;
  status: "normal" | "warning" | "info";
  note: string | null;
};

export type OmsSummaryResponse = {
  module_status: ModuleStatus;
  global_status: "inactive" | "warming" | "ready" | "degraded";
  lifecycle_state: string;
  started: boolean;
  ready: boolean;
  tracked_contexts: number;
  tracked_active_orders: number;
  tracked_historical_orders: number;
  last_intent_id: string | null;
  last_order_id: string | null;
  last_event_type: string | null;
  active_oms_path: string;
  oms_source: string;
  freshness_state: string;
  summary_note: string;
  summary_reason: string | null;
  availability: OmsAvailabilityItemResponse[];
};

export type ManagerAvailabilityItemResponse = {
  key: string;
  label: string;
  value: string;
  status: "normal" | "warning" | "info";
  note: string | null;
};

export type ManagerSummaryResponse = {
  module_status: ModuleStatus;
  global_status: "inactive" | "warming" | "ready" | "degraded";
  lifecycle_state: string;
  started: boolean;
  ready: boolean;
  tracked_contexts: number;
  tracked_active_workflows: number;
  tracked_historical_workflows: number;
  last_workflow_id: string | null;
  last_event_type: string | null;
  active_manager_path: string;
  manager_source: string;
  freshness_state: string;
  summary_note: string;
  summary_reason: string | null;
  availability: ManagerAvailabilityItemResponse[];
};

export type ValidationAvailabilityItemResponse = {
  key: string;
  label: string;
  value: string;
  status: "normal" | "warning" | "info";
  note: string | null;
};

export type ValidationSummaryResponse = {
  module_status: ModuleStatus;
  global_status: "inactive" | "warming" | "ready" | "degraded";
  lifecycle_state: string;
  started: boolean;
  ready: boolean;
  tracked_contexts: number;
  tracked_active_reviews: number;
  tracked_historical_reviews: number;
  last_review_id: string | null;
  last_event_type: string | null;
  active_validation_path: string;
  validation_source: string;
  freshness_state: string;
  summary_note: string;
  summary_reason: string | null;
  availability: ValidationAvailabilityItemResponse[];
};

export type PaperAvailabilityItemResponse = {
  key: string;
  label: string;
  value: string;
  status: "normal" | "warning" | "info";
  note: string | null;
};

export type PaperSummaryResponse = {
  module_status: ModuleStatus;
  global_status: "inactive" | "warming" | "ready" | "degraded";
  lifecycle_state: string;
  started: boolean;
  ready: boolean;
  tracked_contexts: number;
  tracked_active_rehearsals: number;
  tracked_historical_rehearsals: number;
  last_rehearsal_id: string | null;
  last_event_type: string | null;
  active_paper_path: string;
  paper_source: string;
  freshness_state: string;
  summary_note: string;
  summary_reason: string | null;
  availability: PaperAvailabilityItemResponse[];
};

export type BacktestAvailabilityItemResponse = {
  key: string;
  label: string;
  value: string;
  status: "normal" | "warning" | "info";
  note: string | null;
};

export type BacktestSummaryResponse = {
  module_status: ModuleStatus;
  global_status: "inactive" | "warming" | "ready" | "degraded";
  lifecycle_state: string;
  started: boolean;
  ready: boolean;
  tracked_inputs: number;
  tracked_contexts: number;
  tracked_active_replays: number;
  tracked_historical_replays: number;
  last_replay_id: string | null;
  last_event_type: string | null;
  active_backtest_path: string;
  backtest_source: string;
  freshness_state: string;
  summary_note: string;
  summary_reason: string | null;
  availability: BacktestAvailabilityItemResponse[];
};

export type ReportingCatalogCountsResponse = {
  total_artifacts: number;
  total_bundles: number;
  validation_artifacts: number;
  paper_artifacts: number;
  replay_artifacts: number;
};

export type ReportingLastArtifactResponse = {
  kind: string;
  status: string;
  source_layer: string;
  generated_at: string;
};

export type ReportingLastBundleResponse = {
  reporting_name: string;
  generated_at: string;
  artifact_count: number;
};

export type ReportingSummaryResponse = {
  module_status: ModuleStatus;
  global_status: "inactive" | "warming" | "ready";
  catalog_counts: ReportingCatalogCountsResponse;
  last_artifact_snapshot: ReportingLastArtifactResponse | null;
  last_bundle_snapshot: ReportingLastBundleResponse | null;
  summary_note: string;
  summary_reason: string | null;
};
