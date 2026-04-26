"""Explicit backend projection for the current Bybit connectors screen."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from cryptotechnolog.live_feed.bybit_connector_state import (
    BybitAdmissionSnapshot,
    BybitDiscoverySnapshot,
    BybitProjectionSnapshot,
    BybitTradeTruthSnapshot,
    BybitTransportSnapshot,
)
from cryptotechnolog.live_feed.bybit_trade_count_truth_model import (
    FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP,
)


@dataclass(slots=True, frozen=True)
class BybitConnectorScreenSymbolProjection:
    symbol: str
    trade_seen: bool
    orderbook_seen: bool
    best_bid: str | None
    best_ask: str | None
    volume_24h_usd: str | None
    derived_trade_count_24h: int | None
    bucket_trade_count_24h: int | None
    ledger_trade_count_24h: int | None
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
class BybitConnectorScreenProjection:
    enabled: bool
    exchange: str
    symbol: str | None
    symbols: tuple[str, ...]
    symbol_snapshots: tuple[BybitConnectorScreenSymbolProjection, ...]
    transport_status: str
    recovery_status: str
    subscription_alive: bool
    trade_seen: bool
    orderbook_seen: bool
    best_bid: str | None
    best_ask: str | None
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
    derived_trade_count_state: str | None
    derived_trade_count_ready: bool
    derived_trade_count_observation_started_at: str | None
    derived_trade_count_reliable_after: str | None
    derived_trade_count_last_gap_at: str | None
    derived_trade_count_last_gap_reason: str | None
    derived_trade_count_backfill_status: str | None
    derived_trade_count_backfill_needed: bool | None
    derived_trade_count_backfill_processed_archives: int | None
    derived_trade_count_backfill_total_archives: int | None
    derived_trade_count_backfill_progress_percent: int | None
    derived_trade_count_last_backfill_at: str | None
    derived_trade_count_last_backfill_source: str | None
    derived_trade_count_last_backfill_reason: str | None
    ledger_trade_count_available: bool
    ledger_trade_count_last_error: str | None
    ledger_trade_count_last_synced_at: str | None
    trade_count_truth_model: str
    trade_count_canonical_truth_owner: str
    trade_count_canonical_truth_source: str
    trade_count_operational_truth_owner: str
    trade_count_operational_truth_source: str
    trade_count_connector_canonical_role: str
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
    desired_scope_mode: str | None
    desired_trade_count_filter_minimum: int | None
    applied_scope_mode: str | None
    applied_trade_count_filter_minimum: int | None
    policy_apply_status: str | None
    policy_apply_reason: str | None
    operator_runtime_state: str
    operator_runtime_reason: str | None
    operator_confidence_state: str
    operator_confidence_reason: str | None
    operator_state_surface: dict[str, object] | None
    operational_recovery_state: str | None
    operational_recovery_reason: str | None
    canonical_ledger_sync_state: str | None
    canonical_ledger_sync_reason: str | None
    historical_recovery_state: str
    historical_recovery_reason: str | None
    historical_recovery_retry_pending: bool
    historical_recovery_backfill_task_active: bool
    historical_recovery_retry_task_active: bool
    historical_recovery_cutoff_at: str | None
    post_recovery_materialization_status: str | None
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
    scope_mode: str
    discovery_status: str
    discovery_error: str | None
    total_instruments_discovered: int | None
    instruments_passed_coarse_filter: int | None
    quote_volume_filter_ready: bool | None
    trade_count_filter_ready: bool | None
    instruments_passed_trade_count_filter: int | None
    universe_admission_state: str | None
    trade_count_product_truth_state: str
    trade_count_product_truth_reason: str
    trade_count_admission_basis: str
    trade_count_admission_truth_owner: str
    trade_count_admission_truth_source: str
    active_subscribed_scope_count: int
    live_trade_streams_count: int
    live_orderbook_count: int
    degraded_or_stale_count: int

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["symbol_snapshots"] = tuple(
            snapshot.to_dict() for snapshot in self.symbol_snapshots
        )
        return payload


@dataclass(slots=True, frozen=True)
class _BybitProjectionApplyTruth:
    desired_scope_mode: str | None
    desired_trade_count_filter_minimum: int | None
    applied_scope_mode: str | None
    applied_trade_count_filter_minimum: int | None
    policy_apply_status: str | None
    policy_apply_reason: str | None


class DiagnosticsProjection:
    """Pure projection from Bybit named snapshots to a screen-facing backend contract."""

    @classmethod
    def from_snapshot(
        cls,
        snapshot: BybitProjectionSnapshot,
        *,
        apply_truth: _BybitProjectionApplyTruth | None = None,
    ) -> BybitConnectorScreenProjection:
        return cls.from_snapshots(
            exchange=snapshot.exchange,
            enabled=snapshot.enabled,
            primary_symbol=snapshot.primary_symbol,
            symbols=snapshot.symbols,
            discovery=snapshot.discovery,
            transport=snapshot.transport,
            trade_truth=snapshot.trade_truth,
            admission=snapshot.admission,
            extras=snapshot.extras,
            apply_truth=apply_truth,
        )

    @classmethod
    def from_snapshots(
        cls,
        *,
        exchange: str,
        enabled: bool,
        primary_symbol: str | None,
        symbols: tuple[str, ...],
        discovery: BybitDiscoverySnapshot,
        transport: BybitTransportSnapshot,
        trade_truth: BybitTradeTruthSnapshot,
        admission: BybitAdmissionSnapshot,
        extras: dict[str, object] | None = None,
        apply_truth: _BybitProjectionApplyTruth | None = None,
    ) -> BybitConnectorScreenProjection:
        quote_volume_by_symbol = dict(discovery.quote_turnover_24h_by_symbol)
        symbol_snapshots = tuple(
            BybitConnectorScreenSymbolProjection(
                symbol=snapshot.symbol,
                trade_seen=snapshot.trade_seen,
                orderbook_seen=snapshot.orderbook_seen,
                best_bid=snapshot.best_bid,
                best_ask=snapshot.best_ask,
                volume_24h_usd=snapshot.volume_24h_usd
                or quote_volume_by_symbol.get(snapshot.symbol),
                derived_trade_count_24h=snapshot.derived_trade_count_24h,
                bucket_trade_count_24h=snapshot.bucket_trade_count_24h,
                ledger_trade_count_24h=snapshot.ledger_trade_count_24h,
                trade_count_reconciliation_verdict=snapshot.trade_count_reconciliation_verdict,
                trade_count_reconciliation_reason=snapshot.trade_count_reconciliation_reason,
                trade_count_reconciliation_absolute_diff=(
                    snapshot.trade_count_reconciliation_absolute_diff
                ),
                trade_count_reconciliation_tolerance=(
                    snapshot.trade_count_reconciliation_tolerance
                ),
                trade_count_cutover_readiness_state=snapshot.trade_count_cutover_readiness_state,
                trade_count_cutover_readiness_reason=snapshot.trade_count_cutover_readiness_reason,
                observed_trade_count_since_reset=snapshot.observed_trade_count_since_reset,
                product_trade_count_24h=snapshot.product_trade_count_24h,
                product_trade_count_state=snapshot.product_trade_count_state,
                product_trade_count_reason=snapshot.product_trade_count_reason,
                product_trade_count_truth_owner=snapshot.product_trade_count_truth_owner,
                product_trade_count_truth_source=snapshot.product_trade_count_truth_source,
                trade_ingest_seen=snapshot.trade_ingest_seen,
                orderbook_ingest_seen=snapshot.orderbook_ingest_seen,
            )
            for snapshot in trade_truth.symbol_snapshots
        )
        has_live_transport_messages = (
            transport.transport_status in {"connected", "degraded"}
            and transport.last_message_at is not None
        )
        if has_live_transport_messages:
            live_trade_streams_count = sum(
                1 for snapshot in symbol_snapshots if snapshot.trade_seen
            )
            live_orderbook_count = sum(
                1 for snapshot in symbol_snapshots if snapshot.orderbook_seen
            )
            trade_seen = trade_truth.trade_seen
            orderbook_seen = trade_truth.orderbook_seen
            best_bid = trade_truth.best_bid
            best_ask = trade_truth.best_ask
        else:
            live_trade_streams_count = 0
            live_orderbook_count = 0
            trade_seen = False
            orderbook_seen = False
            best_bid = None
            best_ask = None

        active_subscribed_scope_count = len(symbol_snapshots) or len(symbols)
        quote_volume_filter_ready: bool | None
        trade_count_filter_ready: bool | None
        instruments_passed_trade_count_filter: int | None
        universe_admission_state: str | None
        degraded_reason = transport.degraded_reason
        operator_state_surface = None
        if isinstance(extras, dict):
            surface = extras.get("operator_state_surface")
            if isinstance(surface, dict):
                operator_state_surface = surface
        if operator_state_surface is None:
            operator_state_surface = {
                "runtime": {
                    "state": trade_truth.operational_recovery_state,
                    "reason": trade_truth.operational_recovery_reason,
                },
                "ledger_sync": {
                    "state": trade_truth.canonical_ledger_sync_state,
                    "reason": trade_truth.canonical_ledger_sync_reason,
                },
            }

        if discovery.scope_mode == "universe":
            quote_volume_filter_ready = discovery.discovery_status == "ready"
            empty_selected_scope = quote_volume_filter_ready and not admission.selected_symbols
            trade_count_filter_required = admission.trade_count_filter_minimum > 0
            if empty_selected_scope:
                trade_count_filter_ready = True
            else:
                trade_count_filter_ready = (
                    trade_truth.derived_trade_count_ready if trade_count_filter_required else True
                )
            if empty_selected_scope:
                instruments_passed_trade_count_filter = 0
            elif trade_count_filter_required and not trade_count_filter_ready:
                instruments_passed_trade_count_filter = None
            elif trade_count_filter_required:
                instruments_passed_trade_count_filter = sum(
                    1
                    for snapshot in symbol_snapshots
                    if snapshot.derived_trade_count_24h is not None
                    and snapshot.derived_trade_count_24h
                    >= admission.trade_count_filter_minimum
                )
            else:
                instruments_passed_trade_count_filter = active_subscribed_scope_count

            if not quote_volume_filter_ready:
                universe_admission_state = "waiting_for_filter_readiness"
            elif (
                not trade_count_filter_ready
                and trade_truth.derived_trade_count_state == "live_tail_pending_after_gap"
            ):
                universe_admission_state = "waiting_for_live_tail"
            elif not trade_count_filter_ready:
                universe_admission_state = "waiting_for_filter_readiness"
            elif instruments_passed_trade_count_filter == 0:
                universe_admission_state = "waiting_for_qualifying_instruments"
            else:
                universe_admission_state = "ready_for_selection"

            if discovery.discovery_status == "unavailable":
                degraded_reason = degraded_reason or "discovery_unavailable"
            elif enabled and degraded_reason is None and active_subscribed_scope_count == 0:
                degraded_reason = universe_admission_state
        else:
            quote_volume_filter_ready = None
            trade_count_filter_ready = None
            instruments_passed_trade_count_filter = None
            universe_admission_state = None

        operator_runtime_state, operator_runtime_reason = cls._build_operator_runtime_truth(
            enabled=enabled,
            transport_status=transport.transport_status,
            degraded_reason=degraded_reason,
            last_disconnect_reason=transport.last_disconnect_reason,
            universe_admission_state=universe_admission_state,
            policy_apply_status=apply_truth.policy_apply_status if apply_truth else None,
            policy_apply_reason=apply_truth.policy_apply_reason if apply_truth else None,
        )
        operator_confidence_state, operator_confidence_reason = (
            cls._build_operator_confidence_truth(
                operator_runtime_state=operator_runtime_state,
                operator_runtime_reason=operator_runtime_reason,
                live_trade_streams_count=live_trade_streams_count,
                live_orderbook_count=live_orderbook_count,
                active_subscribed_scope_count=active_subscribed_scope_count,
            )
        )
        post_recovery_materialization_status = None
        if isinstance(extras, dict):
            status = extras.get("post_recovery_materialization_status")
            if isinstance(status, str):
                post_recovery_materialization_status = status

        return cls._build_contract(
            exchange=exchange,
            enabled=enabled,
            primary_symbol=primary_symbol,
            symbols=symbols,
            symbol_snapshots=symbol_snapshots,
            discovery=discovery,
            transport=transport,
            trade_truth=trade_truth,
            admission=admission,
            apply_truth=apply_truth,
            trade_seen=trade_seen,
            orderbook_seen=orderbook_seen,
            best_bid=best_bid,
            best_ask=best_ask,
            degraded_reason=degraded_reason,
            quote_volume_filter_ready=quote_volume_filter_ready,
            trade_count_filter_ready=trade_count_filter_ready,
            instruments_passed_trade_count_filter=instruments_passed_trade_count_filter,
            universe_admission_state=universe_admission_state,
            active_subscribed_scope_count=active_subscribed_scope_count,
            live_trade_streams_count=live_trade_streams_count,
            live_orderbook_count=live_orderbook_count,
            operator_runtime_state=operator_runtime_state,
            operator_runtime_reason=operator_runtime_reason,
            operator_confidence_state=operator_confidence_state,
            operator_confidence_reason=operator_confidence_reason,
            operator_state_surface=operator_state_surface,
            post_recovery_materialization_status=post_recovery_materialization_status,
        )

    @staticmethod
    def _build_operator_runtime_truth(
        *,
        enabled: bool,
        transport_status: str,
        degraded_reason: str | None,
        last_disconnect_reason: str | None,
        universe_admission_state: str | None,
        policy_apply_status: str | None,
        policy_apply_reason: str | None,
    ) -> tuple[str, str | None]:
        if not enabled:
            return "disabled", None
        if policy_apply_status == "deferred":
            return "apply_deferred", policy_apply_reason
        if transport_status in {"connecting", "idle"}:
            return "connecting", None
        if transport_status != "connected":
            return "transport_unavailable", degraded_reason or last_disconnect_reason
        if universe_admission_state == "ready_for_selection":
            return "ready", None
        if universe_admission_state == "waiting_for_live_tail":
            return (
                "waiting_for_live_tail",
                "Historical window restored, waiting for post-gap live tail.",
            )
        if universe_admission_state == "waiting_for_filter_readiness":
            return "warming_up", "Trade-count layer is still warming up."
        if universe_admission_state == "waiting_for_qualifying_instruments":
            return "no_qualifying_instruments", (
                "Filters are ready, but no instruments currently qualify."
            )
        return "live", None

    @staticmethod
    def _build_operator_confidence_truth(
        *,
        operator_runtime_state: str,
        operator_runtime_reason: str | None,
        live_trade_streams_count: int,
        live_orderbook_count: int,
        active_subscribed_scope_count: int,
    ) -> tuple[str, str | None]:
        if operator_runtime_state == "disabled":
            return "disabled", None
        if operator_runtime_state == "apply_deferred":
            return "deferred", "Saved policy truth is ahead of the currently applied runtime."
        if operator_runtime_state == "waiting_for_live_tail":
            return (
                "preserved_after_gap",
                "Historical window is preserved; only post-gap live tail confidence is pending.",
            )
        if active_subscribed_scope_count > 0 and (
            live_trade_streams_count == 0 or live_orderbook_count == 0
        ):
            return (
                "streams_recovering",
                "Transport is back, but not all live streams have resumed yet.",
            )
        if operator_runtime_state == "warming_up":
            return (
                "cold_recovery",
                "Trade-count layer is rebuilding confidence from a wider recovery boundary.",
            )
        if operator_runtime_state == "no_qualifying_instruments":
            return (
                "steady_but_empty",
                "Runtime is stable, but final admission currently has no qualifying instruments.",
            )
        if operator_runtime_state == "transport_unavailable":
            return "transport_unavailable", operator_runtime_reason
        return "steady", None

    @staticmethod
    def _build_contract(
        *,
        exchange: str,
        enabled: bool,
        primary_symbol: str | None,
        symbols: tuple[str, ...],
        symbol_snapshots: tuple[BybitConnectorScreenSymbolProjection, ...],
        discovery: BybitDiscoverySnapshot,
        transport: BybitTransportSnapshot,
        trade_truth: BybitTradeTruthSnapshot,
        admission: BybitAdmissionSnapshot,
        apply_truth: _BybitProjectionApplyTruth | None,
        trade_seen: bool,
        orderbook_seen: bool,
        best_bid: str | None,
        best_ask: str | None,
        degraded_reason: str | None,
        quote_volume_filter_ready: bool | None,
        trade_count_filter_ready: bool | None,
        instruments_passed_trade_count_filter: int | None,
        universe_admission_state: str | None,
        active_subscribed_scope_count: int,
        live_trade_streams_count: int,
        live_orderbook_count: int,
        operator_runtime_state: str,
        operator_runtime_reason: str | None,
        operator_confidence_state: str,
        operator_confidence_reason: str | None,
        operator_state_surface: dict[str, object] | None,
        post_recovery_materialization_status: str | None,
    ) -> BybitConnectorScreenProjection:
        return BybitConnectorScreenProjection(
            enabled=enabled,
            exchange=exchange,
            symbol=primary_symbol,
            symbols=symbols,
            symbol_snapshots=symbol_snapshots,
            transport_status=transport.transport_status,
            recovery_status=transport.recovery_status,
            subscription_alive=transport.subscription_alive,
            trade_seen=trade_seen,
            orderbook_seen=orderbook_seen,
            best_bid=best_bid,
            best_ask=best_ask,
            last_message_at=transport.last_message_at,
            message_age_ms=transport.message_age_ms,
            transport_rtt_ms=transport.transport_rtt_ms,
            last_ping_sent_at=transport.last_ping_sent_at,
            last_pong_at=transport.last_pong_at,
            application_ping_sent_at=transport.application_ping_sent_at,
            application_pong_at=transport.application_pong_at,
            application_heartbeat_latency_ms=transport.application_heartbeat_latency_ms,
            last_ping_timeout_at=transport.last_ping_timeout_at,
            last_ping_timeout_message_age_ms=transport.last_ping_timeout_message_age_ms,
            last_ping_timeout_loop_lag_ms=transport.last_ping_timeout_loop_lag_ms,
            last_ping_timeout_backfill_status=transport.last_ping_timeout_backfill_status,
            last_ping_timeout_processed_archives=transport.last_ping_timeout_processed_archives,
            last_ping_timeout_total_archives=transport.last_ping_timeout_total_archives,
            last_ping_timeout_cache_source=transport.last_ping_timeout_cache_source,
            last_ping_timeout_ignored_due_to_recent_messages=(
                transport.last_ping_timeout_ignored_due_to_recent_messages
            ),
            degraded_reason=degraded_reason,
            last_disconnect_reason=transport.last_disconnect_reason,
            retry_count=transport.retry_count,
            ready=transport.ready,
            started=transport.started,
            lifecycle_state=transport.lifecycle_state,
            reset_required=transport.reset_required,
            derived_trade_count_state=trade_truth.derived_trade_count_state,
            derived_trade_count_ready=trade_truth.derived_trade_count_ready,
            derived_trade_count_observation_started_at=(
                trade_truth.derived_trade_count_observation_started_at
            ),
            derived_trade_count_reliable_after=trade_truth.derived_trade_count_reliable_after,
            derived_trade_count_last_gap_at=trade_truth.derived_trade_count_last_gap_at,
            derived_trade_count_last_gap_reason=trade_truth.derived_trade_count_last_gap_reason,
            derived_trade_count_backfill_status=trade_truth.derived_trade_count_backfill_status,
            derived_trade_count_backfill_needed=trade_truth.derived_trade_count_backfill_needed,
            derived_trade_count_backfill_processed_archives=(
                trade_truth.derived_trade_count_backfill_processed_archives
            ),
            derived_trade_count_backfill_total_archives=(
                trade_truth.derived_trade_count_backfill_total_archives
            ),
            derived_trade_count_backfill_progress_percent=(
                trade_truth.derived_trade_count_backfill_progress_percent
            ),
            derived_trade_count_last_backfill_at=trade_truth.derived_trade_count_last_backfill_at,
            derived_trade_count_last_backfill_source=(
                trade_truth.derived_trade_count_last_backfill_source
            ),
            derived_trade_count_last_backfill_reason=(
                trade_truth.derived_trade_count_last_backfill_reason
            ),
            ledger_trade_count_available=trade_truth.ledger_trade_count_available,
            ledger_trade_count_last_error=trade_truth.ledger_trade_count_last_error,
            ledger_trade_count_last_synced_at=trade_truth.ledger_trade_count_last_synced_at,
            trade_count_truth_model=trade_truth.trade_count_truth_model,
            trade_count_canonical_truth_owner=trade_truth.trade_count_canonical_truth_owner,
            trade_count_canonical_truth_source=trade_truth.trade_count_canonical_truth_source,
            trade_count_operational_truth_owner=trade_truth.trade_count_operational_truth_owner,
            trade_count_operational_truth_source=trade_truth.trade_count_operational_truth_source,
            trade_count_connector_canonical_role=trade_truth.trade_count_connector_canonical_role,
            trade_count_cutover_readiness_state=trade_truth.trade_count_cutover_readiness_state,
            trade_count_cutover_readiness_reason=trade_truth.trade_count_cutover_readiness_reason,
            trade_count_cutover_compared_symbols=trade_truth.trade_count_cutover_compared_symbols,
            trade_count_cutover_ready_symbols=trade_truth.trade_count_cutover_ready_symbols,
            trade_count_cutover_not_ready_symbols=trade_truth.trade_count_cutover_not_ready_symbols,
            trade_count_cutover_blocked_symbols=trade_truth.trade_count_cutover_blocked_symbols,
            trade_count_cutover_evaluation_state=trade_truth.trade_count_cutover_evaluation_state,
            trade_count_cutover_evaluation_reasons=(
                trade_truth.trade_count_cutover_evaluation_reasons
            ),
            trade_count_cutover_evaluation_minimum_compared_symbols=(
                trade_truth.trade_count_cutover_evaluation_minimum_compared_symbols
            ),
            trade_count_cutover_manual_review_state=(
                trade_truth.trade_count_cutover_manual_review_state
            ),
            trade_count_cutover_manual_review_reasons=(
                trade_truth.trade_count_cutover_manual_review_reasons
            ),
            trade_count_cutover_manual_review_evaluation_state=(
                trade_truth.trade_count_cutover_manual_review_evaluation_state
            ),
            trade_count_cutover_manual_review_contour=(
                trade_truth.trade_count_cutover_manual_review_contour
            ),
            trade_count_cutover_manual_review_scope_mode=(
                trade_truth.trade_count_cutover_manual_review_scope_mode
            ),
            trade_count_cutover_manual_review_scope_symbol_count=(
                trade_truth.trade_count_cutover_manual_review_scope_symbol_count
            ),
            trade_count_cutover_manual_review_compared_symbols=(
                trade_truth.trade_count_cutover_manual_review_compared_symbols
            ),
            trade_count_cutover_manual_review_ready_symbols=(
                trade_truth.trade_count_cutover_manual_review_ready_symbols
            ),
            trade_count_cutover_manual_review_not_ready_symbols=(
                trade_truth.trade_count_cutover_manual_review_not_ready_symbols
            ),
            trade_count_cutover_manual_review_blocked_symbols=(
                trade_truth.trade_count_cutover_manual_review_blocked_symbols
            ),
            trade_count_cutover_discussion_artifact=trade_truth.trade_count_cutover_discussion_artifact,
            trade_count_cutover_review_record=trade_truth.trade_count_cutover_review_record,
            trade_count_cutover_review_package=trade_truth.trade_count_cutover_review_package,
            trade_count_cutover_review_catalog=trade_truth.trade_count_cutover_review_catalog,
            trade_count_cutover_review_snapshot_collection=(
                trade_truth.trade_count_cutover_review_snapshot_collection
            ),
            trade_count_cutover_review_compact_digest=(
                trade_truth.trade_count_cutover_review_compact_digest
            ),
            trade_count_cutover_export_report_bundle=(
                trade_truth.trade_count_cutover_export_report_bundle
            ),
            desired_scope_mode=apply_truth.desired_scope_mode if apply_truth else None,
            desired_trade_count_filter_minimum=(
                apply_truth.desired_trade_count_filter_minimum if apply_truth else None
            ),
            applied_scope_mode=apply_truth.applied_scope_mode if apply_truth else None,
            applied_trade_count_filter_minimum=(
                apply_truth.applied_trade_count_filter_minimum if apply_truth else None
            ),
            policy_apply_status=apply_truth.policy_apply_status if apply_truth else None,
            policy_apply_reason=apply_truth.policy_apply_reason if apply_truth else None,
            operator_runtime_state=operator_runtime_state,
            operator_runtime_reason=operator_runtime_reason,
            operator_confidence_state=operator_confidence_state,
            operator_confidence_reason=operator_confidence_reason,
            operator_state_surface=operator_state_surface,
            operational_recovery_state=trade_truth.operational_recovery_state,
            operational_recovery_reason=trade_truth.operational_recovery_reason,
            canonical_ledger_sync_state=trade_truth.canonical_ledger_sync_state,
            canonical_ledger_sync_reason=trade_truth.canonical_ledger_sync_reason,
            historical_recovery_state=trade_truth.historical_recovery_state,
            historical_recovery_reason=trade_truth.historical_recovery_reason,
            historical_recovery_retry_pending=trade_truth.historical_recovery_retry_pending,
            historical_recovery_backfill_task_active=(
                trade_truth.historical_recovery_backfill_task_active
            ),
            historical_recovery_retry_task_active=trade_truth.historical_recovery_retry_task_active,
            historical_recovery_cutoff_at=trade_truth.historical_recovery_cutoff_at,
            post_recovery_materialization_status=post_recovery_materialization_status,
            archive_cache_enabled=trade_truth.archive_cache_enabled,
            archive_cache_memory_hits=trade_truth.archive_cache_memory_hits,
            archive_cache_disk_hits=trade_truth.archive_cache_disk_hits,
            archive_cache_misses=trade_truth.archive_cache_misses,
            archive_cache_writes=trade_truth.archive_cache_writes,
            archive_cache_last_hit_source=trade_truth.archive_cache_last_hit_source,
            archive_cache_last_url=trade_truth.archive_cache_last_url,
            archive_cache_last_cleanup_at=trade_truth.archive_cache_last_cleanup_at,
            archive_cache_last_pruned_files=trade_truth.archive_cache_last_pruned_files,
            archive_cache_last_network_fetch_ms=trade_truth.archive_cache_last_network_fetch_ms,
            archive_cache_last_disk_read_ms=trade_truth.archive_cache_last_disk_read_ms,
            archive_cache_last_gzip_decode_ms=trade_truth.archive_cache_last_gzip_decode_ms,
            archive_cache_last_csv_parse_ms=trade_truth.archive_cache_last_csv_parse_ms,
            archive_cache_last_archive_total_ms=trade_truth.archive_cache_last_archive_total_ms,
            archive_cache_last_symbol_total_ms=trade_truth.archive_cache_last_symbol_total_ms,
            archive_cache_last_symbol=trade_truth.archive_cache_last_symbol,
            archive_cache_total_network_fetch_ms=trade_truth.archive_cache_total_network_fetch_ms,
            archive_cache_total_disk_read_ms=trade_truth.archive_cache_total_disk_read_ms,
            archive_cache_total_gzip_decode_ms=trade_truth.archive_cache_total_gzip_decode_ms,
            archive_cache_total_csv_parse_ms=trade_truth.archive_cache_total_csv_parse_ms,
            archive_cache_total_archive_total_ms=trade_truth.archive_cache_total_archive_total_ms,
            archive_cache_total_symbol_total_ms=trade_truth.archive_cache_total_symbol_total_ms,
            scope_mode=discovery.scope_mode,
            discovery_status=discovery.discovery_status,
            discovery_error=discovery.quote_turnover_last_error,
            total_instruments_discovered=discovery.total_instruments_discovered,
            instruments_passed_coarse_filter=discovery.instruments_passed_coarse_filter,
            quote_volume_filter_ready=quote_volume_filter_ready,
            trade_count_filter_ready=trade_count_filter_ready,
            instruments_passed_trade_count_filter=instruments_passed_trade_count_filter,
            universe_admission_state=universe_admission_state,
            trade_count_product_truth_state=trade_truth.trade_count_product_truth_state,
            trade_count_product_truth_reason=trade_truth.trade_count_product_truth_reason,
            trade_count_admission_basis=admission.trade_count_admission_basis,
            trade_count_admission_truth_owner=admission.trade_count_admission_truth_owner,
            trade_count_admission_truth_source=admission.trade_count_admission_truth_source,
            active_subscribed_scope_count=active_subscribed_scope_count,
            live_trade_streams_count=live_trade_streams_count,
            live_orderbook_count=live_orderbook_count,
            degraded_or_stale_count=max(
                0,
                active_subscribed_scope_count
                - min(live_trade_streams_count, live_orderbook_count),
            ),
        )


def build_disabled_bybit_projection_snapshot(
    *,
    exchange: str,
    enabled: bool,
    discovery: BybitDiscoverySnapshot,
    admission: BybitAdmissionSnapshot,
) -> BybitProjectionSnapshot:
    transport_status = "idle" if enabled else "disabled"
    lifecycle_state = "waiting_for_scope" if enabled else "disabled"
    return BybitProjectionSnapshot(
        exchange=exchange,
        enabled=enabled,
        primary_symbol=None,
        symbols=(),
        discovery=discovery,
        transport=BybitTransportSnapshot(
            transport_status=transport_status,
            recovery_status="waiting_for_scope" if enabled else "idle",
            subscription_alive=False,
            last_message_at=None,
            message_age_ms=None,
            transport_rtt_ms=None,
            last_ping_sent_at=None,
            last_pong_at=None,
            application_ping_sent_at=None,
            application_pong_at=None,
            application_heartbeat_latency_ms=None,
            last_ping_timeout_at=None,
            last_ping_timeout_message_age_ms=None,
            last_ping_timeout_loop_lag_ms=None,
            last_ping_timeout_backfill_status=None,
            last_ping_timeout_processed_archives=None,
            last_ping_timeout_total_archives=None,
            last_ping_timeout_cache_source=None,
            last_ping_timeout_ignored_due_to_recent_messages=False,
            degraded_reason=None,
            last_disconnect_reason=None,
            retry_count=None,
            ready=False,
            started=False,
            lifecycle_state=lifecycle_state,
            reset_required=False,
        ),
        trade_truth=BybitTradeTruthSnapshot(
            symbol_snapshots=(),
            trade_seen=False,
            orderbook_seen=False,
            best_bid=None,
            best_ask=None,
            operational_recovery_state="not_applicable",
            operational_recovery_reason=None,
            canonical_ledger_sync_state="not_applicable",
            canonical_ledger_sync_reason=None,
            derived_trade_count_state=None,
            derived_trade_count_ready=False,
            derived_trade_count_observation_started_at=None,
            derived_trade_count_reliable_after=None,
            derived_trade_count_last_gap_at=None,
            derived_trade_count_last_gap_reason=None,
            derived_trade_count_backfill_status=None,
            derived_trade_count_backfill_needed=None,
            derived_trade_count_backfill_processed_archives=None,
            derived_trade_count_backfill_total_archives=None,
            derived_trade_count_backfill_progress_percent=None,
            derived_trade_count_last_backfill_at=None,
            derived_trade_count_last_backfill_source=None,
            derived_trade_count_last_backfill_reason=None,
            ledger_trade_count_available=False,
            ledger_trade_count_scope_status="unavailable",
            ledger_trade_count_last_error=None,
            ledger_trade_count_last_synced_at=None,
            trade_count_truth_model=FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.truth_model,
            trade_count_canonical_truth_owner=(
                FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.canonical_trade_truth_owner
            ),
            trade_count_canonical_truth_source=(
                FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.canonical_trade_truth_source
            ),
            trade_count_operational_truth_owner=(
                FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.connector_runtime_truth_owner
            ),
            trade_count_operational_truth_source=(
                FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.connector_runtime_truth_source
            ),
            trade_count_connector_canonical_role=(
                FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.connector_canonical_role
            ),
            trade_count_product_truth_state="pending_validation",
            trade_count_product_truth_reason="pending_validation_present",
            trade_count_cutover_readiness_state="not_ready",
            trade_count_cutover_readiness_reason="no_symbols_compared",
            trade_count_cutover_compared_symbols=0,
            trade_count_cutover_ready_symbols=0,
            trade_count_cutover_not_ready_symbols=0,
            trade_count_cutover_blocked_symbols=0,
            trade_count_cutover_evaluation_state="not_eligible",
            trade_count_cutover_evaluation_reasons=(),
            trade_count_cutover_evaluation_minimum_compared_symbols=1,
            trade_count_cutover_manual_review_state="manual_review_not_recommended",
            trade_count_cutover_manual_review_reasons=(),
            trade_count_cutover_manual_review_evaluation_state="not_eligible",
            trade_count_cutover_manual_review_contour="linear",
            trade_count_cutover_manual_review_scope_mode=discovery.scope_mode,
            trade_count_cutover_manual_review_scope_symbol_count=0,
            trade_count_cutover_manual_review_compared_symbols=0,
            trade_count_cutover_manual_review_ready_symbols=0,
            trade_count_cutover_manual_review_not_ready_symbols=0,
            trade_count_cutover_manual_review_blocked_symbols=0,
            trade_count_cutover_discussion_artifact={},
            trade_count_cutover_review_record={},
            trade_count_cutover_review_package={},
            trade_count_cutover_review_catalog={},
            trade_count_cutover_review_snapshot_collection={},
            trade_count_cutover_review_compact_digest={},
            trade_count_cutover_export_report_bundle={},
            historical_recovery_state="idle",
            historical_recovery_reason=None,
            historical_recovery_retry_pending=False,
            historical_recovery_backfill_task_active=False,
            historical_recovery_retry_task_active=False,
            historical_recovery_cutoff_at=None,
            archive_cache_enabled=False,
            archive_cache_memory_hits=0,
            archive_cache_disk_hits=0,
            archive_cache_misses=0,
            archive_cache_writes=0,
            archive_cache_last_hit_source=None,
            archive_cache_last_url=None,
            archive_cache_last_cleanup_at=None,
            archive_cache_last_pruned_files=0,
            archive_cache_last_network_fetch_ms=None,
            archive_cache_last_disk_read_ms=None,
            archive_cache_last_gzip_decode_ms=None,
            archive_cache_last_csv_parse_ms=None,
            archive_cache_last_archive_total_ms=None,
            archive_cache_last_symbol_total_ms=None,
            archive_cache_last_symbol=None,
            archive_cache_total_network_fetch_ms=0,
            archive_cache_total_disk_read_ms=0,
            archive_cache_total_gzip_decode_ms=0,
            archive_cache_total_csv_parse_ms=0,
            archive_cache_total_archive_total_ms=0,
            archive_cache_total_symbol_total_ms=0,
        ),
        admission=admission,
    )
