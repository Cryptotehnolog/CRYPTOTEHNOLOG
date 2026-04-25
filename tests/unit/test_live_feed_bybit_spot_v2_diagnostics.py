from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from cryptotechnolog.live_feed.bybit_spot_v2_diagnostics import (
    BybitSpotV2DiagnosticsService,
)


@dataclass(slots=True, frozen=True)
class _PersistedSymbolSnapshot:
    normalized_symbol: str
    live_trade_count_24h: int
    archive_trade_count_24h: int
    persisted_trade_count_24h: int
    earliest_trade_at: datetime | None
    latest_trade_at: datetime | None
    coverage_status: str


@dataclass(slots=True, frozen=True)
class _PersistedWindowSnapshot:
    window_started_at: datetime
    live_trade_count_24h: int
    archive_trade_count_24h: int
    persisted_trade_count_24h: int
    earliest_trade_at: datetime | None
    latest_trade_at: datetime | None
    symbols_covered: tuple[str, ...]
    coverage_status: str
    symbols: tuple[_PersistedSymbolSnapshot, ...]


@dataclass(slots=True, frozen=True)
class _ReconciliationSymbolSnapshot:
    normalized_symbol: str
    reconciliation_verdict: str
    reconciliation_reason: str
    absolute_diff: int | None
    derived_trade_count_24h: int | None
    persisted_trade_count_24h: int


@dataclass(slots=True, frozen=True)
class _ReconciliationSnapshot:
    scope_verdict: str
    scope_reason: str
    symbol_snapshots: tuple[_ReconciliationSymbolSnapshot, ...]


class _PersistedQueryService:
    async def query_rolling_window(self, *, symbols, observed_at, window_hours):
        _ = (symbols, observed_at, window_hours)
        return _PersistedWindowSnapshot(
            window_started_at=datetime(2026, 4, 13, 21, 30, tzinfo=UTC),
            live_trade_count_24h=28,
            archive_trade_count_24h=492532,
            persisted_trade_count_24h=492560,
            earliest_trade_at=datetime(2026, 4, 13, 21, 30, tzinfo=UTC),
            latest_trade_at=datetime(2026, 4, 14, 21, 8, tzinfo=UTC),
            symbols_covered=("BTC/USDT", "ETH/USDT"),
            coverage_status="hybrid",
            symbols=(
                _PersistedSymbolSnapshot(
                    normalized_symbol="BTC/USDT",
                    live_trade_count_24h=24,
                    archive_trade_count_24h=231034,
                    persisted_trade_count_24h=231058,
                    earliest_trade_at=None,
                    latest_trade_at=None,
                    coverage_status="hybrid",
                ),
                _PersistedSymbolSnapshot(
                    normalized_symbol="ETH/USDT",
                    live_trade_count_24h=4,
                    archive_trade_count_24h=261498,
                    persisted_trade_count_24h=261502,
                    earliest_trade_at=None,
                    latest_trade_at=None,
                    coverage_status="hybrid",
                ),
            ),
        )


class _ReconciliationService:
    async def build_snapshot(self, *, symbols, observed_at, window_hours):
        _ = (symbols, observed_at, window_hours)
        return _ReconciliationSnapshot(
            scope_verdict="retired_baseline",
            scope_reason="legacy_baseline_frozen_after_primary_switch",
            symbol_snapshots=(
                _ReconciliationSymbolSnapshot(
                    normalized_symbol="BTC/USDT",
                    reconciliation_verdict="retired_baseline",
                    reconciliation_reason="legacy_baseline_frozen_after_primary_switch",
                    absolute_diff=None,
                    derived_trade_count_24h=None,
                    persisted_trade_count_24h=231058,
                ),
                _ReconciliationSymbolSnapshot(
                    normalized_symbol="ETH/USDT",
                    reconciliation_verdict="retired_baseline",
                    reconciliation_reason="legacy_baseline_frozen_after_primary_switch",
                    absolute_diff=None,
                    derived_trade_count_24h=None,
                    persisted_trade_count_24h=261502,
                ),
            ),
        )


@pytest.mark.asyncio
async def test_spot_v2_diagnostics_service_builds_compact_snapshot() -> None:
    service = BybitSpotV2DiagnosticsService(
        persisted_query_service=_PersistedQueryService(),
        reconciliation_service=_ReconciliationService(),
        transport_diagnostics_provider=lambda: {
            "transport_status": "connected",
            "subscription_alive": True,
            "transport_rtt_ms": 415,
            "last_message_at": "2026-04-14T21:08:10.915000+00:00",
            "messages_received_count": 47,
            "trade_seen": True,
            "orderbook_seen": True,
            "best_bid": "74140.2",
            "best_ask": "74140.3",
            "trade_ingest_count": 5,
            "orderbook_ingest_count": 51,
        },
        recovery_diagnostics_provider=lambda: {
            "status": "running",
            "stage": "archive_load_started",
            "reason": None,
            "last_progress_checkpoint": "archive_load_started",
        },
        symbol_volume_24h_provider=lambda symbols: {
            "BTC/USDT": "123456.78",
            "ETH/USDT": "98765.43",
        },
    )

    snapshot = await service.build_snapshot(
        symbols=("BTC/USDT", "ETH/USDT"),
        observed_at=datetime(2026, 4, 14, 21, 30, tzinfo=UTC),
    )
    payload = snapshot.as_dict()

    assert payload["generation"] == "v2"
    assert payload["status"] == "recovering"
    assert payload["transport"]["transport_status"] == "connected"
    assert payload["ingest"]["trade_seen"] is True
    assert payload["persistence"]["persisted_trade_count_24h"] == 492560
    assert payload["persistence"]["count_window_started_at"] == "2026-04-13T21:30:00+00:00"
    assert payload["persistence"]["window_ended_at"] == "2026-04-14T21:30:00+00:00"
    assert payload["persistence"]["first_persisted_trade_at"] == "2026-04-13T21:30:00+00:00"
    assert payload["persistence"]["last_persisted_trade_at"] == "2026-04-14T21:08:00+00:00"
    assert payload["persistence"]["window_contract"] == "rolling_24h_exact"
    assert (
        payload["persistence"]["split_contract"]
        == "archive_origin_plus_live_residual_inside_same_window"
    )
    assert payload["recovery"]["status"] == "running"
    assert payload["reconciliation"]["scope_verdict"] == "retired_baseline"
    assert payload["reconciliation"]["symbols"][0]["normalized_symbol"] == "BTC/USDT"
    assert payload["reconciliation"]["symbols"][0]["volume_24h_usd"] == "123456.78"
    assert payload["reconciliation"]["symbols"][1]["normalized_symbol"] == "ETH/USDT"


@pytest.mark.asyncio
async def test_spot_v2_diagnostics_marks_stale_legacy_baseline_as_frozen() -> None:
    service = BybitSpotV2DiagnosticsService(
        persisted_query_service=_PersistedQueryService(),
        reconciliation_service=_ReconciliationService(),
        transport_diagnostics_provider=lambda: {
            "transport_status": "connected",
            "subscription_alive": True,
            "transport_rtt_ms": 415,
            "last_message_at": "2026-04-14T21:08:10.915000+00:00",
            "messages_received_count": 47,
            "trade_seen": True,
            "orderbook_seen": True,
            "best_bid": "74140.2",
            "best_ask": "74140.3",
            "trade_ingest_count": 5,
            "orderbook_ingest_count": 51,
        },
        recovery_diagnostics_provider=lambda: {
            "status": "skipped",
            "stage": "skipped_coverage_present",
            "reason": "coverage_present",
            "last_progress_checkpoint": "coverage_present",
        },
        symbol_volume_24h_provider=lambda symbols: {},
    )

    snapshot = await service.build_snapshot(
        symbols=("BTC/USDT", "ETH/USDT"),
        observed_at=datetime(2026, 4, 14, 21, 30, tzinfo=UTC),
    )

    assert snapshot.status == "legacy_baseline_frozen"
    assert snapshot.reconciliation["scope_verdict"] == "retired_baseline"
    assert (
        snapshot.reconciliation["scope_reason"]
        == "legacy_baseline_frozen_after_primary_switch"
    )
