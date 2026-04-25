"""
Read-only compact cutover review digest over review snapshot collection.

Модуль intentionally ограничен reporting/digest semantics без durable storage,
workflow engine, action semantics или real cutover execution.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bybit_trade_count_cutover_review_snapshot_collection import (
    BybitTradeCountCutoverReviewSnapshotCollection,
)


@dataclass(slots=True, frozen=True)
class BybitTradeCountCutoverReviewCompactDigest:
    """Structured read-only compact digest for current cutover review status."""

    contour: str
    scope_mode: str
    headline: str
    discussion_state: str
    manual_review_state: str
    cutover_evaluation_state: str
    cutover_readiness_state: str
    compared_symbols: int
    ready_symbols: int
    not_ready_symbols: int
    blocked_symbols: int
    reasons_summary: tuple[str, ...]
    compact_symbol_exceptions: tuple[str, ...]
    current_review_snapshot_collection: BybitTradeCountCutoverReviewSnapshotCollection


def build_cutover_review_compact_digest(
    *,
    review_snapshot_collection: BybitTradeCountCutoverReviewSnapshotCollection,
) -> BybitTradeCountCutoverReviewCompactDigest:
    symbol_exceptions = (
        review_snapshot_collection.current_review_catalog.current_review_package.symbol_exceptions
    )
    return BybitTradeCountCutoverReviewCompactDigest(
        contour=review_snapshot_collection.contour,
        scope_mode=review_snapshot_collection.scope_mode,
        headline=review_snapshot_collection.headline,
        discussion_state=review_snapshot_collection.discussion_state,
        manual_review_state=review_snapshot_collection.manual_review_state,
        cutover_evaluation_state=review_snapshot_collection.cutover_evaluation_state,
        cutover_readiness_state=review_snapshot_collection.cutover_readiness_state,
        compared_symbols=review_snapshot_collection.compared_symbols,
        ready_symbols=review_snapshot_collection.ready_symbols,
        not_ready_symbols=review_snapshot_collection.not_ready_symbols,
        blocked_symbols=review_snapshot_collection.blocked_symbols,
        reasons_summary=review_snapshot_collection.reasons_summary,
        compact_symbol_exceptions=tuple(
            str(item.get("symbol", ""))
            for item in symbol_exceptions
            if isinstance(item, dict) and str(item.get("symbol", ""))
        ),
        current_review_snapshot_collection=review_snapshot_collection,
    )
