"""Separate live-trade ledger path for Bybit spot v2."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from typing import TYPE_CHECKING

from .bybit_live_trade_fact import BybitLiveTradeFactBuildResult
from .bybit_live_trade_identity import BybitLiveTradeIdentityResult

if TYPE_CHECKING:
    from cryptotechnolog.core.database import DatabaseManager


@dataclass(slots=True, frozen=True)
class BybitSpotV2LiveTradeLedgerRecord:
    exchange: str
    normalized_symbol: str
    live_trade_id: str
    source_trade_identity: str
    canonical_dedup_identity: str
    identity_contract_version: int
    exchange_trade_at: datetime
    side: str
    normalized_price: Decimal
    normalized_size: Decimal
    is_buyer_maker: bool
    source_metadata: dict[str, str]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class BybitSpotV2LiveTradeLedgerWriteResult:
    status: str
    record: BybitSpotV2LiveTradeLedgerRecord | None
    reason: str | None = None


class BybitSpotV2LiveTradeLedgerRepository:
    """Narrow repository for separate spot v2 live-trade ledger rows."""

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
                    CREATE TABLE IF NOT EXISTS bybit_spot_v2_live_trade_ledger (
                        exchange_id TEXT NOT NULL,
                        normalized_symbol TEXT NOT NULL,
                        live_trade_id TEXT NOT NULL,
                        source_trade_identity TEXT NOT NULL,
                        canonical_dedup_identity TEXT NOT NULL,
                        identity_contract_version INTEGER NOT NULL,
                        exchange_trade_at TIMESTAMPTZ NOT NULL,
                        side TEXT NOT NULL,
                        normalized_price NUMERIC NOT NULL,
                        normalized_size NUMERIC NOT NULL,
                        is_buyer_maker BOOLEAN NOT NULL,
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
                    CREATE INDEX IF NOT EXISTS idx_bybit_spot_v2_live_trade_ledger_symbol_time
                    ON bybit_spot_v2_live_trade_ledger (
                        normalized_symbol,
                        exchange_trade_at DESC
                    )
                    """
                )
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_bybit_spot_v2_live_trade_ledger_symbol_time_canonical
                    ON bybit_spot_v2_live_trade_ledger (
                        normalized_symbol,
                        exchange_trade_at DESC,
                        canonical_dedup_identity
                    )
                    """
                )
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_bybit_spot_v2_live_trade_ledger_symbol_canonical_time
                    ON bybit_spot_v2_live_trade_ledger (
                        normalized_symbol,
                        canonical_dedup_identity,
                        exchange_trade_at DESC
                    )
                    """
                )
            self._schema_ready = True

    async def upsert_live_trade(
        self,
        record: BybitSpotV2LiveTradeLedgerRecord,
    ) -> None:
        await self.ensure_schema()
        async with self._db_manager.connection() as conn:
            await conn.execute(
                """
                INSERT INTO bybit_spot_v2_live_trade_ledger (
                    exchange_id,
                    normalized_symbol,
                    live_trade_id,
                    source_trade_identity,
                    canonical_dedup_identity,
                    identity_contract_version,
                    exchange_trade_at,
                    side,
                    normalized_price,
                    normalized_size,
                    is_buyer_maker,
                    source_metadata,
                    created_at,
                    updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7,
                    $8, $9, $10, $11, $12::jsonb, $13, $14
                )
                ON CONFLICT (
                    exchange_id,
                    identity_contract_version,
                    canonical_dedup_identity
                ) DO UPDATE SET
                    normalized_symbol = EXCLUDED.normalized_symbol,
                    live_trade_id = EXCLUDED.live_trade_id,
                    source_trade_identity = EXCLUDED.source_trade_identity,
                    exchange_trade_at = EXCLUDED.exchange_trade_at,
                    side = EXCLUDED.side,
                    normalized_price = EXCLUDED.normalized_price,
                    normalized_size = EXCLUDED.normalized_size,
                    is_buyer_maker = EXCLUDED.is_buyer_maker,
                    source_metadata = EXCLUDED.source_metadata,
                    updated_at = EXCLUDED.updated_at
                """,
                record.exchange,
                record.normalized_symbol,
                record.live_trade_id,
                record.source_trade_identity,
                record.canonical_dedup_identity,
                record.identity_contract_version,
                record.exchange_trade_at,
                record.side,
                record.normalized_price,
                record.normalized_size,
                record.is_buyer_maker,
                json.dumps(record.source_metadata, ensure_ascii=False, sort_keys=True),
                record.created_at,
                record.updated_at,
            )

    async def upsert_live_trades(
        self,
        records: list[BybitSpotV2LiveTradeLedgerRecord],
    ) -> None:
        if not records:
            return
        await self.ensure_schema()
        async with self._db_manager.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    CREATE TEMP TABLE tmp_bybit_spot_v2_live_trade_ledger (
                        exchange_id TEXT NOT NULL,
                        normalized_symbol TEXT NOT NULL,
                        live_trade_id TEXT NOT NULL,
                        source_trade_identity TEXT NOT NULL,
                        canonical_dedup_identity TEXT NOT NULL,
                        identity_contract_version INTEGER NOT NULL,
                        exchange_trade_at TIMESTAMPTZ NOT NULL,
                        side TEXT NOT NULL,
                        normalized_price NUMERIC NOT NULL,
                        normalized_size NUMERIC NOT NULL,
                        is_buyer_maker BOOLEAN NOT NULL,
                        source_metadata JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    ) ON COMMIT DROP
                    """
                )
                await conn.copy_records_to_table(
                    "tmp_bybit_spot_v2_live_trade_ledger",
                    records=[
                        (
                            record.exchange,
                            record.normalized_symbol,
                            record.live_trade_id,
                            record.source_trade_identity,
                            record.canonical_dedup_identity,
                            record.identity_contract_version,
                            record.exchange_trade_at,
                            record.side,
                            record.normalized_price,
                            record.normalized_size,
                            record.is_buyer_maker,
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
                        "normalized_symbol",
                        "live_trade_id",
                        "source_trade_identity",
                        "canonical_dedup_identity",
                        "identity_contract_version",
                        "exchange_trade_at",
                        "side",
                        "normalized_price",
                        "normalized_size",
                        "is_buyer_maker",
                        "source_metadata",
                        "created_at",
                        "updated_at",
                    ],
                )
                await conn.execute(
                    """
                    INSERT INTO bybit_spot_v2_live_trade_ledger (
                        exchange_id,
                        normalized_symbol,
                        live_trade_id,
                        source_trade_identity,
                        canonical_dedup_identity,
                        identity_contract_version,
                        exchange_trade_at,
                        side,
                        normalized_price,
                        normalized_size,
                        is_buyer_maker,
                        source_metadata,
                        created_at,
                        updated_at
                    )
                    SELECT
                        exchange_id,
                        normalized_symbol,
                        live_trade_id,
                        source_trade_identity,
                        canonical_dedup_identity,
                        identity_contract_version,
                        exchange_trade_at,
                        side,
                        normalized_price,
                        normalized_size,
                        is_buyer_maker,
                        source_metadata,
                        created_at,
                        updated_at
                    FROM tmp_bybit_spot_v2_live_trade_ledger
                    ON CONFLICT (
                        exchange_id,
                        identity_contract_version,
                        canonical_dedup_identity
                    ) DO UPDATE SET
                        normalized_symbol = EXCLUDED.normalized_symbol,
                        live_trade_id = EXCLUDED.live_trade_id,
                        source_trade_identity = EXCLUDED.source_trade_identity,
                        exchange_trade_at = EXCLUDED.exchange_trade_at,
                        side = EXCLUDED.side,
                        normalized_price = EXCLUDED.normalized_price,
                        normalized_size = EXCLUDED.normalized_size,
                        is_buyer_maker = EXCLUDED.is_buyer_maker,
                        source_metadata = EXCLUDED.source_metadata,
                        updated_at = EXCLUDED.updated_at
                    """
                )

    async def count_rows(self, *, normalized_symbol: str | None = None) -> int:
        await self.ensure_schema()
        async with self._db_manager.connection() as conn:
            if normalized_symbol is None:
                value = await conn.fetchval(
                    "SELECT COUNT(*) FROM bybit_spot_v2_live_trade_ledger"
                )
            else:
                value = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM bybit_spot_v2_live_trade_ledger
                    WHERE normalized_symbol = $1
                    """,
                    normalized_symbol,
                )
        return int(value or 0)

    async def fetch_latest_trade(
        self,
        *,
        normalized_symbol: str,
    ) -> BybitSpotV2LiveTradeLedgerRecord | None:
        async with self._db_manager.connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    exchange_id,
                    normalized_symbol,
                    live_trade_id,
                    source_trade_identity,
                    canonical_dedup_identity,
                    identity_contract_version,
                    exchange_trade_at,
                    side,
                    normalized_price,
                    normalized_size,
                    is_buyer_maker,
                    source_metadata,
                    created_at,
                    updated_at
                FROM bybit_spot_v2_live_trade_ledger
                WHERE normalized_symbol = $1
                ORDER BY exchange_trade_at DESC, updated_at DESC
                LIMIT 1
                """,
                normalized_symbol,
            )
        if row is None:
            return None
        return BybitSpotV2LiveTradeLedgerRecord(
            exchange=str(row["exchange_id"]),
            normalized_symbol=str(row["normalized_symbol"]),
            live_trade_id=str(row["live_trade_id"]),
            source_trade_identity=str(row["source_trade_identity"]),
            canonical_dedup_identity=str(row["canonical_dedup_identity"]),
            identity_contract_version=int(row["identity_contract_version"]),
            exchange_trade_at=row["exchange_trade_at"],
            side=str(row["side"]),
            normalized_price=Decimal(str(row["normalized_price"])),
            normalized_size=Decimal(str(row["normalized_size"])),
            is_buyer_maker=bool(row["is_buyer_maker"]),
            source_metadata=_normalize_source_metadata_payload(
                row["source_metadata"]
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def fetch_latest_trade_before(
        self,
        *,
        normalized_symbol: str,
        observed_at: datetime,
    ) -> BybitSpotV2LiveTradeLedgerRecord | None:
        normalized_observed_at = observed_at.astimezone(UTC)
        async with self._db_manager.connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    exchange_id,
                    normalized_symbol,
                    live_trade_id,
                    source_trade_identity,
                    canonical_dedup_identity,
                    identity_contract_version,
                    exchange_trade_at,
                    side,
                    normalized_price,
                    normalized_size,
                    is_buyer_maker,
                    source_metadata,
                    created_at,
                    updated_at
                FROM bybit_spot_v2_live_trade_ledger
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
        return BybitSpotV2LiveTradeLedgerRecord(
            exchange=str(row["exchange_id"]),
            normalized_symbol=str(row["normalized_symbol"]),
            live_trade_id=str(row["live_trade_id"]),
            source_trade_identity=str(row["source_trade_identity"]),
            canonical_dedup_identity=str(row["canonical_dedup_identity"]),
            identity_contract_version=int(row["identity_contract_version"]),
            exchange_trade_at=row["exchange_trade_at"],
            side=str(row["side"]),
            normalized_price=Decimal(str(row["normalized_price"])),
            normalized_size=Decimal(str(row["normalized_size"])),
            is_buyer_maker=bool(row["is_buyer_maker"]),
            source_metadata=_normalize_source_metadata_payload(
                row["source_metadata"]
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def fetch_earliest_trade_after(
        self,
        *,
        normalized_symbol: str,
        trade_at: datetime,
        observed_at: datetime,
    ) -> BybitSpotV2LiveTradeLedgerRecord | None:
        normalized_trade_at = trade_at.astimezone(UTC)
        normalized_observed_at = observed_at.astimezone(UTC)
        async with self._db_manager.connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    exchange_id,
                    normalized_symbol,
                    live_trade_id,
                    source_trade_identity,
                    canonical_dedup_identity,
                    identity_contract_version,
                    exchange_trade_at,
                    side,
                    normalized_price,
                    normalized_size,
                    is_buyer_maker,
                    source_metadata,
                    created_at,
                    updated_at
                FROM bybit_spot_v2_live_trade_ledger
                WHERE normalized_symbol = $1
                  AND exchange_trade_at > $2
                  AND exchange_trade_at < $3
                ORDER BY exchange_trade_at ASC, updated_at ASC
                LIMIT 1
                """,
                normalized_symbol,
                normalized_trade_at,
                normalized_observed_at,
            )
        if row is None:
            return None
        return BybitSpotV2LiveTradeLedgerRecord(
            exchange=str(row["exchange_id"]),
            normalized_symbol=str(row["normalized_symbol"]),
            live_trade_id=str(row["live_trade_id"]),
            source_trade_identity=str(row["source_trade_identity"]),
            canonical_dedup_identity=str(row["canonical_dedup_identity"]),
            identity_contract_version=int(row["identity_contract_version"]),
            exchange_trade_at=row["exchange_trade_at"],
            side=str(row["side"]),
            normalized_price=Decimal(str(row["normalized_price"])),
            normalized_size=Decimal(str(row["normalized_size"])),
            is_buyer_maker=bool(row["is_buyer_maker"]),
            source_metadata=_normalize_source_metadata_payload(
                row["source_metadata"]
            ),
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
                    DELETE FROM bybit_spot_v2_live_trade_ledger
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
    return {}


async def write_bybit_spot_v2_live_trade_to_ledger(
    *,
    fact_result: BybitLiveTradeFactBuildResult,
    identity: BybitLiveTradeIdentityResult,
    repository: BybitSpotV2LiveTradeLedgerRepository,
) -> BybitSpotV2LiveTradeLedgerWriteResult:
    if fact_result.trade_fact is None:
        return BybitSpotV2LiveTradeLedgerWriteResult(
            status="skipped",
            record=None,
            reason=fact_result.reason or "live_trade_fact_unavailable",
        )
    if (
        identity.verdict != "exact_candidate"
        or identity.source_trade_identity is None
        or identity.canonical_dedup_identity is None
    ):
        return BybitSpotV2LiveTradeLedgerWriteResult(
            status="skipped",
            record=None,
            reason=identity.reason or "identity_not_identifiable",
        )
    trade_fact = fact_result.trade_fact
    now = datetime.now(UTC)
    record = BybitSpotV2LiveTradeLedgerRecord(
        exchange="bybit_spot_v2",
        normalized_symbol=trade_fact.normalized_symbol,
        live_trade_id=trade_fact.live_trade_id,
        source_trade_identity=identity.source_trade_identity,
        canonical_dedup_identity=identity.canonical_dedup_identity,
        identity_contract_version=identity.identity_contract_version,
        exchange_trade_at=trade_fact.exchange_trade_at,
        side=trade_fact.side,
        normalized_price=trade_fact.normalized_price,
        normalized_size=trade_fact.normalized_size,
        is_buyer_maker=trade_fact.is_buyer_maker,
        source_metadata={
            "source": identity.source,
            "identity_verdict": identity.verdict,
            "identity_reason": identity.reason or "",
            "live_trade_id": trade_fact.live_trade_id,
            **identity.metadata,
            **trade_fact.raw_fields,
        },
        created_at=now,
        updated_at=now,
    )
    await repository.upsert_live_trade(record)
    return BybitSpotV2LiveTradeLedgerWriteResult(
        status="written",
        record=record,
    )


__all__ = [
    "BybitSpotV2LiveTradeLedgerRecord",
    "BybitSpotV2LiveTradeLedgerRepository",
    "BybitSpotV2LiveTradeLedgerWriteResult",
    "write_bybit_spot_v2_live_trade_to_ledger",
]
