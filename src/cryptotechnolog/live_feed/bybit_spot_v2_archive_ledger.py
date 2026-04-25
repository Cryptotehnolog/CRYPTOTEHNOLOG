"""Separate archive-trade ledger path for Bybit spot v2."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from typing import TYPE_CHECKING

from .bybit_trade_backfill import BybitArchiveTradeFactExtraction
from .bybit_trade_identity import BybitTradeIdentityResult

if TYPE_CHECKING:
    from cryptotechnolog.core.database import DatabaseManager


@dataclass(slots=True, frozen=True)
class BybitSpotV2ArchiveTradeLedgerRecord:
    exchange: str
    contour: str
    normalized_symbol: str
    archive_trade_id: str
    source_trade_identity: str
    canonical_dedup_identity: str
    identity_contract_version: int
    exchange_trade_at: datetime
    side: str
    normalized_price: Decimal
    normalized_size: Decimal
    source_symbol_raw: str | None
    source_metadata: dict[str, str]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class BybitSpotV2ArchiveTradeLedgerWriteResult:
    status: str
    record: BybitSpotV2ArchiveTradeLedgerRecord | None
    reason: str | None = None


class BybitSpotV2ArchiveTradeLedgerRepository:
    """Narrow repository for separate spot v2 archive trade rows."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self._db_manager = db_manager
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()

    async def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        async with self._schema_lock:
            if self._schema_ready:
                return
            async with self._db_manager.connection() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bybit_spot_v2_archive_trade_ledger (
                        exchange_id TEXT NOT NULL,
                        contour TEXT NOT NULL,
                        normalized_symbol TEXT NOT NULL,
                        archive_trade_id TEXT NOT NULL,
                        source_trade_identity TEXT NOT NULL,
                        canonical_dedup_identity TEXT NOT NULL,
                        identity_contract_version INTEGER NOT NULL,
                        exchange_trade_at TIMESTAMPTZ NOT NULL,
                        side TEXT NOT NULL,
                        normalized_price NUMERIC NOT NULL,
                        normalized_size NUMERIC NOT NULL,
                        source_symbol_raw TEXT NULL,
                        source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        PRIMARY KEY (
                            exchange_id,
                            identity_contract_version,
                            canonical_dedup_identity
                        )
                    )
                    """
                )
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_bybit_spot_v2_archive_trade_ledger_symbol_time
                    ON bybit_spot_v2_archive_trade_ledger (
                        normalized_symbol,
                        exchange_trade_at DESC
                    )
                    """
                )
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_bybit_spot_v2_archive_trade_ledger_symbol_time_canonical
                    ON bybit_spot_v2_archive_trade_ledger (
                        normalized_symbol,
                        exchange_trade_at DESC,
                        canonical_dedup_identity
                    )
                    """
                )
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_bybit_spot_v2_archive_trade_ledger_symbol_canonical_time
                    ON bybit_spot_v2_archive_trade_ledger (
                        normalized_symbol,
                        canonical_dedup_identity,
                        exchange_trade_at DESC
                    )
                    """
                )
            self._schema_ready = True

    async def upsert_archive_trade(
        self,
        record: BybitSpotV2ArchiveTradeLedgerRecord,
    ) -> None:
        await self.ensure_schema()
        async with self._db_manager.connection() as conn:
            await conn.execute(
                """
                INSERT INTO bybit_spot_v2_archive_trade_ledger (
                    exchange_id,
                    contour,
                    normalized_symbol,
                    archive_trade_id,
                    source_trade_identity,
                    canonical_dedup_identity,
                    identity_contract_version,
                    exchange_trade_at,
                    side,
                    normalized_price,
                    normalized_size,
                    source_symbol_raw,
                    source_metadata,
                    created_at,
                    updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8,
                    $9, $10, $11, $12, $13::jsonb, $14, $15
                )
                ON CONFLICT (
                    exchange_id,
                    identity_contract_version,
                    canonical_dedup_identity
                ) DO UPDATE SET
                    contour = EXCLUDED.contour,
                    normalized_symbol = EXCLUDED.normalized_symbol,
                    archive_trade_id = EXCLUDED.archive_trade_id,
                    source_trade_identity = EXCLUDED.source_trade_identity,
                    exchange_trade_at = EXCLUDED.exchange_trade_at,
                    side = EXCLUDED.side,
                    normalized_price = EXCLUDED.normalized_price,
                    normalized_size = EXCLUDED.normalized_size,
                    source_symbol_raw = EXCLUDED.source_symbol_raw,
                    source_metadata = EXCLUDED.source_metadata,
                    updated_at = EXCLUDED.updated_at
                """,
                record.exchange,
                record.contour,
                record.normalized_symbol,
                record.archive_trade_id,
                record.source_trade_identity,
                record.canonical_dedup_identity,
                record.identity_contract_version,
                record.exchange_trade_at,
                record.side,
                record.normalized_price,
                record.normalized_size,
                record.source_symbol_raw,
                json.dumps(record.source_metadata, ensure_ascii=False, sort_keys=True),
                record.created_at,
                record.updated_at,
            )

    async def upsert_archive_trades(
        self,
        records: list[BybitSpotV2ArchiveTradeLedgerRecord],
    ) -> None:
        if not records:
            return
        await self.ensure_schema()
        async with self._db_manager.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    CREATE TEMP TABLE tmp_bybit_spot_v2_archive_trade_ledger (
                        exchange_id TEXT NOT NULL,
                        contour TEXT NOT NULL,
                        normalized_symbol TEXT NOT NULL,
                        archive_trade_id TEXT NOT NULL,
                        source_trade_identity TEXT NOT NULL,
                        canonical_dedup_identity TEXT NOT NULL,
                        identity_contract_version INTEGER NOT NULL,
                        exchange_trade_at TIMESTAMPTZ NOT NULL,
                        side TEXT NOT NULL,
                        normalized_price NUMERIC NOT NULL,
                        normalized_size NUMERIC NOT NULL,
                        source_symbol_raw TEXT NULL,
                        source_metadata JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    ) ON COMMIT DROP
                    """,
                )
                await conn.copy_records_to_table(
                    "tmp_bybit_spot_v2_archive_trade_ledger",
                    records=[
                        (
                            record.exchange,
                            record.contour,
                            record.normalized_symbol,
                            record.archive_trade_id,
                            record.source_trade_identity,
                            record.canonical_dedup_identity,
                            record.identity_contract_version,
                            record.exchange_trade_at,
                            record.side,
                            record.normalized_price,
                            record.normalized_size,
                            record.source_symbol_raw,
                            json.dumps(
                                record.source_metadata,
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                            record.created_at,
                            record.updated_at,
                        )
                        for record in records
                    ],
                    columns=[
                        "exchange_id",
                        "contour",
                        "normalized_symbol",
                        "archive_trade_id",
                        "source_trade_identity",
                        "canonical_dedup_identity",
                        "identity_contract_version",
                        "exchange_trade_at",
                        "side",
                        "normalized_price",
                        "normalized_size",
                        "source_symbol_raw",
                        "source_metadata",
                        "created_at",
                        "updated_at",
                    ],
                )
                await conn.execute(
                    """
                    INSERT INTO bybit_spot_v2_archive_trade_ledger (
                        exchange_id,
                        contour,
                        normalized_symbol,
                        archive_trade_id,
                        source_trade_identity,
                        canonical_dedup_identity,
                        identity_contract_version,
                        exchange_trade_at,
                        side,
                        normalized_price,
                        normalized_size,
                        source_symbol_raw,
                        source_metadata,
                        created_at,
                        updated_at
                    )
                    SELECT
                        exchange_id,
                        contour,
                        normalized_symbol,
                        archive_trade_id,
                        source_trade_identity,
                        canonical_dedup_identity,
                        identity_contract_version,
                        exchange_trade_at,
                        side,
                        normalized_price,
                        normalized_size,
                        source_symbol_raw,
                        source_metadata,
                        created_at,
                        updated_at
                    FROM tmp_bybit_spot_v2_archive_trade_ledger
                    ON CONFLICT (
                        exchange_id,
                        identity_contract_version,
                        canonical_dedup_identity
                    ) DO UPDATE SET
                        contour = EXCLUDED.contour,
                        normalized_symbol = EXCLUDED.normalized_symbol,
                        archive_trade_id = EXCLUDED.archive_trade_id,
                        source_trade_identity = EXCLUDED.source_trade_identity,
                        exchange_trade_at = EXCLUDED.exchange_trade_at,
                        side = EXCLUDED.side,
                        normalized_price = EXCLUDED.normalized_price,
                        normalized_size = EXCLUDED.normalized_size,
                        source_symbol_raw = EXCLUDED.source_symbol_raw,
                        source_metadata = EXCLUDED.source_metadata,
                        updated_at = EXCLUDED.updated_at
                    """
                )

    async def count_rows(self, *, normalized_symbol: str | None = None) -> int:
        await self.ensure_schema()
        async with self._db_manager.connection() as conn:
            if normalized_symbol is None:
                value = await conn.fetchval(
                    "SELECT COUNT(*) FROM bybit_spot_v2_archive_trade_ledger"
                )
            else:
                value = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM bybit_spot_v2_archive_trade_ledger
                    WHERE normalized_symbol = $1
                    """,
                    normalized_symbol,
                )
        return int(value or 0)

    async def fetch_latest_trade(
        self,
        *,
        normalized_symbol: str,
    ) -> BybitSpotV2ArchiveTradeLedgerRecord | None:
        return await self._fetch_one(
            normalized_symbol=normalized_symbol,
            order_direction="DESC",
        )

    async def fetch_earliest_trade(
        self,
        *,
        normalized_symbol: str,
    ) -> BybitSpotV2ArchiveTradeLedgerRecord | None:
        return await self._fetch_one(
            normalized_symbol=normalized_symbol,
            order_direction="ASC",
        )

    async def fetch_latest_trade_before(
        self,
        *,
        normalized_symbol: str,
        observed_at: datetime,
    ) -> BybitSpotV2ArchiveTradeLedgerRecord | None:
        normalized_observed_at = observed_at.astimezone(UTC)
        async with self._db_manager.connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    exchange_id,
                    contour,
                    normalized_symbol,
                    archive_trade_id,
                    source_trade_identity,
                    canonical_dedup_identity,
                    identity_contract_version,
                    exchange_trade_at,
                    side,
                    normalized_price,
                    normalized_size,
                    source_symbol_raw,
                    source_metadata,
                    created_at,
                    updated_at
                FROM bybit_spot_v2_archive_trade_ledger
                WHERE normalized_symbol = $1
                  AND exchange_trade_at < $2
                ORDER BY exchange_trade_at DESC, updated_at DESC
                LIMIT 1
                """,
                normalized_symbol,
                normalized_observed_at,
            )
        if row is None:
            return None
        return BybitSpotV2ArchiveTradeLedgerRecord(
            exchange=str(row["exchange_id"]),
            contour=str(row["contour"]),
            normalized_symbol=str(row["normalized_symbol"]),
            archive_trade_id=str(row["archive_trade_id"]),
            source_trade_identity=str(row["source_trade_identity"]),
            canonical_dedup_identity=str(row["canonical_dedup_identity"]),
            identity_contract_version=int(row["identity_contract_version"]),
            exchange_trade_at=row["exchange_trade_at"],
            side=str(row["side"]),
            normalized_price=Decimal(str(row["normalized_price"])),
            normalized_size=Decimal(str(row["normalized_size"])),
            source_symbol_raw=(
                str(row["source_symbol_raw"])
                if row["source_symbol_raw"] is not None
                else None
            ),
            source_metadata=_normalize_source_metadata_payload(row["source_metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def _fetch_one(
        self,
        *,
        normalized_symbol: str,
        order_direction: str,
    ) -> BybitSpotV2ArchiveTradeLedgerRecord | None:
        async with self._db_manager.connection() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT
                    exchange_id,
                    contour,
                    normalized_symbol,
                    archive_trade_id,
                    source_trade_identity,
                    canonical_dedup_identity,
                    identity_contract_version,
                    exchange_trade_at,
                    side,
                    normalized_price,
                    normalized_size,
                    source_symbol_raw,
                    source_metadata,
                    created_at,
                    updated_at
                FROM bybit_spot_v2_archive_trade_ledger
                WHERE normalized_symbol = $1
                ORDER BY exchange_trade_at {order_direction}, updated_at {order_direction}
                LIMIT 1
                """,
                normalized_symbol,
            )
        if row is None:
            return None
        return BybitSpotV2ArchiveTradeLedgerRecord(
            exchange=str(row["exchange_id"]),
            contour=str(row["contour"]),
            normalized_symbol=str(row["normalized_symbol"]),
            archive_trade_id=str(row["archive_trade_id"]),
            source_trade_identity=str(row["source_trade_identity"]),
            canonical_dedup_identity=str(row["canonical_dedup_identity"]),
            identity_contract_version=int(row["identity_contract_version"]),
            exchange_trade_at=row["exchange_trade_at"],
            side=str(row["side"]),
            normalized_price=Decimal(str(row["normalized_price"])),
            normalized_size=Decimal(str(row["normalized_size"])),
            source_symbol_raw=(
                str(row["source_symbol_raw"])
                if row["source_symbol_raw"] is not None
                else None
            ),
            source_metadata=_normalize_source_metadata_payload(row["source_metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def delete_trades_older_than(self, *, cutoff_at: datetime) -> int:
        await self.ensure_schema()
        normalized_cutoff_at = cutoff_at.astimezone(UTC)
        async with self._db_manager.connection() as conn:
            deleted = await conn.fetchval(
                """
                WITH deleted AS (
                    DELETE FROM bybit_spot_v2_archive_trade_ledger
                    WHERE exchange_trade_at < $1
                    RETURNING 1
                )
                SELECT COUNT(*) FROM deleted
                """,
                normalized_cutoff_at,
            )
        return int(deleted or 0)

    async def cleanup_retention(
        self,
        *,
        retention_hours: int = 48,
        reference_at: datetime | None = None,
    ) -> int:
        normalized_reference_at = (reference_at or datetime.now(tz=UTC)).astimezone(UTC)
        cutoff_at = normalized_reference_at - timedelta(hours=int(retention_hours))
        return await self.delete_trades_older_than(cutoff_at=cutoff_at)


def _normalize_source_metadata_payload(value: object) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items()}
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, dict):
            return {str(key): str(item) for key, item in decoded.items()}
    return {}


async def write_bybit_spot_v2_archive_trade_to_ledger(
    *,
    extraction: BybitArchiveTradeFactExtraction,
    identity: BybitTradeIdentityResult,
    repository: BybitSpotV2ArchiveTradeLedgerRepository,
) -> BybitSpotV2ArchiveTradeLedgerWriteResult:
    if extraction.trade_fact is None:
        return BybitSpotV2ArchiveTradeLedgerWriteResult(
            status="skipped",
            record=None,
            reason=extraction.reason or "archive_trade_fact_unavailable",
        )
    if (
        identity.source_trade_identity is None
        or identity.canonical_dedup_identity is None
        or identity.normalized_symbol is None
    ):
        return BybitSpotV2ArchiveTradeLedgerWriteResult(
            status="skipped",
            record=None,
            reason=identity.reason or "archive_identity_incomplete",
        )
    trade_fact = extraction.trade_fact
    if trade_fact.archive_trade_id is None:
        return BybitSpotV2ArchiveTradeLedgerWriteResult(
            status="skipped",
            record=None,
            reason="archive_trade_id_missing",
        )
    now = datetime.now(UTC)
    record = BybitSpotV2ArchiveTradeLedgerRecord(
        exchange="bybit_spot_v2",
        contour=trade_fact.contour,
        normalized_symbol=trade_fact.normalized_symbol,
        archive_trade_id=trade_fact.archive_trade_id,
        source_trade_identity=identity.source_trade_identity,
        canonical_dedup_identity=identity.canonical_dedup_identity,
        identity_contract_version=identity.identity_contract_version,
        exchange_trade_at=trade_fact.exchange_trade_at,
        side=trade_fact.side,
        normalized_price=trade_fact.normalized_price,
        normalized_size=trade_fact.normalized_size,
        source_symbol_raw=trade_fact.source_symbol_raw,
        source_metadata={
            "source": identity.source,
            "identity_verdict": identity.verdict,
            "identity_reason": identity.reason or "",
            "archive_trade_id": trade_fact.archive_trade_id,
            **identity.metadata,
            **trade_fact.raw_fields,
        },
        created_at=now,
        updated_at=now,
    )
    await repository.upsert_archive_trade(record)
    return BybitSpotV2ArchiveTradeLedgerWriteResult(
        status="written",
        record=record,
    )


def build_bybit_spot_v2_archive_trade_ledger_record(
    *,
    extraction: BybitArchiveTradeFactExtraction,
    identity: BybitTradeIdentityResult,
) -> BybitSpotV2ArchiveTradeLedgerRecord | None:
    if extraction.trade_fact is None:
        return None
    if (
        identity.source_trade_identity is None
        or identity.canonical_dedup_identity is None
        or identity.normalized_symbol is None
    ):
        return None
    trade_fact = extraction.trade_fact
    if trade_fact.archive_trade_id is None:
        return None
    now = datetime.now(UTC)
    return BybitSpotV2ArchiveTradeLedgerRecord(
        exchange="bybit_spot_v2",
        contour=trade_fact.contour,
        normalized_symbol=trade_fact.normalized_symbol,
        archive_trade_id=trade_fact.archive_trade_id,
        source_trade_identity=identity.source_trade_identity,
        canonical_dedup_identity=identity.canonical_dedup_identity,
        identity_contract_version=identity.identity_contract_version,
        exchange_trade_at=trade_fact.exchange_trade_at,
        side=trade_fact.side,
        normalized_price=trade_fact.normalized_price,
        normalized_size=trade_fact.normalized_size,
        source_symbol_raw=trade_fact.source_symbol_raw,
        source_metadata={
            "source": identity.source,
            "identity_verdict": identity.verdict,
            "identity_reason": identity.reason or "",
            "archive_trade_id": trade_fact.archive_trade_id,
        },
        created_at=now,
        updated_at=now,
    )


__all__ = [
    "BybitSpotV2ArchiveTradeLedgerRecord",
    "BybitSpotV2ArchiveTradeLedgerRepository",
    "BybitSpotV2ArchiveTradeLedgerWriteResult",
    "write_bybit_spot_v2_archive_trade_to_ledger",
]
