"""
Read-only cutover review snapshot collection/listing over review catalog.

Модуль intentionally ограничен reporting/listing semantics без durable storage,
workflow engine, action semantics или real cutover execution.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bybit_trade_count_cutover_review_catalog import BybitTradeCountCutoverReviewCatalog


@dataclass(slots=True, frozen=True)
class BybitTradeCountCutoverReviewSnapshotCollection:
    """Structured read-only listing over the current cutover review catalog."""

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
    current_review_catalog: BybitTradeCountCutoverReviewCatalog
    current_review_package_headline: str
    current_review_package_discussion_state: str


def build_cutover_review_snapshot_collection(
    *,
    review_catalog: BybitTradeCountCutoverReviewCatalog,
) -> BybitTradeCountCutoverReviewSnapshotCollection:
    return BybitTradeCountCutoverReviewSnapshotCollection(
        contour=review_catalog.contour,
        scope_mode=review_catalog.scope_mode,
        headline=review_catalog.headline,
        discussion_state=review_catalog.discussion_state,
        manual_review_state=review_catalog.manual_review_state,
        cutover_evaluation_state=review_catalog.cutover_evaluation_state,
        cutover_readiness_state=review_catalog.cutover_readiness_state,
        compared_symbols=review_catalog.compared_symbols,
        ready_symbols=review_catalog.ready_symbols,
        not_ready_symbols=review_catalog.not_ready_symbols,
        blocked_symbols=review_catalog.blocked_symbols,
        reasons_summary=review_catalog.reasons_summary,
        current_review_catalog=review_catalog,
        current_review_package_headline=review_catalog.current_review_package.headline,
        current_review_package_discussion_state=(
            review_catalog.current_review_package.discussion_state
        ),
    )
