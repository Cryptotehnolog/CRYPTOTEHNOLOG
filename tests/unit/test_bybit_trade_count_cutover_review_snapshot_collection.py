from __future__ import annotations

from cryptotechnolog.live_feed.bybit_trade_count_cutover_discussion import (
    BybitTradeCountCutoverDiscussionArtifact,
    BybitTradeCountCutoverDiscussionException,
    BybitTradeCountCutoverDiscussionVerdictCount,
)
from cryptotechnolog.live_feed.bybit_trade_count_cutover_review_catalog import (
    build_cutover_review_catalog,
)
from cryptotechnolog.live_feed.bybit_trade_count_cutover_review_package import (
    build_cutover_review_package,
)
from cryptotechnolog.live_feed.bybit_trade_count_cutover_review_record import (
    BybitTradeCountCutoverReviewRecord,
)
from cryptotechnolog.live_feed.bybit_trade_count_cutover_review_snapshot_collection import (
    build_cutover_review_snapshot_collection,
)


def test_review_snapshot_collection_honestly_reflects_current_review_catalog() -> None:
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
    catalog = build_cutover_review_catalog(review_package=package)

    collection = build_cutover_review_snapshot_collection(review_catalog=catalog)

    assert collection.contour == "linear"
    assert collection.scope_mode == "universe"
    assert collection.headline == "Manual cutover review is not recommended for current scope."
    assert collection.discussion_state == "discussion_not_ready"
    assert collection.manual_review_state == "manual_review_not_recommended"
    assert collection.cutover_evaluation_state == "not_eligible"
    assert collection.cutover_readiness_state == "not_ready"
    assert collection.compared_symbols == 2
    assert collection.ready_symbols == 1
    assert collection.not_ready_symbols == 1
    assert collection.blocked_symbols == 0
    assert collection.reasons_summary == ("mismatches_present", "mismatch_present")
    assert collection.current_review_package_headline == (
        "Manual cutover review is not recommended for current scope."
    )
    assert collection.current_review_package_discussion_state == "discussion_not_ready"
    assert collection.current_review_catalog.current_review_package.review_record.captured_at == (
        "2026-04-09T12:00:00+00:00"
    )
    assert collection.current_review_catalog.current_review_package.symbol_exceptions[0]["symbol"] == (
        "ETH/USDT"
    )
