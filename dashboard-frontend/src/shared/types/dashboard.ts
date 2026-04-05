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

export type OpenPositionResponse = {
  position_id: string;
  symbol: string;
  exchange: string;
  strategy: string | null;
  side: string;
  entry_price: string | number;
  quantity: string | number;
  initial_stop: string | number;
  current_stop: string | number;
  current_risk_usd: string | number;
  current_risk_r: string | number;
  current_price: string | number;
  unrealized_pnl_usd: string | number;
  unrealized_pnl_percent: string | number;
  trailing_state: string;
  opened_at: string;
  updated_at: string;
};

export type OpenPositionsResponse = {
  positions: OpenPositionResponse[];
};

export type PositionHistoryRecordResponse = {
  position_id: string;
  symbol: string;
  exchange: string;
  strategy: string | null;
  side: string;
  entry_price: string | number;
  quantity: string | number;
  initial_stop: string | number;
  current_stop: string | number;
  trailing_state: string;
  opened_at: string;
  closed_at: string;
  exit_price: string | number | null;
  exit_reason: string | null;
  realized_pnl_r: string | number | null;
  realized_pnl_usd: string | number | null;
  realized_pnl_percent: string | number | null;
};

export type PositionHistoryResponse = {
  positions: PositionHistoryRecordResponse[];
};

export type UniversePolicySettingsResponse = {
  max_spread_bps: number;
  min_top_depth_usd: number;
  min_depth_5bps_usd: number;
  max_latency_ms: number;
  min_coverage_ratio: number;
  max_data_age_ms: number;
  min_quality_score: number;
  min_ready_instruments: number;
  min_degraded_instruments_ratio: number;
  min_ready_confidence: number;
  min_degraded_confidence: number;
};

export type DecisionChainSettingsResponse = {
  signal_min_trend_strength: number;
  signal_min_regime_confidence: number;
  signal_target_risk_reward: number;
  signal_max_age_seconds: number;
  strategy_min_signal_confidence: number;
  strategy_max_candidate_age_seconds: number;
  execution_min_strategy_confidence: number;
  execution_max_intent_age_seconds: number;
  opportunity_min_confidence: number;
  opportunity_min_priority: number;
  opportunity_max_age_seconds: number;
  orchestration_min_confidence: number;
  orchestration_min_priority: number;
  orchestration_max_decision_age_seconds: number;
};

export type RiskLimitsSettingsResponse = {
  base_r_percent: number;
  max_r_per_trade: number;
  max_portfolio_r: number;
  risk_max_total_exposure_usd: number;
  max_position_size: number;
  risk_starting_equity: number;
};

export type TrailingPolicySettingsResponse = {
  arm_at_pnl_r: number;
  t2_at_pnl_r: number;
  t3_at_pnl_r: number;
  t4_at_pnl_r: number;
  t1_atr_multiplier: number;
  t2_atr_multiplier: number;
  t3_atr_multiplier: number;
  t4_atr_multiplier: number;
  emergency_buffer_bps: number;
  structural_min_adx: number;
  structural_confirmed_highs: number;
  structural_confirmed_lows: number;
};

export type CorrelationPolicySettingsResponse = {
  correlation_limit: number;
  same_group_correlation: number;
  cross_group_correlation: number;
};

export type ProtectionPolicySettingsResponse = {
  halt_priority_threshold: number;
  freeze_priority_threshold: number;
};

export type FundingPolicySettingsResponse = {
  min_arbitrage_spread: number;
  min_annualized_spread: number;
  max_acceptable_funding: number;
  min_exchange_improvement: number;
  min_quotes_for_opportunity: number;
};

export type SystemStatePolicySettingsResponse = {
  trading_risk_multiplier: number;
  trading_max_positions: number;
  trading_max_order_size: number;
  degraded_risk_multiplier: number;
  degraded_max_positions: number;
  degraded_max_order_size: number;
  risk_reduction_risk_multiplier: number;
  risk_reduction_max_positions: number;
  risk_reduction_max_order_size: number;
  survival_risk_multiplier: number;
  survival_max_positions: number;
  survival_max_order_size: number;
};

export type SystemStateTimeoutSettingsResponse = {
  boot_max_seconds: number;
  init_max_seconds: number;
  ready_max_seconds: number;
  risk_reduction_max_seconds: number;
  degraded_max_seconds: number;
  survival_max_seconds: number;
  error_max_seconds: number;
  recovery_max_seconds: number;
};

export type ReliabilityPolicySettingsResponse = {
  circuit_breaker_failure_threshold: number;
  circuit_breaker_recovery_timeout_seconds: number;
  circuit_breaker_success_threshold: number;
  watchdog_failure_threshold: number;
  watchdog_backoff_base_seconds: number;
  watchdog_backoff_multiplier: number;
  watchdog_max_backoff_seconds: number;
  watchdog_jitter_factor: number;
  watchdog_check_interval_seconds: number;
};

export type HealthPolicySettingsResponse = {
  check_timeout_seconds: number;
  background_check_interval_seconds: number;
  check_and_wait_timeout_seconds: number;
};

export type EventBusPolicySettingsResponse = {
  subscriber_capacity: number;
  fill_ratio_low: number;
  fill_ratio_normal: number;
  fill_ratio_high: number;
  push_wait_timeout_seconds: number;
  drain_timeout_seconds: number;
};

export type ManualApprovalPolicySettingsResponse = {
  approval_timeout_minutes: number;
};

export type WorkflowTimeoutsSettingsResponse = {
  manager_max_age_seconds: number;
  validation_max_age_seconds: number;
  paper_max_age_seconds: number;
  replay_max_age_seconds: number;
};

export type LiveFeedPolicySettingsResponse = {
  retry_delay_seconds: number;
  bybit_connector_scope_mode: string;
  bybit_connector_symbol: string | null;
  bybit_spot_connector_scope_mode: string;
  bybit_spot_connector_symbol: string | null;
  bybit_universe_min_quote_volume_24h_usd: number;
  bybit_universe_min_trade_count_24h: number;
  bybit_universe_max_symbols_per_scope: number;
};

export type BybitConnectorSymbolSnapshotResponse = {
  symbol: string;
  trade_seen: boolean;
  orderbook_seen: boolean;
  best_bid: string | null;
  best_ask: string | null;
};

export type BybitConnectorDiagnosticsResponse = {
  enabled: boolean;
  symbol: string | null;
  symbols: string[];
  symbol_snapshots: BybitConnectorSymbolSnapshotResponse[];
  transport_status: string;
  recovery_status: string;
  subscription_alive: boolean;
  trade_seen: boolean;
  orderbook_seen: boolean;
  best_bid: string | null;
  best_ask: string | null;
  last_message_at: string | null;
  message_age_ms: number | null;
  transport_rtt_ms: number | null;
  degraded_reason: string | null;
  last_disconnect_reason: string | null;
  retry_count: number | null;
  ready: boolean;
  started: boolean;
  lifecycle_state: string | null;
  reset_required: boolean;
  scope_mode: string;
  total_instruments_discovered: number | null;
  instruments_passed_coarse_filter: number | null;
  active_subscribed_scope_count: number;
  live_trade_streams_count: number;
  live_orderbook_count: number;
  degraded_or_stale_count: number;
};

export type BybitSpotConnectorDiagnosticsResponse = BybitConnectorDiagnosticsResponse;
