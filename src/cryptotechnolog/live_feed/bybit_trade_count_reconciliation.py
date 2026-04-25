"""
Read-only comparison policy between bucket truth and ledger truth.

Модуль intentionally ограничен reconciliation groundwork без
product truth switch, cutover logic или runtime admission semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BybitTradeCountReconciliationVerdict = Literal[
    "match",
    "within_tolerance",
    "mismatch",
    "not_comparable",
    "validation_blocked",
]


@dataclass(slots=True, frozen=True)
class BybitTradeCountReconciliationPolicy:
    """Read-only comparison policy for bucket vs ledger trade count."""

    absolute_tolerance: int = 0

    def __post_init__(self) -> None:
        if self.absolute_tolerance < 0:
            raise ValueError("absolute_tolerance не может быть отрицательным")


@dataclass(slots=True, frozen=True)
class BybitTradeCountReconciliationResult:
    """Machine-readable reconciliation result for one symbol snapshot."""

    verdict: BybitTradeCountReconciliationVerdict
    bucket_trade_count_24h: int | None
    ledger_trade_count_24h: int | None
    absolute_diff: int | None
    tolerance: int
    reason: str


def reconcile_trade_count_truths(
    *,
    bucket_trade_count_24h: int | None,
    ledger_trade_count_24h: int | None,
    ledger_trade_count_available: bool,
    ledger_trade_count_reason: str | None = None,
    ledger_trade_count_stale: bool = False,
    ledger_historical_coverage_gap: bool = False,
    ledger_window_completeness_proven: bool = True,
    policy: BybitTradeCountReconciliationPolicy | None = None,
) -> BybitTradeCountReconciliationResult:
    resolved_policy = policy or BybitTradeCountReconciliationPolicy()
    if not ledger_trade_count_available:
        return BybitTradeCountReconciliationResult(
            verdict="validation_blocked",
            bucket_trade_count_24h=bucket_trade_count_24h,
            ledger_trade_count_24h=ledger_trade_count_24h,
            absolute_diff=None,
            tolerance=resolved_policy.absolute_tolerance,
            reason=ledger_trade_count_reason or "ledger_path_unavailable",
        )
    if ledger_trade_count_stale:
        return BybitTradeCountReconciliationResult(
            verdict="not_comparable",
            bucket_trade_count_24h=bucket_trade_count_24h,
            ledger_trade_count_24h=ledger_trade_count_24h,
            absolute_diff=None,
            tolerance=resolved_policy.absolute_tolerance,
            reason=ledger_trade_count_reason or "ledger_snapshot_stale",
        )
    if ledger_historical_coverage_gap:
        return BybitTradeCountReconciliationResult(
            verdict="not_comparable",
            bucket_trade_count_24h=bucket_trade_count_24h,
            ledger_trade_count_24h=ledger_trade_count_24h,
            absolute_diff=None,
            tolerance=resolved_policy.absolute_tolerance,
            reason="ledger_historical_coverage_gap",
        )
    if ledger_trade_count_24h is not None and not ledger_window_completeness_proven:
        return BybitTradeCountReconciliationResult(
            verdict="not_comparable",
            bucket_trade_count_24h=bucket_trade_count_24h,
            ledger_trade_count_24h=ledger_trade_count_24h,
            absolute_diff=None,
            tolerance=resolved_policy.absolute_tolerance,
            reason="incomplete_rolling_window",
        )
    if bucket_trade_count_24h is None or ledger_trade_count_24h is None:
        return BybitTradeCountReconciliationResult(
            verdict="not_comparable",
            bucket_trade_count_24h=bucket_trade_count_24h,
            ledger_trade_count_24h=ledger_trade_count_24h,
            absolute_diff=None,
            tolerance=resolved_policy.absolute_tolerance,
            reason=ledger_trade_count_reason or "one_side_missing",
        )
    absolute_diff = abs(bucket_trade_count_24h - ledger_trade_count_24h)
    if absolute_diff == 0:
        return BybitTradeCountReconciliationResult(
            verdict="match",
            bucket_trade_count_24h=bucket_trade_count_24h,
            ledger_trade_count_24h=ledger_trade_count_24h,
            absolute_diff=0,
            tolerance=resolved_policy.absolute_tolerance,
            reason="counts_equal",
        )
    if 0 < absolute_diff <= resolved_policy.absolute_tolerance:
        return BybitTradeCountReconciliationResult(
            verdict="within_tolerance",
            bucket_trade_count_24h=bucket_trade_count_24h,
            ledger_trade_count_24h=ledger_trade_count_24h,
            absolute_diff=absolute_diff,
            tolerance=resolved_policy.absolute_tolerance,
            reason="difference_within_absolute_tolerance",
        )
    return BybitTradeCountReconciliationResult(
        verdict="mismatch",
        bucket_trade_count_24h=bucket_trade_count_24h,
        ledger_trade_count_24h=ledger_trade_count_24h,
        absolute_diff=absolute_diff,
        tolerance=resolved_policy.absolute_tolerance,
        reason="difference_exceeds_absolute_tolerance",
    )
