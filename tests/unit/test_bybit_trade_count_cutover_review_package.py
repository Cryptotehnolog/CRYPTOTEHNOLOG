from __future__ import annotations

from cryptotechnolog.live_feed.bybit_trade_count_cutover_review_package import (
    build_cutover_review_package,
)
from cryptotechnolog.live_feed.bybit_trade_count_cutover_review_record import (
    BybitTradeCountCutoverReviewRecord,
)
from cryptotechnolog.live_feed.bybit_trade_count_cutover_discussion import (
    BybitTradeCountCutoverDiscussionArtifact,
    BybitTradeCountCutoverDiscussionException,
    BybitTradeCountCutoverDiscussionVerdictCount,
)


def test_review_package_honestly_reflects_discussion_artifact_and_review_record() -> None:
    discussion = BybitTradeCountCutoverDiscussionArtifact(
        discussion_state="discussion_not_ready",
        headline="Manual cutover review is not recommended for current scope.",
        contour="linear",
        scope_mode="universe",
        scope_symbol_count=2,
        reconciliation_summary=(
            BybitTradeCountCutoverDiscussionVerdictCount(name="mismatch", count=1),
        ),
        cutover_readiness_state="not_ready",
        cutover_readiness_reason="mismatch_present",
        cutover_evaluation_state="not_eligible",
        cutover_evaluation_reasons=("mismatches_present",),
        manual_review_state="manual_review_not_recommended",
        manual_review_reasons=("mismatches_present",),
        compared_symbols=2,
        ready_symbols=1,
        not_ready_symbols=1,
        blocked_symbols=0,
        symbol_exceptions=(
            BybitTradeCountCutoverDiscussionException(
                symbol="ETH/USDT",
                reconciliation_verdict="mismatch",
                reconciliation_reason="difference_exceeds_absolute_tolerance",
                cutover_readiness_state="not_ready",
                cutover_readiness_reason="mismatch_present",
            ),
        ),
    )
    record = BybitTradeCountCutoverReviewRecord(
        captured_at="2026-04-09T12:00:00+00:00",
        contour="linear",
        scope_mode="universe",
        scope_symbol_count=2,
        discussion_state="discussion_not_ready",
        manual_review_state="manual_review_not_recommended",
        cutover_evaluation_state="not_eligible",
        cutover_readiness_state="not_ready",
        compared_symbols=2,
        ready_symbols=1,
        not_ready_symbols=1,
        blocked_symbols=0,
        headline="Manual cutover review is not recommended for current scope.",
        reasons_summary=("mismatches_present", "mismatch_present"),
        symbol_exceptions=(
            {
                "symbol": "ETH/USDT",
                "reconciliation_verdict": "mismatch",
                "reconciliation_reason": "difference_exceeds_absolute_tolerance",
                "cutover_readiness_state": "not_ready",
                "cutover_readiness_reason": "mismatch_present",
            },
        ),
    )

    package = build_cutover_review_package(
        discussion_artifact=discussion,
        review_record=record,
    )

    assert package.contour == "linear"
    assert package.scope_mode == "universe"
    assert package.scope_symbol_count == 2
    assert package.discussion_state == "discussion_not_ready"
    assert package.manual_review_state == "manual_review_not_recommended"
    assert package.cutover_evaluation_state == "not_eligible"
    assert package.cutover_readiness_state == "not_ready"
    assert package.compared_symbols == 2
    assert package.not_ready_symbols == 1
    assert package.headline == "Manual cutover review is not recommended for current scope."
    assert package.reasons_summary == ("mismatches_present", "mismatch_present")
    assert package.review_record.captured_at == "2026-04-09T12:00:00+00:00"
    assert package.symbol_exceptions[0]["symbol"] == "ETH/USDT"
