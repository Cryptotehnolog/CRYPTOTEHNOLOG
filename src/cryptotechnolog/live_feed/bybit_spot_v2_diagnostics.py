"""Compact operator-facing diagnostics surface for Bybit spot v2."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
import inspect
from typing import TYPE_CHECKING, Any

from cryptotechnolog.core.database import DatabaseManager

from .bybit_spot_v2_persisted_query import BybitSpotV2PersistedQueryService
from .bybit_spot_v2_reconciliation import BybitSpotV2ReconciliationService
from .bybit_spot_v2_recovery import run_bybit_spot_v2_recovery_probe

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(slots=True, frozen=True)
class BybitSpotV2DiagnosticsSymbolSnapshot:
    normalized_symbol: str
    volume_24h_usd: str | None
    reconciliation_verdict: str
    reconciliation_reason: str
    absolute_diff: int | None
    derived_trade_count_24h: int | None
    persisted_trade_count_24h: int


@dataclass(slots=True, frozen=True)
class BybitSpotV2DiagnosticsSnapshot:
    generation: str
    status: str
    observed_at: datetime
    symbols: tuple[str, ...]
    transport: dict[str, object]
    ingest: dict[str, object]
    persistence: dict[str, object]
    recovery: dict[str, object]
    reconciliation: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["observed_at"] = self.observed_at.isoformat()
        return payload


class BybitSpotV2DiagnosticsService:
    """Build a compact v2 operator snapshot from existing transport/recovery/persistence slices."""

    def __init__(
        self,
        *,
        persisted_query_service: BybitSpotV2PersistedQueryService,
        reconciliation_service: BybitSpotV2ReconciliationService,
        transport_diagnostics_provider: Callable[[], dict[str, object]],
        recovery_diagnostics_provider: Callable[[], dict[str, object]],
        symbol_volume_24h_provider: Callable[[Sequence[str]], dict[str, str | None]] | None = None,
    ) -> None:
        self._persisted_query_service = persisted_query_service
        self._reconciliation_service = reconciliation_service
        self._transport_diagnostics_provider = transport_diagnostics_provider
        self._recovery_diagnostics_provider = recovery_diagnostics_provider
        self._symbol_volume_24h_provider = symbol_volume_24h_provider

    async def build_snapshot(
        self,
        *,
        symbols: Sequence[str],
        observed_at: datetime | None = None,
        window_hours: int = 24,
    ) -> BybitSpotV2DiagnosticsSnapshot:
        normalized_symbols = tuple(str(symbol) for symbol in symbols if str(symbol))
        effective_observed_at = (observed_at or _utcnow()).astimezone(UTC)
        transport = self._transport_diagnostics_provider()
        recovery = self._recovery_diagnostics_provider()
        if inspect.isawaitable(recovery):
            recovery = await recovery
        volume_24h_by_symbol = (
            self._symbol_volume_24h_provider(normalized_symbols)
            if self._symbol_volume_24h_provider is not None
            else {}
        )
        persisted = await self._persisted_query_service.query_rolling_window(
            symbols=normalized_symbols,
            observed_at=effective_observed_at,
            window_hours=window_hours,
        )
        reconciliation = await self._reconciliation_service.build_snapshot(
            symbols=normalized_symbols,
            observed_at=effective_observed_at,
            window_hours=window_hours,
        )
        return BybitSpotV2DiagnosticsSnapshot(
            generation="v2",
            status=_resolve_operator_status(
                transport=transport,
                recovery=recovery,
                scope_verdict=reconciliation.scope_verdict,
                scope_reason=reconciliation.scope_reason,
            ),
            observed_at=effective_observed_at,
            symbols=normalized_symbols,
            transport={
                "transport_status": transport.get("transport_status"),
                "subscription_alive": transport.get("subscription_alive"),
                "transport_rtt_ms": transport.get("transport_rtt_ms"),
                "last_message_at": transport.get("last_message_at"),
                "messages_received_count": transport.get("messages_received_count"),
            },
            ingest={
                "trade_seen": transport.get("trade_seen"),
                "orderbook_seen": transport.get("orderbook_seen"),
                "best_bid": transport.get("best_bid"),
                "best_ask": transport.get("best_ask"),
                "trade_ingest_count": transport.get("trade_ingest_count"),
                "orderbook_ingest_count": transport.get("orderbook_ingest_count"),
            },
            persistence={
                "requested_window_started_at": (
                    (effective_observed_at - timedelta(hours=window_hours)).isoformat()
                ),
                "count_window_started_at": persisted.window_started_at.isoformat(),
                "window_ended_at": effective_observed_at.isoformat(),
                "window_contract": "rolling_24h_exact",
                "split_contract": "archive_origin_plus_live_residual_inside_same_window",
                "live_trade_count_24h": persisted.live_trade_count_24h,
                "archive_trade_count_24h": persisted.archive_trade_count_24h,
                "persisted_trade_count_24h": persisted.persisted_trade_count_24h,
                "first_persisted_trade_at": (
                    persisted.earliest_trade_at.isoformat()
                    if persisted.earliest_trade_at is not None
                    else None
                ),
                "last_persisted_trade_at": (
                    persisted.latest_trade_at.isoformat()
                    if persisted.latest_trade_at is not None
                    else None
                ),
                "earliest_trade_at": (
                    persisted.earliest_trade_at.isoformat()
                    if persisted.earliest_trade_at is not None
                    else None
                ),
                "latest_trade_at": (
                    persisted.latest_trade_at.isoformat()
                    if persisted.latest_trade_at is not None
                    else None
                ),
                "symbols_covered": persisted.symbols_covered,
                "coverage_status": persisted.coverage_status,
            },
            recovery={
                "status": recovery.get("status"),
                "stage": recovery.get("stage"),
                "reason": recovery.get("reason"),
                "last_progress_checkpoint": recovery.get("last_progress_checkpoint"),
            },
            reconciliation={
                "scope_verdict": reconciliation.scope_verdict,
                "scope_reason": reconciliation.scope_reason,
                "symbols": tuple(
                    BybitSpotV2DiagnosticsSymbolSnapshot(
                        normalized_symbol=snapshot.normalized_symbol,
                        volume_24h_usd=volume_24h_by_symbol.get(snapshot.normalized_symbol),
                        reconciliation_verdict=snapshot.reconciliation_verdict,
                        reconciliation_reason=snapshot.reconciliation_reason,
                        absolute_diff=snapshot.absolute_diff,
                        derived_trade_count_24h=snapshot.derived_trade_count_24h,
                        persisted_trade_count_24h=snapshot.persisted_trade_count_24h,
                    )
                    for snapshot in reconciliation.symbol_snapshots
                ),
            },
        )


def _resolve_operator_status(
    *,
    transport: dict[str, object],
    recovery: dict[str, object],
    scope_verdict: str,
    scope_reason: str | None = None,
) -> str:
    transport_status = str(transport.get("transport_status") or "unknown")
    subscription_alive = transport.get("subscription_alive") is True
    recovery_status = str(recovery.get("status") or "unknown")
    if transport_status != "connected" or not subscription_alive:
        return "transport_degraded"
    if recovery_status in {"planned", "running"}:
        return "recovering"
    if scope_verdict == "mismatch":
        return "attention_required"
    if scope_verdict == "retired_baseline":
        return "legacy_baseline_frozen"
    if scope_verdict == "unavailable":
        if scope_reason == "legacy_derived_snapshot_stale_after_primary_switch":
            return "legacy_reconciliation_stale"
        return "derived_unavailable"
    return "ready"


def _disabled_transport_diagnostics() -> dict[str, object]:
    return {
        "transport_status": "disabled",
        "subscription_alive": False,
        "transport_rtt_ms": None,
        "last_message_at": None,
        "messages_received_count": 0,
        "trade_seen": False,
        "orderbook_seen": False,
        "best_bid": None,
        "best_ask": None,
        "trade_ingest_count": 0,
        "orderbook_ingest_count": 0,
    }


def _disabled_recovery_diagnostics() -> dict[str, object]:
    return {
        "status": "disabled",
        "stage": "disabled",
        "reason": None,
        "last_progress_checkpoint": None,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compact spot v2 diagnostics surface.",
    )
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    db_manager = DatabaseManager()
    try:
        probe = await asyncio.wait_for(
            run_bybit_spot_v2_recovery_probe(
                db_manager=db_manager,
                symbols=tuple(args.symbols),
                window_hours=args.window_hours,
                timeout_seconds=args.timeout_seconds,
            ),
            timeout=args.timeout_seconds + 2,
        )
        service = BybitSpotV2DiagnosticsService(
            persisted_query_service=BybitSpotV2PersistedQueryService(db_manager),
            reconciliation_service=BybitSpotV2ReconciliationService(
                persisted_query_service=BybitSpotV2PersistedQueryService(db_manager),
            ),
            transport_diagnostics_provider=lambda: probe.transport,
            recovery_diagnostics_provider=lambda: probe.recovery,
        )
        snapshot = await service.build_snapshot(
            symbols=tuple(args.symbols),
            observed_at=_utcnow(),
            window_hours=args.window_hours,
        )
        print(json.dumps(snapshot.as_dict(), ensure_ascii=False))
    finally:
        await db_manager.close()


__all__ = [
    "BybitSpotV2DiagnosticsService",
    "BybitSpotV2DiagnosticsSnapshot",
    "BybitSpotV2DiagnosticsSymbolSnapshot",
]


if __name__ == "__main__":
    asyncio.run(_main())
