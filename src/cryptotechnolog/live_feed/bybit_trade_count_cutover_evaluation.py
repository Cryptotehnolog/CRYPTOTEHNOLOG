"""
Formal read-only cutover evaluation policy over readiness/reconciliation diagnostics.

Модуль intentionally ограничен evaluation-only semantics без
product truth switch, runtime admission switch или real cutover execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .bybit_trade_count_cutover_readiness import BybitTradeCountCutoverReadinessResult
from .bybit_trade_count_reconciliation import BybitTradeCountReconciliationResult

BybitTradeCountCutoverEvaluationState = Literal[
    "eligible_for_manual_cutover_review",
    "not_eligible",
    "blocked",
]

BybitTradeCountCutoverEvaluationReason = Literal[
    "mismatches_present",
    "ledger_unavailable",
    "validation_blocked_present",
    "not_comparable_present",
    "insufficient_compared_symbols",
    "all_symbols_ready_for_evaluation",
]


@dataclass(slots=True, frozen=True)
class BybitTradeCountCutoverEvaluationPolicy:
    """Formal machine-readable policy for aggregate cutover evaluation."""

    minimum_compared_symbols: int = 1

    def __post_init__(self) -> None:
        if self.minimum_compared_symbols < 1:
            raise ValueError("minimum_compared_symbols должен быть >= 1")


@dataclass(slots=True, frozen=True)
class BybitTradeCountCutoverEvaluationResult:
    """Read-only evaluation result for manual cutover discussion readiness."""

    state: BybitTradeCountCutoverEvaluationState
    reasons: tuple[BybitTradeCountCutoverEvaluationReason, ...]
    minimum_compared_symbols: int
    compared_symbols: int
    ready_symbols: int
    not_ready_symbols: int
    blocked_symbols: int


def evaluate_cutover_policy(
    *,
    reconciliation_results: tuple[BybitTradeCountReconciliationResult, ...],
    readiness: BybitTradeCountCutoverReadinessResult,
    policy: BybitTradeCountCutoverEvaluationPolicy | None = None,
) -> BybitTradeCountCutoverEvaluationResult:
    resolved_policy = policy or BybitTradeCountCutoverEvaluationPolicy()
    reasons: list[BybitTradeCountCutoverEvaluationReason] = []
    verdicts = {result.verdict for result in reconciliation_results}
    reconciliation_reasons = {result.reason for result in reconciliation_results}

    if (
        readiness.state == "blocked"
        and (
            readiness.reason == "ledger_unavailable"
            or reconciliation_reasons == {"ledger_path_unavailable"}
        )
    ):
        reasons.append("ledger_unavailable")
    if "validation_blocked" in verdicts:
        reasons.append("validation_blocked_present")
    if "mismatch" in verdicts:
        reasons.append("mismatches_present")
    if "not_comparable" in verdicts:
        reasons.append("not_comparable_present")
    blocked = any(
        reason in {"ledger_unavailable", "validation_blocked_present"} for reason in reasons
    ) or readiness.blocked_symbols > 0
    if not blocked and readiness.compared_symbols < resolved_policy.minimum_compared_symbols:
        reasons.append("insufficient_compared_symbols")
    eligible = (
        not blocked
        and not reasons
        and readiness.state == "ready_for_cutover_evaluation"
        and readiness.compared_symbols >= resolved_policy.minimum_compared_symbols
        and readiness.ready_symbols == readiness.compared_symbols
        and readiness.not_ready_symbols == 0
        and readiness.blocked_symbols == 0
    )
    if eligible:
        reasons.append("all_symbols_ready_for_evaluation")

    return BybitTradeCountCutoverEvaluationResult(
        state=(
            "eligible_for_manual_cutover_review"
            if eligible
            else "blocked"
            if blocked
            else "not_eligible"
        ),
        reasons=tuple(dict.fromkeys(reasons)),
        minimum_compared_symbols=resolved_policy.minimum_compared_symbols,
        compared_symbols=readiness.compared_symbols,
        ready_symbols=readiness.ready_symbols,
        not_ready_symbols=readiness.not_ready_symbols,
        blocked_symbols=readiness.blocked_symbols,
    )
