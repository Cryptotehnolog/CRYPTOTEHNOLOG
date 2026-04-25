export type LiveFeedPolicySettingsResponse = {
  retry_delay_seconds: number;
  bybit_spot_universe_min_quote_volume_24h_usd: number;
  bybit_spot_universe_min_trade_count_24h: number;
  bybit_spot_quote_asset_filter: "usdt" | "usdc" | "usdt_usdc";
};

export type BybitConnectorSymbolSnapshotResponse = {
  symbol: string;
  trade_seen: boolean;
  orderbook_seen: boolean;
  trade_ingest_seen: boolean;
  orderbook_ingest_seen: boolean;
  best_bid: string | null;
  best_ask: string | null;
  volume_24h_usd: string | null;
  derived_trade_count_24h: number | null;
  bucket_trade_count_24h: number | null;
  ledger_trade_count_24h: number | null;
  trade_count_reconciliation_verdict: string | null;
  trade_count_reconciliation_reason: string | null;
  trade_count_reconciliation_absolute_diff: number | null;
  trade_count_reconciliation_tolerance: number | null;
  trade_count_cutover_readiness_state: string | null;
  trade_count_cutover_readiness_reason: string | null;
  observed_trade_count_since_reset: number;
  product_trade_count_24h: number | null;
  product_trade_count_state: string | null;
  product_trade_count_reason: string | null;
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
  application_ping_sent_at: string | null;
  application_pong_at: string | null;
  application_heartbeat_latency_ms: number | null;
  degraded_reason: string | null;
  last_disconnect_reason: string | null;
  retry_count: number | null;
  ready: boolean;
  started: boolean;
  lifecycle_state: string | null;
  reset_required: boolean;
  derived_trade_count_state: string | null;
  derived_trade_count_ready: boolean;
  derived_trade_count_observation_started_at: string | null;
  derived_trade_count_reliable_after: string | null;
  derived_trade_count_last_gap_at: string | null;
  derived_trade_count_last_gap_reason: string | null;
  derived_trade_count_backfill_status: string | null;
  derived_trade_count_backfill_needed: boolean | null;
  derived_trade_count_backfill_processed_archives: number | null;
  derived_trade_count_backfill_total_archives: number | null;
  derived_trade_count_backfill_progress_percent: number | null;
  derived_trade_count_last_backfill_at: string | null;
  derived_trade_count_last_backfill_source: string | null;
  derived_trade_count_last_backfill_reason: string | null;
  desired_scope_mode: string | null;
  desired_trade_count_filter_minimum: number | null;
  applied_scope_mode: string | null;
  applied_trade_count_filter_minimum: number | null;
  policy_apply_status: string | null;
  policy_apply_reason: string | null;
  operator_runtime_state: string | null;
  operator_runtime_reason: string | null;
  operator_confidence_state: string | null;
  operator_confidence_reason: string | null;
  operational_recovery_state?: string | null;
  operational_recovery_reason?: string | null;
  canonical_ledger_sync_state?: string | null;
  canonical_ledger_sync_reason?: string | null;
  operator_state_surface?: {
    runtime?: {
      state: string | null;
      reason: string | null;
    } | null;
    ledger_sync?: {
      state: string | null;
      reason: string | null;
    } | null;
  } | null;
  historical_recovery_state: string | null;
  historical_recovery_reason: string | null;
  historical_recovery_retry_pending: boolean;
  historical_recovery_backfill_task_active: boolean;
  historical_recovery_retry_task_active: boolean;
  historical_recovery_cutoff_at: string | null;
  archive_cache_enabled: boolean;
  archive_cache_memory_hits: number;
  archive_cache_disk_hits: number;
  archive_cache_misses: number;
  archive_cache_writes: number;
  archive_cache_last_hit_source: string | null;
  archive_cache_last_url: string | null;
  archive_cache_last_cleanup_at: string | null;
  archive_cache_last_pruned_files: number;
  scope_mode: string;
  total_instruments_discovered: number | null;
  instruments_passed_coarse_filter: number | null;
  quote_volume_filter_ready: boolean | null;
  trade_count_filter_ready: boolean | null;
  instruments_passed_trade_count_filter: number | null;
  universe_admission_state: string | null;
  trade_count_product_truth_state: string | null;
  trade_count_product_truth_reason: string | null;
  trade_count_admission_basis: string | null;
  active_subscribed_scope_count: number;
  live_trade_streams_count: number;
  live_orderbook_count: number;
  degraded_or_stale_count: number;
};

export type BybitSpotConnectorDiagnosticsResponse = BybitConnectorDiagnosticsResponse;

export type BybitSpotRuntimeStatusResponse = {
  generation: string;
  desired_running: boolean;
  transport_status: string;
  subscription_alive: boolean;
  transport_rtt_ms: number | null;
  last_message_at: string | null;
  messages_received_count: number;
  retry_count: number;
  trade_ingest_count: number;
  orderbook_ingest_count: number;
  trade_seen: boolean;
  orderbook_seen: boolean;
  best_bid: string | null;
  best_ask: string | null;
  persisted_trade_count: number;
  last_persisted_trade_at: string | null;
  last_persisted_trade_symbol: string | null;
  recovery_status: string | null;
  recovery_stage: string | null;
  recovery_reason: string | null;
  scope_mode: string;
  total_instruments_discovered: number | null;
  volume_filtered_symbols_count?: number | null;
  filtered_symbols_count?: number | null;
  selected_symbols_count: number;
  scope_limit_applied?: boolean;
  lifecycle_state?: string;
  symbols: string[];
};

export type BybitSpotProductSnapshotResponse = BybitSpotRuntimeStatusResponse & {
  observed_at: string | null;
  persistence_24h: {
    live_trade_count_24h: number;
    archive_trade_count_24h: number;
    persisted_trade_count_24h: number;
    first_persisted_trade_at: string | null;
    last_persisted_trade_at: string | null;
    coverage_status: string;
  };
  instrument_rows: Array<{
    symbol: string;
    volume_24h_usd: string | null;
    trade_count_24h: number | null;
  }>;
};

export type BybitSpotV2DiagnosticsSymbolResponse = {
  normalized_symbol: string;
  volume_24h_usd: string | null;
  reconciliation_verdict: string;
  reconciliation_reason: string;
  absolute_diff: number | null;
  derived_trade_count_24h: number | null;
  persisted_trade_count_24h: number;
};

export type BybitSpotV2DiagnosticsResponse = {
  generation: string;
  status: string;
  observed_at: string | null;
  symbols: string[];
  transport: {
    transport_status: string | null;
    subscription_alive: boolean;
    transport_rtt_ms: number | null;
    last_message_at: string | null;
    messages_received_count: number;
  };
  ingest: {
    trade_seen: boolean;
    orderbook_seen: boolean;
    best_bid: string | null;
    best_ask: string | null;
    trade_ingest_count: number;
    orderbook_ingest_count: number;
  };
  persistence: {
    requested_window_started_at: string | null;
    count_window_started_at: string | null;
    window_ended_at: string | null;
    window_contract: string | null;
    split_contract: string | null;
    live_trade_count_24h: number;
    archive_trade_count_24h: number;
    persisted_trade_count_24h: number;
    first_persisted_trade_at: string | null;
    last_persisted_trade_at: string | null;
    earliest_trade_at: string | null;
    latest_trade_at: string | null;
    symbols_covered: string[];
    coverage_status: string;
  };
  recovery: {
    status: string | null;
    stage: string | null;
    reason: string | null;
    last_progress_checkpoint: string | null;
  };
  reconciliation: {
    scope_verdict: string | null;
    scope_reason: string | null;
    symbols: BybitSpotV2DiagnosticsSymbolResponse[];
  };
};
