"""
Live-side ledger write path for canonical Bybit trade facts.

Модуль intentionally ограничен только foundation write orchestration
без runtime/bootstrap wiring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from .bybit_trade_ledger_contracts import BybitTradeLedgerRecord

BybitLiveLedgerWriteStatus = Literal["written", "skipped"]


@dataclass(slots=True, frozen=True)
class BybitLiveLedgerWriteResult:
    """Result of live-side ledger write execution."""

    status: BybitLiveLedgerWriteStatus
    record: BybitTradeLedgerRecord | None
    reason: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


async def write_live_trade_fact_to_ledger(
    *,
    fact_result,
    identity,
    repository,
) -> BybitLiveLedgerWriteResult:
    if fact_result.trade_fact is None:
        return BybitLiveLedgerWriteResult(
            status="skipped",
            record=None,
            reason=fact_result.reason or "live_trade_fact_unavailable",
            metadata={"build_status": fact_result.status},
        )
    if identity.verdict == "not_identifiable":
        return BybitLiveLedgerWriteResult(
            status="skipped",
            record=None,
            reason=identity.reason or "identity_not_identifiable",
            metadata={
                "identity_verdict": identity.verdict,
                "identity_contract_version": str(identity.identity_contract_version),
            },
        )
    trade_fact = fact_result.trade_fact
    if (
        identity.source_trade_identity is None
        or identity.canonical_dedup_identity is None
        or identity.normalized_symbol is None
    ):
        return BybitLiveLedgerWriteResult(
            status="skipped",
            record=None,
            reason="identity_result_incomplete",
            metadata={
                "identity_verdict": identity.verdict,
                "identity_contract_version": str(identity.identity_contract_version),
            },
        )
    now = datetime.now(UTC)
    record = BybitTradeLedgerRecord(
        exchange="bybit",
        contour=trade_fact.contour,
        normalized_symbol=trade_fact.normalized_symbol,
        source=identity.source,
        source_trade_identity=identity.source_trade_identity,
        canonical_dedup_identity=identity.canonical_dedup_identity,
        identity_contract_version=identity.identity_contract_version,
        exchange_trade_at=trade_fact.exchange_trade_at,
        side=trade_fact.side,
        normalized_price=trade_fact.normalized_price,
        normalized_size=trade_fact.normalized_size,
        source_symbol_raw=trade_fact.normalized_symbol.replace("/", ""),
        source_metadata={
            "identity_verdict": identity.verdict,
            "identity_reason": identity.reason or "",
            "identity_contract_version": str(identity.identity_contract_version),
            "live_trade_id": trade_fact.live_trade_id,
            "identity_strength": trade_fact.identity_strength,
            "build_status": fact_result.status,
            **identity.metadata,
            **trade_fact.raw_fields,
        },
        created_at=now,
        updated_at=now,
    )
    await repository.upsert_trade_fact(record)
    return BybitLiveLedgerWriteResult(
        status="written",
        record=record,
        metadata={
            "identity_verdict": identity.verdict,
            "identity_contract_version": str(identity.identity_contract_version),
        },
    )
