from __future__ import annotations

import pytest

from cryptotechnolog.live_feed.bybit_trade_count_reconciliation import (
    BybitTradeCountReconciliationPolicy,
    reconcile_trade_count_truths,
)


def test_returns_match_when_counts_equal() -> None:
    result = reconcile_trade_count_truths(
        bucket_trade_count_24h=10,
        ledger_trade_count_24h=10,
        ledger_trade_count_available=True,
    )

    assert result.verdict == "match"
    assert result.absolute_diff == 0
    assert result.reason == "counts_equal"


def test_returns_within_tolerance_only_when_policy_explicitly_allows_it() -> None:
    result = reconcile_trade_count_truths(
        bucket_trade_count_24h=10,
        ledger_trade_count_24h=11,
        ledger_trade_count_available=True,
        policy=BybitTradeCountReconciliationPolicy(absolute_tolerance=1),
    )

    assert result.verdict == "within_tolerance"
    assert result.absolute_diff == 1
    assert result.tolerance == 1


def test_zero_tolerance_baseline_returns_mismatch_for_non_equal_counts() -> None:
    result = reconcile_trade_count_truths(
        bucket_trade_count_24h=10,
        ledger_trade_count_24h=11,
        ledger_trade_count_available=True,
    )

    assert result.verdict == "mismatch"
    assert result.absolute_diff == 1
    assert result.tolerance == 0


def test_returns_not_comparable_when_one_side_missing() -> None:
    result = reconcile_trade_count_truths(
        bucket_trade_count_24h=None,
        ledger_trade_count_24h=11,
        ledger_trade_count_available=True,
    )

    assert result.verdict == "not_comparable"
    assert result.absolute_diff is None
    assert result.reason == "one_side_missing"


def test_returns_validation_blocked_when_ledger_path_unavailable() -> None:
    result = reconcile_trade_count_truths(
        bucket_trade_count_24h=10,
        ledger_trade_count_24h=None,
        ledger_trade_count_available=False,
    )

    assert result.verdict == "validation_blocked"
    assert result.absolute_diff is None
    assert result.reason == "ledger_path_unavailable"


def test_policy_rejects_negative_tolerance() -> None:
    with pytest.raises(ValueError, match="absolute_tolerance"):
        BybitTradeCountReconciliationPolicy(absolute_tolerance=-1)


def test_returns_not_comparable_for_historical_coverage_gap() -> None:
    result = reconcile_trade_count_truths(
        bucket_trade_count_24h=10,
        ledger_trade_count_24h=3,
        ledger_trade_count_available=True,
        ledger_historical_coverage_gap=True,
    )

    assert result.verdict == "not_comparable"
    assert result.absolute_diff is None
    assert result.reason == "ledger_historical_coverage_gap"
