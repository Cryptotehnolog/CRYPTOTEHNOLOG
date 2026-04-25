from __future__ import annotations

from cryptotechnolog.live_feed.bybit_trade_count_cutover_discussion import (
    BybitTradeCountCutoverDiscussionArtifact,
    BybitTradeCountCutoverDiscussionException,
    BybitTradeCountCutoverDiscussionVerdictCount,
)
from cryptotechnolog.live_feed.bybit_trade_count_cutover_review_record import (
    build_cutover_review_record,
)


def test_review_record_honestly_reflects_current_discussion_artifact() -> None:
    record = build_cutover_review_record(
        captured_at="2026-04-09T12:00:00+00:00",
        discussion_artifact=BybitTradeCountCutoverDiscussionArtifact(
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
        ),
    )

    assert record.captured_at == "2026-04-09T12:00:00+00:00"
    assert record.discussion_state == "discussion_not_ready"
    assert record.manual_review_state == "manual_review_not_recommended"
    assert record.cutover_evaluation_state == "not_eligible"
    assert record.cutover_readiness_state == "not_ready"
    assert record.reasons_summary == ("mismatches_present", "mismatch_present")
    assert record.symbol_exceptions[0]["symbol"] == "ETH/USDT"


def test_review_record_preserves_ready_discussion_without_action_semantics() -> None:
    record = build_cutover_review_record(
        captured_at="2026-04-09T12:05:00+00:00",
        discussion_artifact=BybitTradeCountCutoverDiscussionArtifact(
            discussion_state="discussion_ready",
            headline="Manual cutover review is recommended for current scope.",
            contour="linear",
            scope_mode="single_symbol",
            scope_symbol_count=1,
            reconciliation_summary=(
                BybitTradeCountCutoverDiscussionVerdictCount(name="match", count=1),
            ),
            cutover_readiness_state="ready_for_cutover_evaluation",
            cutover_readiness_reason="all_compared_symbols_match",
            cutover_evaluation_state="eligible_for_manual_cutover_review",
            cutover_evaluation_reasons=("all_symbols_ready_for_evaluation",),
            manual_review_state="manual_review_recommended",
            manual_review_reasons=("all_symbols_ready_for_evaluation",),
            compared_symbols=1,
            ready_symbols=1,
            not_ready_symbols=0,
            blocked_symbols=0,
            symbol_exceptions=(),
        ),
    )

    assert record.captured_at == "2026-04-09T12:05:00+00:00"
    assert record.discussion_state == "discussion_ready"
    assert record.manual_review_state == "manual_review_recommended"
    assert record.symbol_exceptions == ()
