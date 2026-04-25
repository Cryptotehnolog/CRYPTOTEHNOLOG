"""Final ownership model for Bybit trade-count truth."""

from __future__ import annotations

from dataclasses import dataclass

from .bybit_trade_count_reconciliation import BybitTradeCountReconciliationResult


@dataclass(slots=True, frozen=True)
class BybitTradeCountTruthOwnership:
    """Explicit final ownership contract for trade-count truths."""

    truth_model: str = "ledger_backed_product_truth_with_connector_operational_runtime"
    canonical_trade_truth_owner: str = "bybit_trade_ledger"
    canonical_trade_truth_source: str = "ledger_backed_canonical_trade_count"
    connector_runtime_truth_owner: str = "bybit_connector_runtime"
    connector_runtime_truth_source: str = "trade_truth_store_operational_layer"
    connector_canonical_role: str = "consumer_of_canonical_trade_truth"
    admission_truth_owner: str = "bybit_connector_runtime"
    admission_truth_source: str = "derived_operational_trade_truth"


FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP = BybitTradeCountTruthOwnership()


@dataclass(slots=True, frozen=True)
class BybitProductTradeCountTruth:
    """Resolved product truth for one symbol under the final ownership model."""

    trade_count_24h: int | None
    state: str
    reason: str
    truth_owner: str
    truth_source: str


def resolve_product_trade_count_truth(
    *,
    reconciliation: BybitTradeCountReconciliationResult,
    ownership: BybitTradeCountTruthOwnership = FINAL_BYBIT_TRADE_COUNT_TRUTH_OWNERSHIP,
) -> BybitProductTradeCountTruth:
    """Resolve product-facing trade count from canonical ledger truth only."""

    if (
        reconciliation.ledger_trade_count_24h is not None
        and reconciliation.verdict in {"match", "within_tolerance"}
    ):
        return BybitProductTradeCountTruth(
            trade_count_24h=reconciliation.ledger_trade_count_24h,
            state="ledger_confirmed",
            reason=reconciliation.reason,
            truth_owner=ownership.canonical_trade_truth_owner,
            truth_source=ownership.canonical_trade_truth_source,
        )
    if (
        reconciliation.ledger_trade_count_24h is not None
        and reconciliation.verdict == "not_comparable"
        and reconciliation.reason in {"ledger_historical_coverage_gap", "incomplete_rolling_window"}
    ):
        return BybitProductTradeCountTruth(
            trade_count_24h=reconciliation.ledger_trade_count_24h,
            state="partial_ledger_coverage",
            reason=reconciliation.reason,
            truth_owner=ownership.canonical_trade_truth_owner,
            truth_source="ledger_truth_partial_coverage",
        )
    if reconciliation.verdict == "mismatch":
        return BybitProductTradeCountTruth(
            trade_count_24h=None,
            state="reconciliation_mismatch",
            reason=reconciliation.reason,
            truth_owner=ownership.canonical_trade_truth_owner,
            truth_source="ledger_truth_blocked_by_reconciliation",
        )
    if reconciliation.verdict == "validation_blocked":
        return BybitProductTradeCountTruth(
            trade_count_24h=None,
            state="ledger_unavailable",
            reason=reconciliation.reason,
            truth_owner=ownership.canonical_trade_truth_owner,
            truth_source="ledger_truth_unavailable",
        )
    return BybitProductTradeCountTruth(
        trade_count_24h=None,
        state="pending_validation",
        reason=reconciliation.reason,
        truth_owner=ownership.canonical_trade_truth_owner,
        truth_source="ledger_truth_pending_validation",
    )
