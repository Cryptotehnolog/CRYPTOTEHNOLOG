from __future__ import annotations

from cryptotechnolog.live_feed.bybit_trade_count_cutover_discussion import (
    build_cutover_discussion_artifact,
)
from cryptotechnolog.live_feed.bybit_trade_count_cutover_evaluation import (
    BybitTradeCountCutoverEvaluationResult,
)
from cryptotechnolog.live_feed.bybit_trade_count_cutover_readiness import (
    BybitTradeCountCutoverReadinessResult,
)
from cryptotechnolog.live_feed.bybit_trade_count_manual_review import (
    BybitTradeCountManualReviewResult,
)
from cryptotechnolog.live_feed.bybit_trade_count_reconciliation import (
    BybitTradeCountReconciliationResult,
)


def _reconciliation(verdict: str, reason: str) -> BybitTradeCountReconciliationResult:
    return BybitTradeCountReconciliationResult(
        verdict=verdict,  # type: ignore[arg-type]
        bucket_trade_count_24h=None,
        ledger_trade_count_24h=None,
        absolute_diff=None,
        tolerance=0,
        reason=reason,
    )


def _readiness(state: str, reason: str) -> BybitTradeCountCutoverReadinessResult:
    return BybitTradeCountCutoverReadinessResult(
        state=state,  # type: ignore[arg-type]
        reason=reason,
        compared_symbols=2,
        ready_symbols=1,
        not_ready_symbols=1,
        blocked_symbols=0,
    )


def _evaluation(state: str, reasons: tuple[str, ...]) -> BybitTradeCountCutoverEvaluationResult:
    return BybitTradeCountCutoverEvaluationResult(
        state=state,  # type: ignore[arg-type]
        reasons=reasons,  # type: ignore[arg-type]
        minimum_compared_symbols=1,
        compared_symbols=2,
        ready_symbols=1,
        not_ready_symbols=1,
        blocked_symbols=0,
    )


def _manual_review(state: str, reasons: tuple[str, ...]) -> BybitTradeCountManualReviewResult:
    return BybitTradeCountManualReviewResult(
        state=state,  # type: ignore[arg-type]
        reasons=reasons,  # type: ignore[arg-type]
        evaluation_state="not_eligible",
        contour="linear",
        scope_mode="universe",
        scope_symbol_count=2,
        compared_symbols=2,
        ready_symbols=1,
        not_ready_symbols=1,
        blocked_symbols=0,
    )


def test_discussion_artifact_honestly_summarizes_current_cutover_state() -> None:
    artifact = build_cutover_discussion_artifact(
        contour="linear",
        scope_mode="universe",
        scope_symbol_count=2,
        reconciliation_results=(
            _reconciliation("match", "counts_equal"),
            _reconciliation("mismatch", "difference_exceeds_absolute_tolerance"),
        ),
        cutover_readiness=_readiness("not_ready", "mismatch_present"),
        cutover_evaluation=_evaluation("not_eligible", ("mismatches_present",)),
        manual_review=_manual_review("manual_review_not_recommended", ("mismatches_present",)),
        symbol_snapshots=(
            {
                "symbol": "BTC/USDT",
                "trade_count_reconciliation_verdict": "match",
                "trade_count_reconciliation_reason": "counts_equal",
                "trade_count_cutover_readiness_state": "ready_for_cutover_evaluation",
                "trade_count_cutover_readiness_reason": "all_compared_symbols_match",
            },
            {
                "symbol": "ETH/USDT",
                "trade_count_reconciliation_verdict": "mismatch",
                "trade_count_reconciliation_reason": "difference_exceeds_absolute_tolerance",
                "trade_count_cutover_readiness_state": "not_ready",
                "trade_count_cutover_readiness_reason": "mismatch_present",
            },
        ),
    )

    assert artifact.discussion_state == "discussion_not_ready"
    assert artifact.manual_review_state == "manual_review_not_recommended"
    assert artifact.cutover_evaluation_state == "not_eligible"
    assert artifact.cutover_readiness_state == "not_ready"
    assert artifact.compared_symbols == 2
    assert artifact.symbol_exceptions[0].symbol == "ETH/USDT"
    assert artifact.symbol_exceptions[0].reconciliation_verdict == "mismatch"
    assert artifact.reconciliation_summary[0].name == "mismatch"
    assert artifact.reconciliation_summary[0].count == 1


def test_discussion_artifact_is_ready_when_manual_review_is_recommended() -> None:
    artifact = build_cutover_discussion_artifact(
        contour="linear",
        scope_mode="single_symbol",
        scope_symbol_count=1,
        reconciliation_results=(
            _reconciliation("match", "counts_equal"),
        ),
        cutover_readiness=BybitTradeCountCutoverReadinessResult(
            state="ready_for_cutover_evaluation",
            reason="all_compared_symbols_match",
            compared_symbols=1,
            ready_symbols=1,
            not_ready_symbols=0,
            blocked_symbols=0,
        ),
        cutover_evaluation=BybitTradeCountCutoverEvaluationResult(
            state="eligible_for_manual_cutover_review",
            reasons=("all_symbols_ready_for_evaluation",),
            minimum_compared_symbols=1,
            compared_symbols=1,
            ready_symbols=1,
            not_ready_symbols=0,
            blocked_symbols=0,
        ),
        manual_review=BybitTradeCountManualReviewResult(
            state="manual_review_recommended",
            reasons=("all_symbols_ready_for_evaluation",),
            evaluation_state="eligible_for_manual_cutover_review",
            contour="linear",
            scope_mode="single_symbol",
            scope_symbol_count=1,
            compared_symbols=1,
            ready_symbols=1,
            not_ready_symbols=0,
            blocked_symbols=0,
        ),
        symbol_snapshots=(
            {
                "symbol": "BTC/USDT",
                "trade_count_reconciliation_verdict": "match",
                "trade_count_reconciliation_reason": "counts_equal",
                "trade_count_cutover_readiness_state": "ready_for_cutover_evaluation",
                "trade_count_cutover_readiness_reason": "all_compared_symbols_match",
            },
        ),
    )

    assert artifact.discussion_state == "discussion_ready"
    assert artifact.headline == "Manual cutover review is recommended for current scope."
    assert artifact.symbol_exceptions == ()
