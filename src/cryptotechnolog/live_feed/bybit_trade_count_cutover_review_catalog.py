"""
Read-only cutover review catalog/index surface over review package artifact.

Модуль intentionally ограничен reporting/index semantics без durable storage,
workflow engine, action semantics или real cutover execution.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bybit_trade_count_cutover_review_package import BybitTradeCountCutoverReviewPackage


@dataclass(slots=True, frozen=True)
class BybitTradeCountCutoverReviewCatalog:
    """Structured read-only index over the current cutover review package."""

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
    current_review_package: BybitTradeCountCutoverReviewPackage


def build_cutover_review_catalog(
    *,
    review_package: BybitTradeCountCutoverReviewPackage,
) -> BybitTradeCountCutoverReviewCatalog:
    return BybitTradeCountCutoverReviewCatalog(
        contour=review_package.contour,
        scope_mode=review_package.scope_mode,
        headline=review_package.headline,
        discussion_state=review_package.discussion_state,
        manual_review_state=review_package.manual_review_state,
        cutover_evaluation_state=review_package.cutover_evaluation_state,
        cutover_readiness_state=review_package.cutover_readiness_state,
        compared_symbols=review_package.compared_symbols,
        ready_symbols=review_package.ready_symbols,
        not_ready_symbols=review_package.not_ready_symbols,
        blocked_symbols=review_package.blocked_symbols,
        reasons_summary=review_package.reasons_summary,
        current_review_package=review_package,
    )
