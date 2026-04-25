"""
Read-only cutover review package artifact over discussion artifact and review record.

Модуль intentionally ограничен reporting/review-bundle semantics без
workflow engine, action semantics или real cutover execution.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bybit_trade_count_cutover_discussion import BybitTradeCountCutoverDiscussionArtifact
from .bybit_trade_count_cutover_review_record import BybitTradeCountCutoverReviewRecord


@dataclass(slots=True, frozen=True)
class BybitTradeCountCutoverReviewPackage:
    """Structured read-only bundle for manual cutover discussion."""

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
    review_record: BybitTradeCountCutoverReviewRecord
    symbol_exceptions: tuple[dict[str, str | None], ...]


def build_cutover_review_package(
    *,
    discussion_artifact: BybitTradeCountCutoverDiscussionArtifact,
    review_record: BybitTradeCountCutoverReviewRecord,
) -> BybitTradeCountCutoverReviewPackage:
    return BybitTradeCountCutoverReviewPackage(
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
        reasons_summary=review_record.reasons_summary,
        review_record=review_record,
        symbol_exceptions=review_record.symbol_exceptions,
    )
