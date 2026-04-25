from __future__ import annotations

import pytest

from cryptotechnolog.live_feed.bybit_trade_count_cutover_evaluation import (
    BybitTradeCountCutoverEvaluationPolicy,
    evaluate_cutover_policy,
)
from cryptotechnolog.live_feed.bybit_trade_count_cutover_readiness import (
    BybitTradeCountCutoverReadinessResult,
)
from cryptotechnolog.live_feed.bybit_trade_count_reconciliation import (
    BybitTradeCountReconciliationResult,
)


def _reconciliation_result(
    verdict: str,
    *,
    reason: str,
) -> BybitTradeCountReconciliationResult:
    return BybitTradeCountReconciliationResult(
        verdict=verdict,  # type: ignore[arg-type]
        bucket_trade_count_24h=None,
        ledger_trade_count_24h=None,
        absolute_diff=None,
        tolerance=0,
        reason=reason,
    )


def _readiness_result(
    *,
    state: str,
    reason: str,
    compared_symbols: int,
    ready_symbols: int,
    not_ready_symbols: int,
    blocked_symbols: int,
) -> BybitTradeCountCutoverReadinessResult:
    return BybitTradeCountCutoverReadinessResult(
        state=state,  # type: ignore[arg-type]
        reason=reason,
        compared_symbols=compared_symbols,
        ready_symbols=ready_symbols,
        not_ready_symbols=not_ready_symbols,
        blocked_symbols=blocked_symbols,
    )


def test_evaluation_policy_is_eligible_when_all_required_conditions_are_met() -> None:
    result = evaluate_cutover_policy(
        reconciliation_results=(
            _reconciliation_result("match", reason="counts_equal"),
            _reconciliation_result("within_tolerance", reason="difference_within_absolute_tolerance"),
        ),
        readiness=_readiness_result(
            state="ready_for_cutover_evaluation",
            reason="all_compared_symbols_within_policy",
            compared_symbols=2,
            ready_symbols=2,
            not_ready_symbols=0,
            blocked_symbols=0,
        ),
    )

    assert result.state == "eligible_for_manual_cutover_review"
    assert result.reasons == ("all_symbols_ready_for_evaluation",)


def test_evaluation_policy_is_not_eligible_when_mismatch_present() -> None:
    result = evaluate_cutover_policy(
        reconciliation_results=(
            _reconciliation_result(
                "mismatch",
                reason="difference_exceeds_absolute_tolerance",
            ),
        ),
        readiness=_readiness_result(
            state="not_ready",
            reason="mismatch_present",
            compared_symbols=1,
            ready_symbols=0,
            not_ready_symbols=1,
            blocked_symbols=0,
        ),
    )

    assert result.state == "not_eligible"
    assert result.reasons == ("mismatches_present",)


def test_evaluation_policy_is_blocked_when_ledger_is_unavailable() -> None:
    result = evaluate_cutover_policy(
        reconciliation_results=(
            _reconciliation_result("validation_blocked", reason="ledger_path_unavailable"),
        ),
        readiness=_readiness_result(
            state="blocked",
            reason="ledger_unavailable",
            compared_symbols=0,
            ready_symbols=0,
            not_ready_symbols=0,
            blocked_symbols=1,
        ),
    )

    assert result.state == "blocked"
    assert result.reasons == ("ledger_unavailable", "validation_blocked_present")


def test_evaluation_policy_is_not_eligible_when_not_comparable_symbols_exist() -> None:
    result = evaluate_cutover_policy(
        reconciliation_results=(
            _reconciliation_result("not_comparable", reason="one_side_missing"),
        ),
        readiness=_readiness_result(
            state="not_ready",
            reason="not_comparable_symbols_present",
            compared_symbols=0,
            ready_symbols=0,
            not_ready_symbols=1,
            blocked_symbols=0,
        ),
    )

    assert result.state == "not_eligible"
    assert result.reasons == (
        "not_comparable_present",
        "insufficient_compared_symbols",
    )


def test_evaluation_policy_is_not_eligible_when_compared_scope_is_insufficient() -> None:
    result = evaluate_cutover_policy(
        reconciliation_results=(),
        readiness=_readiness_result(
            state="not_ready",
            reason="no_symbols_compared",
            compared_symbols=0,
            ready_symbols=0,
            not_ready_symbols=0,
            blocked_symbols=0,
        ),
        policy=BybitTradeCountCutoverEvaluationPolicy(minimum_compared_symbols=2),
    )

    assert result.state == "not_eligible"
    assert result.reasons == ("insufficient_compared_symbols",)


def test_evaluation_policy_rejects_non_positive_minimum_scope() -> None:
    with pytest.raises(ValueError, match="minimum_compared_symbols"):
        BybitTradeCountCutoverEvaluationPolicy(minimum_compared_symbols=0)
