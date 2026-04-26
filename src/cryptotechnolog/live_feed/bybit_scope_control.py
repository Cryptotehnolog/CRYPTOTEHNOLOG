"""Admission and scope-apply control for Bybit connector phase-3 refactoring."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .bybit_connector_state import BybitAdmissionSnapshot, BybitDiscoverySnapshot
from .bybit_trade_count_truth_model import FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime

    from .bybit import BybitSubscriptionRegistry, BybitWebSocketConnection


@dataclass(slots=True, frozen=True)
class BybitAdmissionTradeTruthInput:
    derived_trade_count_ready: bool
    derived_trade_count_state: str | None
    symbol_trade_count_24h: tuple[tuple[str, int | None], ...]


class BybitAdmissionEngine:
    """Compute desired admission scope without touching transport state directly."""

    def build_snapshot(
        self,
        *,
        discovery: BybitDiscoverySnapshot,
        trade_truth: BybitAdmissionTradeTruthInput,
        applied_subscription_symbols: tuple[str, ...],
        trade_count_filter_minimum: int,
        admission_enabled: bool,
    ) -> BybitAdmissionSnapshot:
        candidate_symbols = (
            discovery.coarse_candidate_symbols if admission_enabled else applied_subscription_symbols
        )
        admission_basis = (
            "derived_operational_truth"
            if admission_enabled and trade_count_filter_minimum > 0
            else "not_applicable"
        )
        readiness_state = "not_applicable"
        if admission_enabled and trade_count_filter_minimum > 0:
            if trade_truth.derived_trade_count_ready:
                readiness_state = "ready"
            elif trade_truth.derived_trade_count_state == "live_tail_pending_after_gap":
                readiness_state = "waiting_for_live_tail"
            else:
                readiness_state = "warming_up"

        qualifying_symbols: tuple[str, ...]
        if admission_enabled and trade_count_filter_minimum > 0:
            qualifying_symbols = tuple(
                symbol
                for symbol, trade_count_24h in trade_truth.symbol_trade_count_24h
                if trade_count_24h is not None and trade_count_24h >= trade_count_filter_minimum
            )
        else:
            qualifying_symbols = candidate_symbols

        selected_symbols = (
            qualifying_symbols
            if readiness_state == "ready" and qualifying_symbols
            else candidate_symbols
        )
        excluded_symbols = tuple(
            symbol for symbol in candidate_symbols if symbol not in qualifying_symbols
        )
        exclusion_reasons = {
            symbol: (
                "below_trade_count_threshold"
                if readiness_state == "ready"
                else "trade_count_not_ready"
            )
            for symbol in excluded_symbols
        }
        return BybitAdmissionSnapshot(
            scope_mode=discovery.scope_mode,
            trade_count_filter_minimum=trade_count_filter_minimum,
            trade_count_admission_basis=admission_basis,
            trade_count_admission_truth_owner=(
                FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.admission_truth_owner
            ),
            trade_count_admission_truth_source=(
                FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP.admission_truth_source
            ),
            trade_count_admission_candidate_symbols=candidate_symbols,
            active_subscribed_symbols=applied_subscription_symbols,
            trade_count_qualifying_symbols=qualifying_symbols,
            trade_count_excluded_symbols=excluded_symbols,
            selected_symbols=selected_symbols,
            exclusion_reasons=tuple(sorted(exclusion_reasons.items())),
            readiness_state=readiness_state,
        )


@dataclass(slots=True, frozen=True)
class BybitScopeApplyResult:
    status: str
    desired_symbols: tuple[str, ...]
    applied_symbols: tuple[str, ...]
    reason: str | None = None


class BybitScopeApplier:
    """Apply already-decided desired scope to transport subscription state only."""

    def build_result(
        self,
        *,
        desired_symbols: tuple[str, ...],
        applied_symbols: tuple[str, ...],
        transport_ready: bool,
    ) -> BybitScopeApplyResult:
        if desired_symbols == applied_symbols:
            return BybitScopeApplyResult(
                status="already_applied",
                desired_symbols=desired_symbols,
                applied_symbols=applied_symbols,
            )
        if not transport_ready:
            return BybitScopeApplyResult(
                status="deferred",
                desired_symbols=desired_symbols,
                applied_symbols=applied_symbols,
                reason="transport_not_ready",
            )
        return BybitScopeApplyResult(
            status="apply_required",
            desired_symbols=desired_symbols,
            applied_symbols=applied_symbols,
        )

    async def apply_desired_scope(
        self,
        *,
        websocket: BybitWebSocketConnection | None,
        previous_registry: BybitSubscriptionRegistry,
        desired_symbols: tuple[str, ...],
        applied_symbols: tuple[str, ...],
        apply_reason: str,
        build_subscription_registry: Callable[[tuple[str, ...]], BybitSubscriptionRegistry],
        clear_symbol_runtime_state: Callable[[str, str, datetime], Awaitable[None]],
        invalidate_orderbook_state: Callable[[tuple[str, ...]], None],
        mark_resubscribing: Callable[[str, datetime], None],
        mark_recovered: Callable[[datetime], None],
        observed_at: datetime,
    ) -> BybitScopeApplyResult:
        plan = self.build_result(
            desired_symbols=desired_symbols,
            applied_symbols=applied_symbols,
            transport_ready=websocket is not None,
        )
        if plan.status != "apply_required" or websocket is None:
            return plan

        if previous_registry.topics:
            await websocket.send(
                json.dumps({
                    "op": "unsubscribe",
                    "args": list(previous_registry.topics),
                })
            )
        removed_symbols = tuple(symbol for symbol in applied_symbols if symbol not in desired_symbols)
        for symbol in removed_symbols:
            await clear_symbol_runtime_state(symbol, apply_reason, observed_at)
        next_registry = build_subscription_registry(desired_symbols)
        invalidate_orderbook_state(desired_symbols)
        if next_registry.topics:
            mark_resubscribing(apply_reason, observed_at)
            await websocket.send(
                json.dumps({
                    "op": "subscribe",
                    "args": list(next_registry.topics),
                })
            )
        else:
            mark_recovered(observed_at)
        return BybitScopeApplyResult(
            status="applied",
            desired_symbols=desired_symbols,
            applied_symbols=desired_symbols,
        )
