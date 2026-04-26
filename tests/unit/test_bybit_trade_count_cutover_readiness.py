from __future__ import annotations

from cryptotechnolog.live_feed.bybit_trade_count_cutover_readiness import (
    aggregate_cutover_readiness,
    readiness_from_reconciliation_result,
)
from cryptotechnolog.live_feed.bybit_trade_count_reconciliation import (
    BybitTradeCountReconciliationResult,
)


def make_reconciliation_result(verdict: str, *, reason: str) -> BybitTradeCountReconciliationResult:
    return BybitTradeCountReconciliationResult(
        verdict=verdict,  # type: ignore[arg-type]
        bucket_trade_count_24h=None,
        ledger_trade_count_24h=None,
        absolute_diff=None,
        tolerance=0,
        reason=reason,
    )


def test_symbol_readiness_is_positive_when_reconciliation_matches() -> None:
    result = readiness_from_reconciliation_result(
        make_reconciliation_result("match", reason="counts_equal"),
    )

    assert result.state == "ready_for_cutover_evaluation"
    assert result.reason == "all_compared_symbols_match"


def test_symbol_readiness_is_not_ready_when_reconciliation_mismatches() -> None:
    result = readiness_from_reconciliation_result(
        make_reconciliation_result("mismatch", reason="difference_exceeds_absolute_tolerance"),
    )

    assert result.state == "not_ready"
    assert result.reason == "mismatch_present"


def test_symbol_readiness_is_blocked_when_validation_is_blocked() -> None:
    result = readiness_from_reconciliation_result(
        make_reconciliation_result("validation_blocked", reason="ledger_path_unavailable"),
    )

    assert result.state == "blocked"
    assert result.reason == "validation_blocked_symbols_present"


def test_aggregate_readiness_is_positive_when_all_symbols_match() -> None:
    aggregate = aggregate_cutover_readiness(
        (
            readiness_from_reconciliation_result(
                make_reconciliation_result("match", reason="counts_equal"),
            ),
            readiness_from_reconciliation_result(
                make_reconciliation_result("match", reason="counts_equal"),
            ),
        )
    )

    assert aggregate.state == "ready_for_cutover_evaluation"
    assert aggregate.reason == "all_compared_symbols_match"
    assert aggregate.ready_symbols == 2


def test_aggregate_readiness_is_not_ready_when_any_mismatch_present() -> None:
    aggregate = aggregate_cutover_readiness(
        (
            readiness_from_reconciliation_result(
                make_reconciliation_result("match", reason="counts_equal"),
            ),
            readiness_from_reconciliation_result(
                make_reconciliation_result("mismatch", reason="difference_exceeds_absolute_tolerance"),
            ),
        )
    )

    assert aggregate.state == "not_ready"
    assert aggregate.reason == "mismatch_present"


def test_aggregate_readiness_is_blocked_when_any_symbol_is_validation_blocked() -> None:
    aggregate = aggregate_cutover_readiness(
        (
            readiness_from_reconciliation_result(
                make_reconciliation_result("match", reason="counts_equal"),
            ),
            readiness_from_reconciliation_result(
                make_reconciliation_result("validation_blocked", reason="ledger_path_unavailable"),
            ),
        )
    )

    assert aggregate.state == "blocked"
    assert aggregate.reason == "blocked_symbols_present"


def test_aggregate_readiness_is_ledger_unavailable_when_all_symbols_are_validation_blocked() -> None:
    aggregate = aggregate_cutover_readiness(
        (
            readiness_from_reconciliation_result(
                make_reconciliation_result("validation_blocked", reason="ledger_path_unavailable"),
            ),
            readiness_from_reconciliation_result(
                make_reconciliation_result("validation_blocked", reason="ledger_path_unavailable"),
            ),
        )
    )

    assert aggregate.state == "blocked"
    assert aggregate.reason == "ledger_unavailable"


def test_aggregate_readiness_is_not_ready_when_only_not_comparable_symbols_exist() -> None:
    aggregate = aggregate_cutover_readiness(
        (
            readiness_from_reconciliation_result(
                make_reconciliation_result("not_comparable", reason="one_side_missing"),
            ),
        )
    )

    assert aggregate.state == "not_ready"
    assert aggregate.reason == "not_comparable_symbols_present"


def test_aggregate_readiness_is_not_ready_when_no_symbols_compared() -> None:
    aggregate = aggregate_cutover_readiness(())

    assert aggregate.state == "not_ready"
    assert aggregate.reason == "no_symbols_compared"
