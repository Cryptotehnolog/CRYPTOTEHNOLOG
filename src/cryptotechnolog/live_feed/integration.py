"""
Узкий ingest integration helper между live_feed и existing market_data runtime.

Этот модуль:
- принимает только typed FeedIngestRequest;
- выполняет narrow conversion/admission path в market_data contracts;
- делегирует дальнейшую domain interpretation в existing market_data runtime;
- не вводит adapter ecosystem, websocket clients, persistence или event-bus platform semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from cryptotechnolog.market_data import (
    MarketDataSide,
    OrderBookLevel,
    OrderBookSnapshotContract,
    TickContract,
)

if TYPE_CHECKING:
    from uuid import UUID

    from cryptotechnolog.market_data import (
        MarketDataRuntime,
        OrderBookUpdateResult,
        TickRuntimeUpdate,
    )

    from .models import FeedIngestRequest


class UnsupportedFeedIngressError(ValueError):
    """Ошибка narrow ingest path для неподдерживаемого или некорректного handoff."""


@dataclass(slots=True, frozen=True)
class LiveFeedMarketDataIngressResult:
    """Результат narrow handoff из live_feed в market_data runtime."""

    request: FeedIngestRequest
    accepted_kind: str
    market_data_contract: TickContract | OrderBookSnapshotContract
    runtime_update: TickRuntimeUpdate | OrderBookUpdateResult


class LiveFeedMarketDataIngress:
    """Explicit helper для узкого handoff из live_feed в market_data."""

    _SUPPORTED_KINDS = frozenset({"trade_tick", "orderbook_snapshot"})

    async def ingest(
        self,
        *,
        request: FeedIngestRequest,
        market_data_runtime: MarketDataRuntime,
        correlation_id: UUID | None = None,
    ) -> LiveFeedMarketDataIngressResult:
        """Принять typed handoff и делегировать interpretation existing market_data runtime."""
        contract = self.build_market_data_contract(request)
        if isinstance(contract, TickContract):
            runtime_update = await market_data_runtime.ingest_tick(
                contract,
                correlation_id=correlation_id,
            )
        else:
            runtime_update = await market_data_runtime.ingest_orderbook_snapshot(
                contract,
                correlation_id=correlation_id,
            )
        return LiveFeedMarketDataIngressResult(
            request=request,
            accepted_kind=request.envelope.payload_kind,
            market_data_contract=contract,
            runtime_update=runtime_update,
        )

    def build_market_data_contract(
        self,
        request: FeedIngestRequest,
    ) -> TickContract | OrderBookSnapshotContract:
        """Сконвертировать typed live-feed handoff в typed market_data contract."""
        if request.source_contract != "live_feed_connectivity":
            raise UnsupportedFeedIngressError(
                "Поддерживается только live_feed_connectivity source_contract"
            )
        payload_kind = request.envelope.payload_kind
        if payload_kind not in self._SUPPORTED_KINDS:
            raise UnsupportedFeedIngressError(
                f"Неподдерживаемый payload_kind для market_data handoff: {payload_kind}"
            )
        if payload_kind == "trade_tick":
            return self._build_tick_contract(request)
        return self._build_orderbook_snapshot_contract(request)

    def _build_tick_contract(self, request: FeedIngestRequest) -> TickContract:
        payload = request.envelope.transport_payload
        symbol = self._resolve_symbol(request)
        exchange = request.envelope.session.exchange
        return TickContract(
            symbol=symbol,
            exchange=exchange,
            price=self._decimal_field(payload, "price"),
            quantity=self._decimal_field(payload, "qty"),
            side=self._side_field(payload),
            timestamp=request.envelope.ingested_at,
            trade_id=self._str_field(payload, "trade_id"),
            is_buyer_maker=bool(payload.get("is_buyer_maker", False)),
        )

    def _build_orderbook_snapshot_contract(
        self,
        request: FeedIngestRequest,
    ) -> OrderBookSnapshotContract:
        payload = request.envelope.transport_payload
        symbol = self._resolve_symbol(request)
        exchange = request.envelope.session.exchange
        bids = self._build_levels(payload.get("bids"), side_name="bids")
        asks = self._build_levels(payload.get("asks"), side_name="asks")
        if not bids or not asks:
            raise UnsupportedFeedIngressError(
                "orderbook_snapshot handoff требует non-empty bids и asks"
            )
        return OrderBookSnapshotContract(
            symbol=symbol,
            exchange=exchange,
            timestamp=request.envelope.ingested_at,
            bids=bids,
            asks=asks,
            spread_bps=self._calculate_spread_bps(bids, asks),
            checksum=self._optional_str_field(payload, "checksum"),
        )

    def _resolve_symbol(self, request: FeedIngestRequest) -> str:
        payload_symbol = request.envelope.transport_payload.get("symbol")
        if payload_symbol is not None:
            symbol = str(payload_symbol).strip()
            if symbol:
                return symbol
        scope = request.envelope.session.subscription_scope
        if len(scope) != 1:
            raise UnsupportedFeedIngressError(
                "symbol должен быть явным при multi-symbol subscription scope"
            )
        return scope[0]

    def _build_levels(
        self,
        raw_levels: object,
        *,
        side_name: str,
    ) -> tuple[OrderBookLevel, ...]:
        if not isinstance(raw_levels, list):
            raise UnsupportedFeedIngressError(
                f"orderbook_snapshot handoff требует list payload для {side_name}"
            )
        levels: list[OrderBookLevel] = []
        for level in raw_levels:
            if not isinstance(level, dict):
                raise UnsupportedFeedIngressError(
                    f"orderbook_snapshot handoff требует dict entries для {side_name}"
                )
            levels.append(
                OrderBookLevel(
                    price=self._decimal_field(level, "price"),
                    quantity=self._decimal_field(level, "qty"),
                    orders_count=self._optional_int_field(level, "orders_count"),
                )
            )
        return tuple(levels)

    def _str_field(self, payload: dict[str, object], field_name: str) -> str:
        value = payload.get(field_name)
        if value is None or not str(value).strip():
            raise UnsupportedFeedIngressError(f"ingest handoff требует non-empty {field_name}")
        return str(value)

    def _optional_str_field(self, payload: dict[str, object], field_name: str) -> str | None:
        value = payload.get(field_name)
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    def _decimal_field(self, payload: dict[str, object], field_name: str) -> Decimal:
        value = payload.get(field_name)
        if value is None:
            raise UnsupportedFeedIngressError(f"ingest handoff требует {field_name}")
        return Decimal(str(value))

    def _side_field(self, payload: dict[str, object]) -> MarketDataSide:
        side = self._str_field(payload, "side").lower()
        try:
            return MarketDataSide(side)
        except ValueError as exc:
            raise UnsupportedFeedIngressError(
                f"trade_tick handoff содержит неподдерживаемый side: {side}"
            ) from exc

    def _optional_int_field(self, payload: dict[str, object], field_name: str) -> int | None:
        value = payload.get(field_name)
        if value is None:
            return None
        normalized = int(value)
        if normalized < 0:
            raise UnsupportedFeedIngressError(f"{field_name} не может быть отрицательным")
        return normalized

    def _calculate_spread_bps(
        self,
        bids: tuple[OrderBookLevel, ...],
        asks: tuple[OrderBookLevel, ...],
    ) -> Decimal:
        best_bid = bids[0].price
        best_ask = asks[0].price
        midpoint = (best_bid + best_ask) / Decimal("2")
        if midpoint <= 0:
            return Decimal("0")
        return ((best_ask - best_bid) / midpoint) * Decimal("10000")


def create_live_feed_market_data_ingress() -> LiveFeedMarketDataIngress:
    """Собрать narrow helper для handoff из live_feed в existing market_data runtime."""
    return LiveFeedMarketDataIngress()


__all__ = [
    "LiveFeedMarketDataIngress",
    "LiveFeedMarketDataIngressResult",
    "UnsupportedFeedIngressError",
    "create_live_feed_market_data_ingress",
]
