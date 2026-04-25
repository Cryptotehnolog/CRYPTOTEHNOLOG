"""
Operator-facing read-only cutover discussion artifact over existing diagnostics layers.

Модуль intentionally ограничен reporting/read-model semantics без
action workflow, runtime switch или real cutover execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .bybit_trade_count_cutover_evaluation import BybitTradeCountCutoverEvaluationResult
from .bybit_trade_count_cutover_readiness import BybitTradeCountCutoverReadinessResult
from .bybit_trade_count_manual_review import BybitTradeCountManualReviewResult
from .bybit_trade_count_reconciliation import BybitTradeCountReconciliationResult

BybitTradeCountCutoverDiscussionState = Literal[
    "discussion_ready",
    "discussion_not_ready",
    "discussion_blocked",
]


@dataclass(slots=True, frozen=True)
class BybitTradeCountCutoverDiscussionVerdictCount:
    name: str
    count: int


@dataclass(slots=True, frozen=True)
class BybitTradeCountCutoverDiscussionException:
    symbol: str
    reconciliation_verdict: str | None
    reconciliation_reason: str | None
    cutover_readiness_state: str | None
    cutover_readiness_reason: str | None


@dataclass(slots=True, frozen=True)
class BybitTradeCountCutoverDiscussionArtifact:
    """Read-only operator-facing summary artifact for cutover discussion."""

    discussion_state: BybitTradeCountCutoverDiscussionState
    headline: str
    contour: str
    scope_mode: str
    scope_symbol_count: int
    reconciliation_summary: tuple[BybitTradeCountCutoverDiscussionVerdictCount, ...]
    cutover_readiness_state: str
    cutover_readiness_reason: str
    cutover_evaluation_state: str
    cutover_evaluation_reasons: tuple[str, ...]
    manual_review_state: str
    manual_review_reasons: tuple[str, ...]
    compared_symbols: int
    ready_symbols: int
    not_ready_symbols: int
    blocked_symbols: int
    symbol_exceptions: tuple[BybitTradeCountCutoverDiscussionException, ...]


def build_cutover_discussion_artifact(
    *,
    contour: str,
    scope_mode: str,
    scope_symbol_count: int,
    reconciliation_results: tuple[BybitTradeCountReconciliationResult, ...],
    cutover_readiness: BybitTradeCountCutoverReadinessResult,
    cutover_evaluation: BybitTradeCountCutoverEvaluationResult,
    manual_review: BybitTradeCountManualReviewResult,
    symbol_snapshots: tuple[dict[str, object], ...],
) -> BybitTradeCountCutoverDiscussionArtifact:
    verdict_order = (
        "validation_blocked",
        "mismatch",
        "not_comparable",
        "within_tolerance",
        "match",
    )
    verdict_counts = {
        verdict: sum(1 for result in reconciliation_results if result.verdict == verdict)
        for verdict in verdict_order
    }
    reconciliation_summary = tuple(
        BybitTradeCountCutoverDiscussionVerdictCount(name=verdict, count=count)
        for verdict, count in verdict_counts.items()
        if count > 0
    )
    symbol_exceptions = tuple(
        BybitTradeCountCutoverDiscussionException(
            symbol=str(snapshot.get("symbol", "")),
            reconciliation_verdict=(
                str(snapshot["trade_count_reconciliation_verdict"])
                if isinstance(snapshot.get("trade_count_reconciliation_verdict"), str)
                else None
            ),
            reconciliation_reason=(
                str(snapshot["trade_count_reconciliation_reason"])
                if isinstance(snapshot.get("trade_count_reconciliation_reason"), str)
                else None
            ),
            cutover_readiness_state=(
                str(snapshot["trade_count_cutover_readiness_state"])
                if isinstance(snapshot.get("trade_count_cutover_readiness_state"), str)
                else None
            ),
            cutover_readiness_reason=(
                str(snapshot["trade_count_cutover_readiness_reason"])
                if isinstance(snapshot.get("trade_count_cutover_readiness_reason"), str)
                else None
            ),
        )
        for snapshot in symbol_snapshots
        if snapshot.get("trade_count_reconciliation_verdict") not in {"match", "within_tolerance"}
    )
    discussion_state = (
        "discussion_ready"
        if manual_review.state == "manual_review_recommended"
        else "discussion_blocked"
        if manual_review.state == "manual_review_blocked"
        else "discussion_not_ready"
    )
    headline = (
        "Manual cutover review is recommended for current scope."
        if manual_review.state == "manual_review_recommended"
        else "Manual cutover review is blocked for current scope."
        if manual_review.state == "manual_review_blocked"
        else "Manual cutover review is not recommended for current scope."
    )
    return BybitTradeCountCutoverDiscussionArtifact(
        discussion_state=discussion_state,
        headline=headline,
        contour=contour,
        scope_mode=scope_mode,
        scope_symbol_count=scope_symbol_count,
        reconciliation_summary=reconciliation_summary,
        cutover_readiness_state=cutover_readiness.state,
        cutover_readiness_reason=cutover_readiness.reason,
        cutover_evaluation_state=cutover_evaluation.state,
        cutover_evaluation_reasons=cutover_evaluation.reasons,
        manual_review_state=manual_review.state,
        manual_review_reasons=manual_review.reasons,
        compared_symbols=manual_review.compared_symbols,
        ready_symbols=manual_review.ready_symbols,
        not_ready_symbols=manual_review.not_ready_symbols,
        blocked_symbols=manual_review.blocked_symbols,
        symbol_exceptions=symbol_exceptions,
    )
