"""
Read-only archived cutover review record surface over current discussion artifact.

Модуль intentionally ограничен reporting/history snapshot semantics без
durable workflow engine, action log или real cutover execution.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bybit_trade_count_cutover_discussion import BybitTradeCountCutoverDiscussionArtifact


@dataclass(slots=True, frozen=True)
class BybitTradeCountCutoverReviewRecord:
    """Structured read-only snapshot of current cutover discussion state."""

    captured_at: str
    contour: str
    scope_mode: str
    scope_symbol_count: int
    discussion_state: str
    manual_review_state: str
    cutover_evaluation_state: str
    cutover_readiness_state: str
    compared_symbols: int
    ready_symbols: int
    not_ready_symbols: int
    blocked_symbols: int
    headline: str
    reasons_summary: tuple[str, ...]
    symbol_exceptions: tuple[dict[str, str | None], ...]


def build_cutover_review_record(
    *,
    captured_at: str,
    discussion_artifact: BybitTradeCountCutoverDiscussionArtifact,
) -> BybitTradeCountCutoverReviewRecord:
    reasons_summary = tuple(
        dict.fromkeys(
            (
                *discussion_artifact.manual_review_reasons,
                *discussion_artifact.cutover_evaluation_reasons,
                discussion_artifact.cutover_readiness_reason,
            )
        )
    )
    return BybitTradeCountCutoverReviewRecord(
        captured_at=captured_at,
        contour=discussion_artifact.contour,
        scope_mode=discussion_artifact.scope_mode,
        scope_symbol_count=discussion_artifact.scope_symbol_count,
        discussion_state=discussion_artifact.discussion_state,
        manual_review_state=discussion_artifact.manual_review_state,
        cutover_evaluation_state=discussion_artifact.cutover_evaluation_state,
        cutover_readiness_state=discussion_artifact.cutover_readiness_state,
        compared_symbols=discussion_artifact.compared_symbols,
        ready_symbols=discussion_artifact.ready_symbols,
        not_ready_symbols=discussion_artifact.not_ready_symbols,
        blocked_symbols=discussion_artifact.blocked_symbols,
        headline=discussion_artifact.headline,
        reasons_summary=reasons_summary,
        symbol_exceptions=tuple(
            {
                "symbol": item.symbol,
                "reconciliation_verdict": item.reconciliation_verdict,
                "reconciliation_reason": item.reconciliation_reason,
                "cutover_readiness_state": item.cutover_readiness_state,
                "cutover_readiness_reason": item.cutover_readiness_reason,
            }
            for item in discussion_artifact.symbol_exceptions
        ),
    )
