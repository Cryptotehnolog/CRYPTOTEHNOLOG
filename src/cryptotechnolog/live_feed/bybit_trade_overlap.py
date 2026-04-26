"""
Canonical overlap semantics between archive-side and live-side Bybit trade facts.

Модуль intentionally ограничен только contract-level comparison logic
без repository/runtime/query/reconciliation wiring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BybitTradeOverlapVerdict = Literal[
    "exact_match_candidate",
    "fallback_match_candidate",
    "no_match",
    "ambiguous",
]


@dataclass(slots=True, frozen=True)
class BybitTradeOverlapResult:
    """Machine-readable overlap comparison result for one archive/live pair."""

    verdict: BybitTradeOverlapVerdict
    reason: str
    metadata: dict[str, str] = field(default_factory=dict)


def compare_archive_and_live_trade(
    *,
    archive_extraction,
    archive_identity,
    live_fact_result,
    live_identity,
) -> BybitTradeOverlapResult:
    archive_fact = archive_extraction.trade_fact
    live_fact = live_fact_result.trade_fact
    if (
        archive_fact is None
        or live_fact is None
        or archive_identity.verdict == "not_identifiable"
        or live_identity.verdict == "not_identifiable"
    ):
        return BybitTradeOverlapResult(
            verdict="ambiguous",
            reason="comparison_inputs_not_identifiable",
            metadata={
                "archive_identity_verdict": archive_identity.verdict,
                "live_identity_verdict": live_identity.verdict,
            },
        )
    mismatch_result = _compare_contour_and_symbol(archive_fact=archive_fact, live_fact=live_fact)
    if mismatch_result is not None:
        return mismatch_result

    same_trade_shape = (
        archive_fact.exchange_trade_at == live_fact.exchange_trade_at
        and archive_fact.side == live_fact.side
        and archive_fact.normalized_price == live_fact.normalized_price
        and archive_fact.normalized_size == live_fact.normalized_size
    )

    linear_result = _compare_linear_strong_id_overlap(
        archive_fact=archive_fact,
        live_fact=live_fact,
        same_trade_shape=same_trade_shape,
    )
    if linear_result is not None:
        return linear_result

    if same_trade_shape:
        return BybitTradeOverlapResult(
            verdict="fallback_match_candidate",
            reason="fallback_trade_shape_match",
            metadata={
                "contour": archive_fact.contour,
                "symbol": archive_fact.normalized_symbol,
            },
        )

    same_event_anchor = (
        archive_fact.exchange_trade_at == live_fact.exchange_trade_at
        and archive_fact.normalized_symbol == live_fact.normalized_symbol
        and archive_fact.contour == live_fact.contour
    )
    same_price_size = (
        archive_fact.normalized_price == live_fact.normalized_price
        and archive_fact.normalized_size == live_fact.normalized_size
    )
    if same_event_anchor and (same_price_size or archive_fact.side == live_fact.side):
        return BybitTradeOverlapResult(
            verdict="ambiguous",
            reason="partial_overlap_without_safe_match",
            metadata={
                "contour": archive_fact.contour,
                "symbol": archive_fact.normalized_symbol,
            },
        )

    return BybitTradeOverlapResult(
        verdict="no_match",
        reason="core_trade_shape_differs",
        metadata={
            "contour": archive_fact.contour,
            "symbol": archive_fact.normalized_symbol,
        },
    )


def _compare_contour_and_symbol(*, archive_fact, live_fact) -> BybitTradeOverlapResult | None:
    if archive_fact.contour != live_fact.contour:
        return BybitTradeOverlapResult(
            verdict="no_match",
            reason="different_contour",
            metadata={
                "archive_contour": archive_fact.contour,
                "live_contour": live_fact.contour,
            },
        )
    if archive_fact.normalized_symbol != live_fact.normalized_symbol:
        return BybitTradeOverlapResult(
            verdict="no_match",
            reason="different_symbol",
            metadata={
                "archive_symbol": archive_fact.normalized_symbol,
                "live_symbol": live_fact.normalized_symbol,
            },
        )
    return None


def _compare_linear_strong_id_overlap(
    *,
    archive_fact,
    live_fact,
    same_trade_shape: bool,
) -> BybitTradeOverlapResult | None:
    if archive_fact.contour != "linear":
        return None
    archive_trade_id = archive_fact.archive_trade_id
    live_trade_id = live_fact.live_trade_id
    if archive_trade_id is None or archive_trade_id != live_trade_id:
        return None
    if same_trade_shape:
        return BybitTradeOverlapResult(
            verdict="exact_match_candidate",
            reason="linear_trade_id_and_shape_match",
            metadata={
                "archive_trade_id": archive_trade_id,
                "live_trade_id": live_trade_id,
            },
        )
    return BybitTradeOverlapResult(
        verdict="ambiguous",
        reason="linear_trade_id_matches_but_shape_differs",
        metadata={
            "archive_trade_id": archive_trade_id,
            "live_trade_id": live_trade_id,
        },
    )
