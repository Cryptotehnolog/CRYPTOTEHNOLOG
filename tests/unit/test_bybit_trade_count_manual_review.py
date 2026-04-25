from __future__ import annotations

from cryptotechnolog.live_feed.bybit_trade_count_cutover_evaluation import (
    BybitTradeCountCutoverEvaluationResult,
)
from cryptotechnolog.live_feed.bybit_trade_count_manual_review import (
    manual_review_from_cutover_evaluation,
)


def _evaluation_result(
    *,
    state: str,
    reasons: tuple[str, ...],
    compared_symbols: int = 1,
    ready_symbols: int = 0,
    not_ready_symbols: int = 0,
    blocked_symbols: int = 0,
) -> BybitTradeCountCutoverEvaluationResult:
    return BybitTradeCountCutoverEvaluationResult(
        state=state,  # type: ignore[arg-type]
        reasons=reasons,  # type: ignore[arg-type]
        minimum_compared_symbols=1,
        compared_symbols=compared_symbols,
        ready_symbols=ready_symbols,
        not_ready_symbols=not_ready_symbols,
        blocked_symbols=blocked_symbols,
    )


def test_manual_review_is_recommended_when_cutover_evaluation_is_eligible() -> None:
    result = manual_review_from_cutover_evaluation(
        evaluation=_evaluation_result(
            state="eligible_for_manual_cutover_review",
            reasons=("all_symbols_ready_for_evaluation",),
            compared_symbols=2,
            ready_symbols=2,
        ),
        contour="linear",
        scope_mode="universe",
        scope_symbol_count=2,
    )

    assert result.state == "manual_review_recommended"
    assert result.reasons == ("all_symbols_ready_for_evaluation",)
    assert result.evaluation_state == "eligible_for_manual_cutover_review"
    assert result.contour == "linear"
    assert result.scope_mode == "universe"
    assert result.scope_symbol_count == 2


def test_manual_review_is_not_recommended_when_cutover_evaluation_is_not_eligible() -> None:
    result = manual_review_from_cutover_evaluation(
        evaluation=_evaluation_result(
            state="not_eligible",
            reasons=("mismatches_present",),
            compared_symbols=2,
            ready_symbols=1,
            not_ready_symbols=1,
        ),
        contour="linear",
        scope_mode="universe",
        scope_symbol_count=2,
    )

    assert result.state == "manual_review_not_recommended"
    assert result.reasons == ("mismatches_present",)
    assert result.not_ready_symbols == 1


def test_manual_review_is_blocked_when_cutover_evaluation_is_blocked() -> None:
    result = manual_review_from_cutover_evaluation(
        evaluation=_evaluation_result(
            state="blocked",
            reasons=("ledger_unavailable", "validation_blocked_present"),
            compared_symbols=0,
            blocked_symbols=1,
        ),
        contour="spot",
        scope_mode="single_symbol",
        scope_symbol_count=1,
    )

    assert result.state == "manual_review_blocked"
    assert result.reasons == ("ledger_unavailable", "validation_blocked_present")
    assert result.contour == "spot"
    assert result.scope_mode == "single_symbol"
    assert result.scope_symbol_count == 1
