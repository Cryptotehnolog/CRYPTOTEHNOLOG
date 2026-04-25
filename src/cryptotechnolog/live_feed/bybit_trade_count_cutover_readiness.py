"""
Read-only cutover readiness groundwork over trade-count reconciliation diagnostics.

Модуль intentionally ограничен readiness-only semantics без
product switch, admission switch или real cutover execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .bybit_trade_count_reconciliation import (
    BybitTradeCountReconciliationResult,
    BybitTradeCountReconciliationVerdict,
)

BybitTradeCountCutoverReadinessState = Literal[
    "ready_for_cutover_evaluation",
    "not_ready",
    "blocked",
]


@dataclass(slots=True, frozen=True)
class BybitTradeCountCutoverReadinessResult:
    """Machine-readable cutover-readiness result for one symbol or aggregated scope."""

    state: BybitTradeCountCutoverReadinessState
    reason: str
    compared_symbols: int
    ready_symbols: int
    not_ready_symbols: int
    blocked_symbols: int


def readiness_from_reconciliation_result(
    reconciliation: BybitTradeCountReconciliationResult,
) -> BybitTradeCountCutoverReadinessResult:
    if reconciliation.verdict == "validation_blocked":
        return BybitTradeCountCutoverReadinessResult(
            state="blocked",
            reason="validation_blocked_symbols_present",
            compared_symbols=0,
            ready_symbols=0,
            not_ready_symbols=0,
            blocked_symbols=1,
        )
    if reconciliation.verdict == "mismatch":
        return BybitTradeCountCutoverReadinessResult(
            state="not_ready",
            reason="mismatch_present",
            compared_symbols=1,
            ready_symbols=0,
            not_ready_symbols=1,
            blocked_symbols=0,
        )
    if reconciliation.verdict == "not_comparable":
        return BybitTradeCountCutoverReadinessResult(
            state="not_ready",
            reason="not_comparable_symbols_present",
            compared_symbols=0,
            ready_symbols=0,
            not_ready_symbols=1,
            blocked_symbols=0,
        )
    if reconciliation.verdict in {"match", "within_tolerance"}:
        return BybitTradeCountCutoverReadinessResult(
            state="ready_for_cutover_evaluation",
            reason=(
                "all_compared_symbols_match"
                if reconciliation.verdict == "match"
                else "all_compared_symbols_within_policy"
            ),
            compared_symbols=1,
            ready_symbols=1,
            not_ready_symbols=0,
            blocked_symbols=0,
        )
    raise ValueError(f"Неподдерживаемый reconciliation verdict: {reconciliation.verdict}")


def aggregate_cutover_readiness(
    results: tuple[BybitTradeCountCutoverReadinessResult, ...],
) -> BybitTradeCountCutoverReadinessResult:
    if not results:
        return BybitTradeCountCutoverReadinessResult(
            state="not_ready",
            reason="no_symbols_compared",
            compared_symbols=0,
            ready_symbols=0,
            not_ready_symbols=0,
            blocked_symbols=0,
        )
    compared_symbols = sum(result.compared_symbols for result in results)
    ready_symbols = sum(result.ready_symbols for result in results)
    not_ready_symbols = sum(result.not_ready_symbols for result in results)
    blocked_symbols = sum(result.blocked_symbols for result in results)
    reasons = {result.reason for result in results}
    if blocked_symbols > 0:
        all_symbols_blocked = blocked_symbols == len(results)
        return BybitTradeCountCutoverReadinessResult(
            state="blocked",
            reason=(
                "ledger_unavailable"
                if all_symbols_blocked and "validation_blocked_symbols_present" in reasons
                else "blocked_symbols_present"
            ),
            compared_symbols=compared_symbols,
            ready_symbols=ready_symbols,
            not_ready_symbols=not_ready_symbols,
            blocked_symbols=blocked_symbols,
        )
    if "mismatch_present" in reasons:
        return BybitTradeCountCutoverReadinessResult(
            state="not_ready",
            reason="mismatch_present",
            compared_symbols=compared_symbols,
            ready_symbols=ready_symbols,
            not_ready_symbols=not_ready_symbols,
            blocked_symbols=blocked_symbols,
        )
    if "not_comparable_symbols_present" in reasons:
        return BybitTradeCountCutoverReadinessResult(
            state="not_ready",
            reason="not_comparable_symbols_present",
            compared_symbols=compared_symbols,
            ready_symbols=ready_symbols,
            not_ready_symbols=not_ready_symbols,
            blocked_symbols=blocked_symbols,
        )
    if compared_symbols <= 0:
        return BybitTradeCountCutoverReadinessResult(
            state="not_ready",
            reason="no_symbols_compared",
            compared_symbols=compared_symbols,
            ready_symbols=ready_symbols,
            not_ready_symbols=not_ready_symbols,
            blocked_symbols=blocked_symbols,
        )
    if all(result.reason == "all_compared_symbols_match" for result in results):
        return BybitTradeCountCutoverReadinessResult(
            state="ready_for_cutover_evaluation",
            reason="all_compared_symbols_match",
            compared_symbols=compared_symbols,
            ready_symbols=ready_symbols,
            not_ready_symbols=not_ready_symbols,
            blocked_symbols=blocked_symbols,
        )
    return BybitTradeCountCutoverReadinessResult(
        state="ready_for_cutover_evaluation",
        reason="all_compared_symbols_within_policy",
        compared_symbols=compared_symbols,
        ready_symbols=ready_symbols,
        not_ready_symbols=not_ready_symbols,
        blocked_symbols=blocked_symbols,
    )


def readiness_from_reconciliation_verdict(
    verdict: BybitTradeCountReconciliationVerdict,
) -> BybitTradeCountCutoverReadinessResult:
    stub_reconciliation = BybitTradeCountReconciliationResult(
        verdict=verdict,
        bucket_trade_count_24h=None,
        ledger_trade_count_24h=None,
        absolute_diff=None,
        tolerance=0,
        reason="derived_from_verdict",
    )
    return readiness_from_reconciliation_result(stub_reconciliation)
