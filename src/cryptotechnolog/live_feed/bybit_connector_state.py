"""Named snapshot/state models for Bybit connector phase-2 refactoring."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True, frozen=True)
class BybitDiscoverySnapshot:
    exchange: str
    scope_mode: str
    coarse_candidate_symbols: tuple[str, ...]
    discovery_status: str = "ready"
    total_instruments_discovered: int | None = None
    instruments_passed_coarse_filter: int | None = None
    quote_turnover_24h_by_symbol: tuple[tuple[str, str], ...] = ()
    quote_turnover_last_synced_at: str | None = None
    quote_turnover_last_error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_operator_diagnostics_dict(self) -> dict[str, object]:
        return {
            "coarse_candidate_symbols": self.coarse_candidate_symbols,
        }


@dataclass(slots=True, frozen=True)
class BybitTransportSnapshot:
    transport_status: str
    recovery_status: str
    subscription_alive: bool
    last_message_at: str | None
    message_age_ms: int | None
    transport_rtt_ms: int | None
    last_ping_sent_at: str | None
    last_pong_at: str | None
    application_ping_sent_at: str | None
    application_pong_at: str | None
    application_heartbeat_latency_ms: int | None
    last_ping_timeout_at: str | None
    last_ping_timeout_message_age_ms: int | None
    last_ping_timeout_loop_lag_ms: int | None
    last_ping_timeout_backfill_status: str | None
    last_ping_timeout_processed_archives: int | None
    last_ping_timeout_total_archives: int | None
    last_ping_timeout_cache_source: str | None
    last_ping_timeout_ignored_due_to_recent_messages: bool
    degraded_reason: str | None
    last_disconnect_reason: str | None
    retry_count: int | None
    ready: bool
    started: bool
    lifecycle_state: str | None
    reset_required: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_operator_diagnostics_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class BybitTradeTruthSymbolSnapshot:
    symbol: str
    trade_seen: bool
    orderbook_seen: bool
    best_bid: str | None
    best_ask: str | None
    volume_24h_usd: str | None
    derived_trade_count_24h: int | None
    bucket_trade_count_24h: int | None
    ledger_trade_count_24h: int | None
    ledger_trade_count_status: str
    ledger_trade_count_symbol_last_error: str | None
    ledger_trade_count_symbol_last_synced_at: str | None
    trade_count_reconciliation_verdict: str
    trade_count_reconciliation_reason: str
    trade_count_reconciliation_absolute_diff: int | None
    trade_count_reconciliation_tolerance: int | None
    trade_count_cutover_readiness_state: str
    trade_count_cutover_readiness_reason: str
    observed_trade_count_since_reset: int
    product_trade_count_24h: int | None
    product_trade_count_state: str
    product_trade_count_reason: str
    product_trade_count_truth_owner: str
    product_trade_count_truth_source: str
    trade_ingest_seen: bool = False
    orderbook_ingest_seen: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class BybitTradeTruthSnapshot:
    symbol_snapshots: tuple[BybitTradeTruthSymbolSnapshot, ...]
    trade_seen: bool
    orderbook_seen: bool
    best_bid: str | None
    best_ask: str | None
    operational_recovery_state: str
    operational_recovery_reason: str | None
    canonical_ledger_sync_state: str
    canonical_ledger_sync_reason: str | None
    derived_trade_count_state: str | None
    derived_trade_count_ready: bool
    derived_trade_count_observation_started_at: str | None
    derived_trade_count_reliable_after: str | None
    derived_trade_count_last_gap_at: str | None
    derived_trade_count_last_gap_reason: str | None
    derived_trade_count_backfill_status: str | None
    derived_trade_count_backfill_needed: bool
    derived_trade_count_backfill_processed_archives: int | None
    derived_trade_count_backfill_total_archives: int | None
    derived_trade_count_backfill_progress_percent: int | None
    derived_trade_count_last_backfill_at: str | None
    derived_trade_count_last_backfill_source: str | None
    derived_trade_count_last_backfill_reason: str | None
    ledger_trade_count_available: bool
    ledger_trade_count_scope_status: str
    ledger_trade_count_last_error: str | None
    ledger_trade_count_last_synced_at: str | None
    trade_count_truth_model: str
    trade_count_canonical_truth_owner: str
    trade_count_canonical_truth_source: str
    trade_count_operational_truth_owner: str
    trade_count_operational_truth_source: str
    trade_count_connector_canonical_role: str
    trade_count_product_truth_state: str
    trade_count_product_truth_reason: str
    trade_count_cutover_readiness_state: str
    trade_count_cutover_readiness_reason: str
    trade_count_cutover_compared_symbols: int
    trade_count_cutover_ready_symbols: int
    trade_count_cutover_not_ready_symbols: int
    trade_count_cutover_blocked_symbols: int
    trade_count_cutover_evaluation_state: str
    trade_count_cutover_evaluation_reasons: tuple[str, ...]
    trade_count_cutover_evaluation_minimum_compared_symbols: int
    trade_count_cutover_manual_review_state: str
    trade_count_cutover_manual_review_reasons: tuple[str, ...]
    trade_count_cutover_manual_review_evaluation_state: str
    trade_count_cutover_manual_review_contour: str
    trade_count_cutover_manual_review_scope_mode: str
    trade_count_cutover_manual_review_scope_symbol_count: int
    trade_count_cutover_manual_review_compared_symbols: int
    trade_count_cutover_manual_review_ready_symbols: int
    trade_count_cutover_manual_review_not_ready_symbols: int
    trade_count_cutover_manual_review_blocked_symbols: int
    trade_count_cutover_discussion_artifact: dict[str, object]
    trade_count_cutover_review_record: dict[str, object]
    trade_count_cutover_review_package: dict[str, object]
    trade_count_cutover_review_catalog: dict[str, object]
    trade_count_cutover_review_snapshot_collection: dict[str, object]
    trade_count_cutover_review_compact_digest: dict[str, object]
    trade_count_cutover_export_report_bundle: dict[str, object]
    historical_recovery_state: str
    historical_recovery_reason: str | None
    historical_recovery_retry_pending: bool
    historical_recovery_backfill_task_active: bool
    historical_recovery_retry_task_active: bool
    historical_recovery_cutoff_at: str | None
    archive_cache_enabled: bool
    archive_cache_memory_hits: int
    archive_cache_disk_hits: int
    archive_cache_misses: int
    archive_cache_writes: int
    archive_cache_last_hit_source: str | None
    archive_cache_last_url: str | None
    archive_cache_last_cleanup_at: str | None
    archive_cache_last_pruned_files: int
    archive_cache_last_network_fetch_ms: int | None
    archive_cache_last_disk_read_ms: int | None
    archive_cache_last_gzip_decode_ms: int | None
    archive_cache_last_csv_parse_ms: int | None
    archive_cache_last_archive_total_ms: int | None
    archive_cache_last_symbol_total_ms: int | None
    archive_cache_last_symbol: str | None
    archive_cache_total_network_fetch_ms: int
    archive_cache_total_disk_read_ms: int
    archive_cache_total_gzip_decode_ms: int
    archive_cache_total_csv_parse_ms: int
    archive_cache_total_archive_total_ms: int
    archive_cache_total_symbol_total_ms: int

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["symbol_snapshots"] = tuple(
            snapshot.to_dict() for snapshot in self.symbol_snapshots
        )
        return payload

    def to_operator_diagnostics_dict(self) -> dict[str, object]:
        return self.to_dict()


@dataclass(slots=True, frozen=True)
class BybitAdmissionSnapshot:
    scope_mode: str
    trade_count_filter_minimum: int
    trade_count_admission_basis: str
    trade_count_admission_truth_owner: str
    trade_count_admission_truth_source: str
    trade_count_admission_candidate_symbols: tuple[str, ...]
    active_subscribed_symbols: tuple[str, ...]
    trade_count_qualifying_symbols: tuple[str, ...]
    trade_count_excluded_symbols: tuple[str, ...]
    selected_symbols: tuple[str, ...] = ()
    exclusion_reasons: tuple[tuple[str, str], ...] = ()
    readiness_state: str | None = None

    @property
    def trade_count_admission_candidate_symbol_count(self) -> int:
        return len(self.trade_count_admission_candidate_symbols)

    @property
    def trade_count_qualifying_symbol_count(self) -> int:
        return len(self.trade_count_qualifying_symbols)

    @property
    def trade_count_excluded_symbol_count(self) -> int:
        return len(self.trade_count_excluded_symbols)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["trade_count_admission_candidate_symbol_count"] = (
            self.trade_count_admission_candidate_symbol_count
        )
        payload["trade_count_qualifying_symbol_count"] = self.trade_count_qualifying_symbol_count
        payload["trade_count_excluded_symbol_count"] = self.trade_count_excluded_symbol_count
        return payload

    def to_operator_diagnostics_dict(self) -> dict[str, object]:
        payload = self.to_dict()
        payload.pop("scope_mode", None)
        payload.pop("trade_count_filter_minimum", None)
        return payload


@dataclass(slots=True, frozen=True)
class BybitProjectionSnapshot:
    exchange: str
    enabled: bool
    primary_symbol: str | None
    symbols: tuple[str, ...]
    discovery: BybitDiscoverySnapshot
    transport: BybitTransportSnapshot
    trade_truth: BybitTradeTruthSnapshot
    admission: BybitAdmissionSnapshot
    extras: dict[str, object] = field(default_factory=dict)

    def to_operator_diagnostics_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "enabled": self.enabled,
            "exchange": self.exchange,
            "symbol": self.primary_symbol,
            "symbols": self.symbols,
        }
        payload.update(self.discovery.to_operator_diagnostics_dict())
        payload.update(self.transport.to_operator_diagnostics_dict())
        payload.update(self.trade_truth.to_operator_diagnostics_dict())
        payload.update(self.admission.to_operator_diagnostics_dict())
        payload.update(self.extras)
        return payload
