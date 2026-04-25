from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import uuid

import pytest

from cryptotechnolog.live_feed.bybit_trade_count import (
    BybitDerivedTradeCountPersistenceStore,
    BybitDerivedTradeCountPersistedState,
)
from cryptotechnolog.live_feed.bybit_spot_v2_persisted_query import (
    BybitSpotV2PersistedSymbolSnapshot,
    BybitSpotV2PersistedWindowSnapshot,
)
from cryptotechnolog.live_feed.bybit_spot_v2_reconciliation import (
    BybitSpotV2DerivedTradeCountQueryService,
    BybitSpotV2DerivedSymbolSnapshot,
    BybitSpotV2ReconciliationService,
)


class _FakePersistedQueryService:
    def __init__(self, snapshot: BybitSpotV2PersistedWindowSnapshot) -> None:
        self.snapshot = snapshot

    async def query_rolling_window(self, *, symbols, observed_at, window_hours=24):
        _ = (symbols, observed_at, window_hours)
        return self.snapshot


class _FakeDerivedQueryService:
    def __init__(
        self,
        *,
        persisted_at: datetime | None,
        snapshots: tuple[BybitSpotV2DerivedSymbolSnapshot, ...],
    ) -> None:
        self.persisted_at = persisted_at
        self.snapshots = snapshots

    def query_snapshot(self, *, symbols, observed_at=None):
        _ = (symbols, observed_at)
        return self.persisted_at, self.snapshots


@pytest.mark.asyncio
async def test_spot_v2_reconciliation_reports_mismatch_and_diff() -> None:
    service = BybitSpotV2ReconciliationService(
        persisted_query_service=_FakePersistedQueryService(
            BybitSpotV2PersistedWindowSnapshot(
                observed_at=datetime(2026, 4, 14, 22, 22, 31, tzinfo=UTC),
                window_started_at=datetime(2026, 4, 13, 22, 22, 31, tzinfo=UTC),
                live_trade_count_24h=28,
                archive_trade_count_24h=492532,
                persisted_trade_count_24h=492560,
                earliest_trade_at=datetime(2026, 4, 13, 22, 30, tzinfo=UTC),
                latest_trade_at=datetime(2026, 4, 14, 22, 20, tzinfo=UTC),
                symbols_covered=("BTC/USDT", "ETH/USDT"),
                coverage_status="hybrid",
                symbols=(
                    BybitSpotV2PersistedSymbolSnapshot(
                        normalized_symbol="BTC/USDT",
                        live_trade_count_24h=24,
                        archive_trade_count_24h=231034,
                        persisted_trade_count_24h=231058,
                        earliest_trade_at=datetime(2026, 4, 13, 22, 30, tzinfo=UTC),
                        latest_trade_at=datetime(2026, 4, 14, 22, 20, tzinfo=UTC),
                        coverage_status="hybrid",
                    ),
                    BybitSpotV2PersistedSymbolSnapshot(
                        normalized_symbol="ETH/USDT",
                        live_trade_count_24h=4,
                        archive_trade_count_24h=261498,
                        persisted_trade_count_24h=261502,
                        earliest_trade_at=datetime(2026, 4, 13, 22, 30, tzinfo=UTC),
                        latest_trade_at=datetime(2026, 4, 14, 22, 20, tzinfo=UTC),
                        coverage_status="hybrid",
                    ),
                ),
            )
        ),
        derived_query_service=_FakeDerivedQueryService(
            persisted_at=datetime(2026, 4, 14, 22, 22, 31, tzinfo=UTC),
            snapshots=(
                BybitSpotV2DerivedSymbolSnapshot(
                    normalized_symbol="BTC/USDT",
                    derived_trade_count_24h=104325,
                    derived_state="ready",
                    derived_ready=True,
                ),
                BybitSpotV2DerivedSymbolSnapshot(
                    normalized_symbol="ETH/USDT",
                    derived_trade_count_24h=168981,
                    derived_state="ready",
                    derived_ready=True,
                ),
            ),
        ),
    )

    snapshot = await service.build_snapshot(symbols=("BTC/USDT", "ETH/USDT"))

    assert snapshot.scope_verdict == "mismatch"
    assert snapshot.scope_reason == "symbol_mismatch_present"
    assert snapshot.derived_trade_count_24h == 273306
    assert snapshot.persisted_trade_count_24h == 492560
    assert snapshot.absolute_diff == 219254
    assert snapshot.symbol_snapshots[0].absolute_diff == 126733
    assert snapshot.symbol_snapshots[0].reconciliation_reason == "persisted_exceeds_derived"
    assert snapshot.symbol_snapshots[1].absolute_diff == 92521


@pytest.mark.asyncio
async def test_spot_v2_reconciliation_reports_unavailable_when_derived_is_missing() -> None:
    service = BybitSpotV2ReconciliationService(
        persisted_query_service=_FakePersistedQueryService(
            BybitSpotV2PersistedWindowSnapshot(
                observed_at=datetime(2026, 4, 14, 22, 22, 31, tzinfo=UTC),
                window_started_at=datetime(2026, 4, 13, 22, 22, 31, tzinfo=UTC),
                live_trade_count_24h=1,
                archive_trade_count_24h=2,
                persisted_trade_count_24h=3,
                earliest_trade_at=datetime(2026, 4, 13, 22, 30, tzinfo=UTC),
                latest_trade_at=datetime(2026, 4, 14, 22, 20, tzinfo=UTC),
                symbols_covered=("BTC/USDT",),
                coverage_status="partial",
                symbols=(
                    BybitSpotV2PersistedSymbolSnapshot(
                        normalized_symbol="BTC/USDT",
                        live_trade_count_24h=1,
                        archive_trade_count_24h=2,
                        persisted_trade_count_24h=3,
                        earliest_trade_at=datetime(2026, 4, 13, 22, 30, tzinfo=UTC),
                        latest_trade_at=datetime(2026, 4, 14, 22, 20, tzinfo=UTC),
                        coverage_status="hybrid",
                    ),
                ),
            )
        ),
        derived_query_service=_FakeDerivedQueryService(
            persisted_at=None,
            snapshots=(
                BybitSpotV2DerivedSymbolSnapshot(
                    normalized_symbol="BTC/USDT",
                    derived_trade_count_24h=None,
                    derived_state="store_missing",
                    derived_ready=False,
                ),
            ),
        ),
    )

    snapshot = await service.build_snapshot(symbols=("BTC/USDT",))

    assert snapshot.scope_verdict == "unavailable"
    assert snapshot.scope_reason == "store_missing"
    assert snapshot.absolute_diff is None
    assert snapshot.symbol_snapshots[0].reconciliation_verdict == "unavailable"
    assert snapshot.symbol_snapshots[0].reconciliation_reason == "store_missing"


@pytest.mark.asyncio
async def test_spot_v2_reconciliation_reports_retired_baseline_when_legacy_snapshot_is_stale() -> None:
    service = BybitSpotV2ReconciliationService(
        persisted_query_service=_FakePersistedQueryService(
            BybitSpotV2PersistedWindowSnapshot(
                observed_at=datetime(2026, 4, 15, 16, 0, tzinfo=UTC),
                window_started_at=datetime(2026, 4, 14, 16, 0, tzinfo=UTC),
                live_trade_count_24h=5,
                archive_trade_count_24h=10,
                persisted_trade_count_24h=15,
                earliest_trade_at=datetime(2026, 4, 14, 16, 1, tzinfo=UTC),
                latest_trade_at=datetime(2026, 4, 15, 15, 59, tzinfo=UTC),
                symbols_covered=("BTC/USDT",),
                coverage_status="hybrid",
                symbols=(
                    BybitSpotV2PersistedSymbolSnapshot(
                        normalized_symbol="BTC/USDT",
                        live_trade_count_24h=5,
                        archive_trade_count_24h=10,
                        persisted_trade_count_24h=15,
                        earliest_trade_at=datetime(2026, 4, 14, 16, 1, tzinfo=UTC),
                        latest_trade_at=datetime(2026, 4, 15, 15, 59, tzinfo=UTC),
                        coverage_status="hybrid",
                    ),
                ),
            )
        ),
        derived_query_service=_FakeDerivedQueryService(
            persisted_at=datetime(2026, 4, 15, 12, 0, tzinfo=UTC),
            snapshots=(
                BybitSpotV2DerivedSymbolSnapshot(
                    normalized_symbol="BTC/USDT",
                    derived_trade_count_24h=None,
                    derived_state="stale_persisted_snapshot",
                    derived_ready=False,
                    derived_reason="legacy_derived_snapshot_stale_after_primary_switch",
                ),
            ),
        ),
    )

    snapshot = await service.build_snapshot(symbols=("BTC/USDT",))

    assert snapshot.scope_verdict == "retired_baseline"
    assert snapshot.scope_reason == "legacy_baseline_frozen_after_primary_switch"
    assert snapshot.absolute_diff is None
    assert snapshot.symbol_snapshots[0].reconciliation_verdict == "retired_baseline"
    assert (
        snapshot.symbol_snapshots[0].reconciliation_reason
        == "legacy_baseline_frozen_after_primary_switch"
    )


def test_spot_v2_derived_query_uses_restored_buckets_during_live_tail_pending_gap(
) -> None:
    artifact_dir = Path.cwd() / ".pytest-local-artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    store_path = artifact_dir / f"bybit_spot_derived_trade_count_{uuid.uuid4().hex}.json"
    store = BybitDerivedTradeCountPersistenceStore(path=store_path)
    persisted_at = datetime(2026, 4, 15, 12, 39, 43, tzinfo=UTC)
    try:
        store.save(
            BybitDerivedTradeCountPersistedState(
                persisted_at=persisted_at,
                state="live_tail_pending_after_gap",
                observation_started_at=datetime(2026, 4, 14, 10, 50, 15, tzinfo=UTC),
                last_gap_at=persisted_at,
                last_gap_reason="ping_timeout",
                live_tail_required_after=persisted_at,
                latest_observed_trade_at=None,
                observed_trade_count_since_reset={"BTC/USDT": 0},
                trade_count_buckets={
                    "BTC/USDT": {
                        datetime(2026, 4, 15, 11, 39, tzinfo=UTC): 11,
                        datetime(2026, 4, 15, 12, 20, tzinfo=UTC): 7,
                    }
                },
                historical_window_restored=True,
            )
        )
        service = BybitSpotV2DerivedTradeCountQueryService(store_path=store.path)

        persisted_at_result, snapshots = service.query_snapshot(
            symbols=("BTC/USDT",),
            observed_at=persisted_at,
        )

        assert persisted_at_result == persisted_at
        assert snapshots[0].derived_state == "live_tail_pending_after_gap"
        assert snapshots[0].derived_ready is False
        assert snapshots[0].derived_trade_count_24h == 18
    finally:
        store_path.unlink(missing_ok=True)
