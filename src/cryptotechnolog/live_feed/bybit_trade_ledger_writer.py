"""
Archive trade-ledger write path for canonical Bybit trade facts.

Модуль намеренно ограничен только archive-derived write orchestration
поверх extraction + identity + existing repository foundation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from .bybit_trade_ledger_contracts import BybitTradeLedgerRecord

BybitArchiveLedgerWriteStatus = Literal["written", "skipped"]


@dataclass(slots=True, frozen=True)
class BybitArchiveLedgerWriteResult:
    """Result of archive-derived write path execution."""

    status: BybitArchiveLedgerWriteStatus
    record: BybitTradeLedgerRecord | None
    reason: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


async def write_archive_trade_fact_to_ledger(
    *,
    extraction,
    identity,
    repository,
) -> BybitArchiveLedgerWriteResult:
    if extraction.trade_fact is None:
        return BybitArchiveLedgerWriteResult(
            status="skipped",
            record=None,
            reason=extraction.reason or "archive_trade_fact_unavailable",
            metadata={"extraction_status": extraction.status},
        )
    if identity.verdict == "not_identifiable":
        return BybitArchiveLedgerWriteResult(
            status="skipped",
            record=None,
            reason=identity.reason or "identity_not_identifiable",
            metadata={
                "identity_verdict": identity.verdict,
                "identity_contract_version": str(identity.identity_contract_version),
            },
        )
    trade_fact = extraction.trade_fact
    if (
        identity.source_trade_identity is None
        or identity.canonical_dedup_identity is None
        or identity.normalized_symbol is None
    ):
        return BybitArchiveLedgerWriteResult(
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
        source_symbol_raw=trade_fact.source_symbol_raw,
        source_metadata={
            "identity_verdict": identity.verdict,
            "identity_reason": identity.reason or "",
            "identity_contract_version": str(identity.identity_contract_version),
            "archive_trade_id": trade_fact.archive_trade_id or "",
            "identity_strength": trade_fact.identity_strength,
            "extraction_status": extraction.status,
            **identity.metadata,
            **trade_fact.raw_fields,
        },
        created_at=now,
        updated_at=now,
    )
    await repository.upsert_trade_fact(record)
    return BybitArchiveLedgerWriteResult(
        status="written",
        record=record,
        metadata={
            "identity_verdict": identity.verdict,
            "identity_contract_version": str(identity.identity_contract_version),
        },
    )
