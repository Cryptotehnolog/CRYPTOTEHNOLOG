"""
Scoped read-only manual-review/governance surface over cutover evaluation verdict.

Модуль intentionally ограничен governance read-model semantics без
approval workflow engine, runtime switch или real cutover execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .bybit_trade_count_cutover_evaluation import BybitTradeCountCutoverEvaluationResult

BybitTradeCountManualReviewState = Literal[
    "manual_review_recommended",
    "manual_review_not_recommended",
    "manual_review_blocked",
]

BybitTradeCountManualReviewReason = Literal[
    "mismatches_present",
    "ledger_unavailable",
    "validation_blocked_present",
    "not_comparable_present",
    "insufficient_compared_symbols",
    "all_symbols_ready_for_evaluation",
]


@dataclass(slots=True, frozen=True)
class BybitTradeCountManualReviewResult:
    """Read-only governance/manual-review verdict for current connector scope."""

    state: BybitTradeCountManualReviewState
    reasons: tuple[BybitTradeCountManualReviewReason, ...]
    evaluation_state: str
    contour: str
    scope_mode: str
    scope_symbol_count: int
    compared_symbols: int
    ready_symbols: int
    not_ready_symbols: int
    blocked_symbols: int


def manual_review_from_cutover_evaluation(
    *,
    evaluation: BybitTradeCountCutoverEvaluationResult,
    contour: str,
    scope_mode: str,
    scope_symbol_count: int,
) -> BybitTradeCountManualReviewResult:
    return BybitTradeCountManualReviewResult(
        state=(
            "manual_review_recommended"
            if evaluation.state == "eligible_for_manual_cutover_review"
            else "manual_review_blocked"
            if evaluation.state == "blocked"
            else "manual_review_not_recommended"
        ),
        reasons=evaluation.reasons,
        evaluation_state=evaluation.state,
        contour=contour,
        scope_mode=scope_mode,
        scope_symbol_count=scope_symbol_count,
        compared_symbols=evaluation.compared_symbols,
        ready_symbols=evaluation.ready_symbols,
        not_ready_symbols=evaluation.not_ready_symbols,
        blocked_symbols=evaluation.blocked_symbols,
    )
