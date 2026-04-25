from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cryptotechnolog.live_feed.bybit_spot_v2_archive_ledger import (
    BybitSpotV2ArchiveTradeLedgerRepository,
)
from cryptotechnolog.live_feed.bybit_spot_v2_live_trade_ledger import (
    BybitSpotV2LiveTradeLedgerRepository,
)


class _Connection:
    def __init__(self, *, deleted_count: int = 0) -> None:
        self.deleted_count = deleted_count
        self.fetchval_calls: list[tuple[str, tuple[object, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, sql: str, *params: object) -> None:
        self.execute_calls.append((sql, params))

    async def fetchval(self, sql: str, *params: object):
        self.fetchval_calls.append((sql, params))
        return self.deleted_count


class _ConnectionContext:
    def __init__(self, connection: _Connection) -> None:
        self._connection = connection

    async def __aenter__(self) -> _Connection:
        return self._connection

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _DbManager:
    def __init__(self, connection: _Connection) -> None:
        self._connection = connection

    def connection(self) -> _ConnectionContext:
        return _ConnectionContext(self._connection)


@pytest.mark.asyncio
async def test_spot_v2_live_trade_ledger_cleanup_retention_deletes_rows_older_than_cutoff() -> None:
    connection = _Connection(deleted_count=17)
    repository = BybitSpotV2LiveTradeLedgerRepository(_DbManager(connection))  # type: ignore[arg-type]

    deleted = await repository.cleanup_retention(
        retention_hours=48,
        reference_at=datetime(2026, 4, 24, 2, 0, tzinfo=UTC),
    )

    assert deleted == 17
    assert connection.fetchval_calls
    _, params = connection.fetchval_calls[-1]
    assert params == (datetime(2026, 4, 22, 2, 0, tzinfo=UTC),)


@pytest.mark.asyncio
async def test_spot_v2_archive_trade_ledger_cleanup_retention_deletes_rows_older_than_cutoff() -> None:
    connection = _Connection(deleted_count=23)
    repository = BybitSpotV2ArchiveTradeLedgerRepository(_DbManager(connection))  # type: ignore[arg-type]

    deleted = await repository.cleanup_retention(
        retention_hours=48,
        reference_at=datetime(2026, 4, 24, 2, 0, tzinfo=UTC),
    )

    assert deleted == 23
    assert connection.fetchval_calls
    _, params = connection.fetchval_calls[-1]
    assert params == (datetime(2026, 4, 22, 2, 0, tzinfo=UTC),)
