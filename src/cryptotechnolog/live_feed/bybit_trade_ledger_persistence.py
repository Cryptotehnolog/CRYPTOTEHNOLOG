"""
PostgreSQL repository для foundation-слоя canonical Bybit trade ledger.

Модуль намеренно ограничен только storage foundation без wiring
в текущий Bybit runtime contour.
"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from typing import TYPE_CHECKING, Any, cast

from .bybit_trade_ledger_contracts import (
    BybitTradeLedgerConvergenceResult,
    BybitTradeLedgerMaterializationPrefetch,
    BybitTradeLedgerRecord,
    IBybitTradeLedgerRepository,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    import asyncpg

    from .bybit_trade_overlap import BybitTradeOverlapResult


class BybitTradeLedgerPersistenceError(Exception):
    """Базовая ошибка persistence-слоя canonical Bybit trade ledger."""

    def __init__(self, operation: str, reason: str) -> None:
        self.operation = operation
        self.reason = reason
        super().__init__(f"Ошибка {operation}: {reason}")


class BybitTradeLedgerRepository(IBybitTradeLedgerRepository):
    """Узкий asyncpg repository для foundation-слоя canonical Bybit trade ledger."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def upsert_trade_fact(self, record: BybitTradeLedgerRecord) -> None:
        query = """
            INSERT INTO bybit_trade_ledger (
                exchange_id,
                contour,
                normalized_symbol,
                source,
                source_trade_identity,
                canonical_dedup_identity,
                identity_contract_version,
                exchange_trade_at,
                side,
                normalized_price,
                normalized_size,
                source_symbol_raw,
                source_metadata,
                provenance_state,
                provenance_metadata,
                created_at,
                updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8,
                $9, $10, $11, $12, $13, $14, $15, $16, $17
            )
            ON CONFLICT (
                exchange_id,
                contour,
                identity_contract_version,
                canonical_dedup_identity
            ) DO UPDATE SET
                normalized_symbol = EXCLUDED.normalized_symbol,
                source = EXCLUDED.source,
                source_trade_identity = EXCLUDED.source_trade_identity,
                exchange_trade_at = EXCLUDED.exchange_trade_at,
                side = EXCLUDED.side,
                normalized_price = EXCLUDED.normalized_price,
                normalized_size = EXCLUDED.normalized_size,
                source_symbol_raw = EXCLUDED.source_symbol_raw,
                source_metadata = EXCLUDED.source_metadata,
                provenance_state = EXCLUDED.provenance_state,
                provenance_metadata = EXCLUDED.provenance_metadata,
                updated_at = EXCLUDED.updated_at
        """
        await self._execute(
            "upsert_trade_fact",
            query,
            record.exchange,
            record.contour,
            record.normalized_symbol,
            record.source,
            record.source_trade_identity,
            record.canonical_dedup_identity,
            record.identity_contract_version,
            record.exchange_trade_at,
            record.side,
            record.normalized_price,
            record.normalized_size,
            record.source_symbol_raw,
            json.dumps(record.source_metadata, ensure_ascii=False, sort_keys=True),
            record.provenance_state,
            json.dumps(record.provenance_metadata, ensure_ascii=False, sort_keys=True),
            record.created_at,
            record.updated_at,
        )

    async def converge_trade_fact_pair(
        self,
        *,
        archive_record: BybitTradeLedgerRecord,
        live_record: BybitTradeLedgerRecord,
        overlap_result: BybitTradeOverlapResult,
    ) -> BybitTradeLedgerConvergenceResult:
        if overlap_result.verdict not in {"exact_match_candidate", "fallback_match_candidate"}:
            await self.upsert_trade_fact(archive_record)
            await self.upsert_trade_fact(live_record)
            stored_archive = await self.get_trade_fact(
                exchange=archive_record.exchange,
                contour=archive_record.contour,
                identity_contract_version=archive_record.identity_contract_version,
                canonical_dedup_identity=archive_record.canonical_dedup_identity,
            )
            stored_live = await self.get_trade_fact(
                exchange=live_record.exchange,
                contour=live_record.contour,
                identity_contract_version=live_record.identity_contract_version,
                canonical_dedup_identity=live_record.canonical_dedup_identity,
            )
            stored_records = tuple(
                record
                for record in (stored_archive, stored_live)
                if record is not None
            )
            return BybitTradeLedgerConvergenceResult(
                status="stored_separately",
                stored_records=stored_records,
                overlap_verdict=overlap_result.verdict,
            )

        archive_existing = await self.get_trade_fact(
            exchange=archive_record.exchange,
            contour=archive_record.contour,
            identity_contract_version=archive_record.identity_contract_version,
            canonical_dedup_identity=archive_record.canonical_dedup_identity,
        )
        live_existing = await self.get_trade_fact(
            exchange=live_record.exchange,
            contour=live_record.contour,
            identity_contract_version=live_record.identity_contract_version,
            canonical_dedup_identity=live_record.canonical_dedup_identity,
        )
        anchor = self._select_merge_anchor(
            archive_existing=archive_existing,
            live_existing=live_existing,
            archive_record=archive_record,
            live_record=live_record,
        )
        merged_record = self._build_merged_record(
            anchor=anchor,
            archive_record=archive_record,
            live_record=live_record,
            overlap_result=overlap_result,
        )
        await self.upsert_trade_fact(merged_record)
        for source_record in (archive_record, live_record):
            if source_record.canonical_dedup_identity == merged_record.canonical_dedup_identity:
                continue
            await self._delete_trade_fact(
                exchange=source_record.exchange,
                contour=source_record.contour,
                identity_contract_version=source_record.identity_contract_version,
                canonical_dedup_identity=source_record.canonical_dedup_identity,
            )
        stored_record = await self.get_trade_fact(
            exchange=merged_record.exchange,
            contour=merged_record.contour,
            identity_contract_version=merged_record.identity_contract_version,
            canonical_dedup_identity=merged_record.canonical_dedup_identity,
        )
        return BybitTradeLedgerConvergenceResult(
            status="merged",
            stored_records=((stored_record,) if stored_record is not None else ()),
            overlap_verdict=overlap_result.verdict,
        )

    async def get_trade_fact(
        self,
        *,
        exchange: str,
        contour: str,
        identity_contract_version: int,
        canonical_dedup_identity: str,
    ) -> BybitTradeLedgerRecord | None:
        query = """
            SELECT
                exchange_id,
                contour,
                normalized_symbol,
                source,
                source_trade_identity,
                canonical_dedup_identity,
                identity_contract_version,
                exchange_trade_at,
                side,
                normalized_price,
                normalized_size,
                source_symbol_raw,
                source_metadata,
                provenance_state,
                provenance_metadata,
                created_at,
                updated_at
            FROM bybit_trade_ledger
            WHERE exchange_id = $1
              AND contour = $2
              AND identity_contract_version = $3
              AND canonical_dedup_identity = $4
        """
        row = await self._fetchrow(
            "get_trade_fact",
            query,
            exchange,
            contour,
            identity_contract_version,
            canonical_dedup_identity,
        )
        return None if row is None else self._row_to_record(row)

    async def delete_trade_fact(
        self,
        *,
        exchange: str,
        contour: str,
        identity_contract_version: int,
        canonical_dedup_identity: str,
    ) -> None:
        await self._delete_trade_fact(
            exchange=exchange,
            contour=contour,
            identity_contract_version=identity_contract_version,
            canonical_dedup_identity=canonical_dedup_identity,
        )

    async def list_trade_facts(
        self,
        *,
        exchange: str,
        contour: str,
        normalized_symbol: str,
        window_started_at: datetime,
        window_ended_at: datetime,
        limit: int | None = None,
    ) -> tuple[BybitTradeLedgerRecord, ...]:
        query = """
            SELECT
                exchange_id,
                contour,
                normalized_symbol,
                source,
                source_trade_identity,
                canonical_dedup_identity,
                identity_contract_version,
                exchange_trade_at,
                side,
                normalized_price,
                normalized_size,
                source_symbol_raw,
                source_metadata,
                provenance_state,
                provenance_metadata,
                created_at,
                updated_at
            FROM bybit_trade_ledger
            WHERE exchange_id = $1
              AND contour = $2
              AND normalized_symbol = $3
              AND exchange_trade_at >= $4
              AND exchange_trade_at <= $5
            ORDER BY exchange_trade_at ASC, canonical_dedup_identity ASC
        """
        args: list[object] = [
            exchange,
            contour,
            normalized_symbol,
            window_started_at,
            window_ended_at,
        ]
        if limit is not None:
            query += "\nLIMIT $6"
            args.append(limit)
        rows = await self._fetch(
            "list_trade_facts",
            query,
            *args,
        )
        return tuple(self._row_to_record(row) for row in rows)

    async def prefetch_materialization_window(
        self,
        *,
        exchange: str,
        contour: str,
        normalized_symbol: str,
        window_started_at: datetime,
        window_ended_at: datetime,
    ) -> BybitTradeLedgerMaterializationPrefetch:
        if contour == "spot":
            return BybitTradeLedgerMaterializationPrefetch(
                archive_source_identities=(),
                live_rows=(),
            )
        archive_identities_query = """
            SELECT
                CASE
                    WHEN source = 'bybit_public_archive' THEN source_trade_identity
                    ELSE provenance_metadata -> 'archive' ->> 'source_trade_identity'
                END
                    AS archive_source_identity
            FROM bybit_trade_ledger
            WHERE exchange_id = $1
              AND contour = $2
              AND normalized_symbol = $3
              AND exchange_trade_at >= $4
              AND exchange_trade_at <= $5
              AND (
                    source = 'bybit_public_archive'
                    OR provenance_state = 'live_and_archive'
                  )
        """
        live_rows_query = """
            SELECT
                exchange_id,
                contour,
                normalized_symbol,
                source,
                source_trade_identity,
                canonical_dedup_identity,
                identity_contract_version,
                exchange_trade_at,
                side,
                normalized_price,
                normalized_size,
                source_metadata
            FROM bybit_trade_ledger
            WHERE exchange_id = $1
              AND contour = $2
              AND normalized_symbol = $3
              AND exchange_trade_at >= $4
              AND exchange_trade_at <= $5
              AND source = 'live_public_trade'
            ORDER BY exchange_trade_at ASC, canonical_dedup_identity ASC
        """
        archive_identity_rows = await self._fetch(
            "prefetch_materialization_archive_identities",
            archive_identities_query,
            exchange,
            contour,
            normalized_symbol,
            window_started_at,
            window_ended_at,
        )
        if contour == "spot":
            return BybitTradeLedgerMaterializationPrefetch(
                archive_source_identities=tuple(
                    sorted(
                        self._archive_source_identities_from_scalar_rows(
                            archive_identity_rows,
                            column_name="archive_source_identity",
                        )
                    )
                ),
                live_rows=(),
            )
        live_rows = await self._fetch(
            "prefetch_materialization_live_rows",
            live_rows_query,
            exchange,
            contour,
            normalized_symbol,
            window_started_at,
            window_ended_at,
        )
        return BybitTradeLedgerMaterializationPrefetch(
            archive_source_identities=tuple(
                sorted(
                    self._archive_source_identities_from_scalar_rows(
                        archive_identity_rows,
                        column_name="archive_source_identity",
                    )
                )
            ),
            live_rows=tuple(self._row_to_live_prefetch_record(row) for row in live_rows),
        )

    async def _execute(self, operation: str, query: str, *args: object) -> None:
        try:
            async with self._pool.acquire() as connection:
                await connection.execute(query, *args)
        except Exception as exc:  # pragma: no cover
            raise BybitTradeLedgerPersistenceError(operation, str(exc)) from exc

    async def _fetchrow(
        self,
        operation: str,
        query: str,
        *args: object,
    ) -> dict[str, object] | asyncpg.Record | None:
        try:
            async with self._pool.acquire() as connection:
                return await connection.fetchrow(query, *args)
        except Exception as exc:  # pragma: no cover
            raise BybitTradeLedgerPersistenceError(operation, str(exc)) from exc

    async def _fetch(
        self,
        operation: str,
        query: str,
        *args: object,
    ) -> Sequence[dict[str, object] | asyncpg.Record]:
        try:
            async with self._pool.acquire() as connection:
                return await connection.fetch(query, *args)
        except Exception as exc:  # pragma: no cover
            raise BybitTradeLedgerPersistenceError(operation, str(exc)) from exc

    async def _delete_trade_fact(
        self,
        *,
        exchange: str,
        contour: str,
        identity_contract_version: int,
        canonical_dedup_identity: str,
    ) -> None:
        query = """
            DELETE FROM bybit_trade_ledger
            WHERE exchange_id = $1
              AND contour = $2
              AND identity_contract_version = $3
              AND canonical_dedup_identity = $4
        """
        await self._execute(
            "delete_trade_fact",
            query,
            exchange,
            contour,
            identity_contract_version,
            canonical_dedup_identity,
        )

    def _select_merge_anchor(
        self,
        *,
        archive_existing: BybitTradeLedgerRecord | None,
        live_existing: BybitTradeLedgerRecord | None,
        archive_record: BybitTradeLedgerRecord,
        live_record: BybitTradeLedgerRecord,
    ) -> BybitTradeLedgerRecord:
        for candidate in (archive_existing, live_existing):
            if candidate is not None and candidate.provenance_state == "live_and_archive":
                return candidate
        if archive_existing is not None:
            return archive_existing
        if live_existing is not None:
            return live_existing
        return archive_record

    def _build_merged_record(
        self,
        *,
        anchor: BybitTradeLedgerRecord,
        archive_record: BybitTradeLedgerRecord,
        live_record: BybitTradeLedgerRecord,
        overlap_result: BybitTradeOverlapResult,
    ) -> BybitTradeLedgerRecord:
        merged_provenance = dict(anchor.provenance_metadata)
        merged_provenance.update(archive_record.provenance_metadata)
        merged_provenance.update(live_record.provenance_metadata)
        merged_source_trade_identity = self._build_converged_source_trade_identity(
            archive_record=archive_record,
            live_record=live_record,
        )
        merged_canonical_dedup_identity = self._build_converged_canonical_identity(
            archive_record=archive_record,
            live_record=live_record,
            overlap_result=overlap_result,
        )
        merged_provenance["merge"] = {
            "overlap_verdict": overlap_result.verdict,
            "overlap_reason": overlap_result.reason,
            "overlap_metadata": dict(overlap_result.metadata),
            "merged_source_trade_identity": merged_source_trade_identity,
            "merged_canonical_dedup_identity": merged_canonical_dedup_identity,
        }
        return replace(
            anchor,
            source="bybit_converged_trade",
            source_trade_identity=merged_source_trade_identity,
            canonical_dedup_identity=merged_canonical_dedup_identity,
            normalized_symbol=anchor.normalized_symbol,
            exchange_trade_at=anchor.exchange_trade_at,
            side=anchor.side,
            normalized_price=anchor.normalized_price,
            normalized_size=anchor.normalized_size,
            source_symbol_raw=anchor.source_symbol_raw or archive_record.source_symbol_raw or live_record.source_symbol_raw,
            provenance_state="live_and_archive",
            provenance_metadata=merged_provenance,
            updated_at=max(anchor.updated_at, archive_record.updated_at, live_record.updated_at),
        )

    def _build_converged_source_trade_identity(
        self,
        *,
        archive_record: BybitTradeLedgerRecord,
        live_record: BybitTradeLedgerRecord,
    ) -> str:
        basis = "|".join(
            (
                archive_record.exchange,
                archive_record.contour,
                archive_record.normalized_symbol,
                *sorted((archive_record.source_trade_identity, live_record.source_trade_identity)),
            )
        )
        digest = sha256(basis.encode("utf-8")).hexdigest()
        return (
            f"bybit_converged_trade:{archive_record.contour}:{archive_record.normalized_symbol}:"
            f"{digest}"
        )

    def _build_converged_canonical_identity(
        self,
        *,
        archive_record: BybitTradeLedgerRecord,
        live_record: BybitTradeLedgerRecord,
        overlap_result: BybitTradeOverlapResult,
    ) -> str:
        basis = "|".join(
            (
                archive_record.exchange,
                archive_record.contour,
                archive_record.normalized_symbol,
                str(archive_record.identity_contract_version),
                overlap_result.verdict,
                *sorted(
                    (
                        archive_record.canonical_dedup_identity,
                        live_record.canonical_dedup_identity,
                    )
                ),
            )
        )
        digest = sha256(basis.encode("utf-8")).hexdigest()
        return f"converged:v{archive_record.identity_contract_version}:{digest}"

    def _row_to_record(
        self,
        row: dict[str, object] | asyncpg.Record,
    ) -> BybitTradeLedgerRecord:
        payload = cast("dict[str, Any]", dict(row))
        source_metadata = payload.get("source_metadata") or {}
        if isinstance(source_metadata, str):
            source_metadata = cast("dict[str, Any]", json.loads(source_metadata))
        provenance_metadata = payload.get("provenance_metadata") or {}
        if isinstance(provenance_metadata, str):
            provenance_metadata = cast("dict[str, Any]", json.loads(provenance_metadata))
        return BybitTradeLedgerRecord(
            exchange=str(payload["exchange_id"]),
            contour=str(payload["contour"]),
            normalized_symbol=str(payload["normalized_symbol"]),
            source=str(payload["source"]),
            source_trade_identity=str(payload["source_trade_identity"]),
            canonical_dedup_identity=str(payload["canonical_dedup_identity"]),
            identity_contract_version=int(payload["identity_contract_version"]),
            exchange_trade_at=cast("Any", payload["exchange_trade_at"]),
            side=str(payload["side"]),
            normalized_price=cast("Any", payload["normalized_price"]),
            normalized_size=cast("Any", payload["normalized_size"]),
            source_symbol_raw=(
                str(payload["source_symbol_raw"])
                if payload.get("source_symbol_raw") is not None
                else None
            ),
            source_metadata=cast("dict[str, Any]", source_metadata),
            provenance_state=cast("Any", payload.get("provenance_state")),
            provenance_metadata=cast("dict[str, Any]", provenance_metadata),
            created_at=cast("Any", payload["created_at"]),
            updated_at=cast("Any", payload["updated_at"]),
        )

    def _row_to_live_prefetch_record(
        self,
        row: dict[str, object] | asyncpg.Record,
    ) -> BybitTradeLedgerRecord:
        payload = cast("dict[str, Any]", dict(row))
        source_metadata = payload.get("source_metadata") or {}
        if isinstance(source_metadata, str):
            source_metadata = cast("dict[str, Any]", json.loads(source_metadata))
        exchange_trade_at = cast("Any", payload["exchange_trade_at"])
        return BybitTradeLedgerRecord(
            exchange=str(payload["exchange_id"]),
            contour=str(payload["contour"]),
            normalized_symbol=str(payload["normalized_symbol"]),
            source=str(payload["source"]),
            source_trade_identity=str(payload["source_trade_identity"]),
            canonical_dedup_identity=str(payload["canonical_dedup_identity"]),
            identity_contract_version=int(payload["identity_contract_version"]),
            exchange_trade_at=exchange_trade_at,
            side=str(payload["side"]),
            normalized_price=cast("Any", payload["normalized_price"]),
            normalized_size=cast("Any", payload["normalized_size"]),
            source_metadata=cast("dict[str, Any]", source_metadata),
            created_at=exchange_trade_at,
            updated_at=exchange_trade_at,
        )

    def _archive_source_identities_from_scalar_rows(
        self,
        rows: Sequence[dict[str, object] | asyncpg.Record],
        *,
        column_name: str,
    ) -> set[str]:
        identities: set[str] = set()
        for row in rows:
            payload = cast("dict[str, Any]", dict(row))
            identity = payload.get(column_name)
            if isinstance(identity, str) and identity:
                identities.add(identity)
        return identities
