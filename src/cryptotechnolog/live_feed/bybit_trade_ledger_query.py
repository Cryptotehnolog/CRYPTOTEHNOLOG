"""
Ledger read/query path for rolling 24h Bybit trade count.

Модуль intentionally ограничен read-only query semantics поверх
уже существующего canonical trade ledger repository contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .bybit_trade_ledger_contracts import BybitTradeLedgerRecord, IBybitTradeLedgerRepository

_ROLLING_TRADE_COUNT_WINDOW = timedelta(hours=24)


@dataclass(slots=True, frozen=True)
class BybitTradeLedgerTradeCountQuery:
    """Read-only query for one rolling 24h trade-count window."""

    exchange: str
    contour: str
    normalized_symbol: str
    window_ended_at: datetime
    window: timedelta = _ROLLING_TRADE_COUNT_WINDOW

    @property
    def window_started_at(self) -> datetime:
        return self.window_ended_at.astimezone(UTC) - self.window


@dataclass(slots=True, frozen=True)
class BybitTradeLedgerTradeCountResult:
    """Typed result of rolling 24h trade-count query over ledger truth."""

    exchange: str
    contour: str
    normalized_symbol: str
    window_started_at: datetime
    window_ended_at: datetime
    trade_count_24h: int
    first_trade_at: datetime | None
    sources: tuple[str, ...]
    matched_rows: tuple[BybitTradeLedgerRecord, ...]


class BybitTradeLedgerTradeCountQueryService:
    """Read-only query service for rolling 24h trade count from ledger rows."""

    def __init__(self, repository: IBybitTradeLedgerRepository) -> None:
        self._repository = repository

    async def get_trade_count_24h(
        self,
        *,
        exchange: str,
        contour: str,
        normalized_symbol: str,
        window_ended_at: datetime,
    ) -> BybitTradeLedgerTradeCountResult:
        query = BybitTradeLedgerTradeCountQuery(
            exchange=exchange,
            contour=contour,
            normalized_symbol=normalized_symbol,
            window_ended_at=window_ended_at.astimezone(UTC),
        )
        rows = await self._repository.list_trade_facts(
            exchange=query.exchange,
            contour=query.contour,
            normalized_symbol=query.normalized_symbol,
            window_started_at=query.window_started_at,
            window_ended_at=query.window_ended_at,
        )
        return BybitTradeLedgerTradeCountResult(
            exchange=query.exchange,
            contour=query.contour,
            normalized_symbol=query.normalized_symbol,
            window_started_at=query.window_started_at,
            window_ended_at=query.window_ended_at,
            trade_count_24h=len(rows),
            first_trade_at=rows[0].exchange_trade_at if rows else None,
            sources=tuple(sorted({record.source for record in rows})),
            matched_rows=rows,
        )
