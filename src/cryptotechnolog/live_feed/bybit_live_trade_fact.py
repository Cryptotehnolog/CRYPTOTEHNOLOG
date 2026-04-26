"""
Typed live-side trade fact contract for Bybit publicTrade payloads.

Модуль intentionally не делает runtime wiring и работает только
с уже существующим parser transport payload contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

BybitLiveTradeFactBuildStatus = Literal["full_mappable", "not_mappable"]
BybitLiveTradeIdentityStrength = Literal["strong_candidate"]


@dataclass(slots=True, frozen=True)
class BybitLiveTradeFact:
    """Typed live trade fact extracted from current Bybit parser payload."""

    contour: str
    normalized_symbol: str
    exchange_trade_at: datetime
    side: str
    normalized_price: Decimal
    normalized_size: Decimal
    live_trade_id: str
    is_buyer_maker: bool
    raw_fields: dict[str, str]
    identity_strength: BybitLiveTradeIdentityStrength


@dataclass(slots=True, frozen=True)
class BybitLiveTradeFactBuildResult:
    """Result of live trade fact construction from transport payload."""

    status: BybitLiveTradeFactBuildStatus
    trade_fact: BybitLiveTradeFact | None
    reason: str | None = None


def build_bybit_live_trade_fact(
    *,
    contour: str,
    transport_payload: dict[str, Any],
) -> BybitLiveTradeFactBuildResult:
    symbol = _required_str(transport_payload.get("symbol"))
    side = _normalize_side(transport_payload.get("side"))
    trade_id = _required_str(transport_payload.get("trade_id"))
    price = _parse_decimal(transport_payload.get("price"))
    size = _parse_decimal(transport_payload.get("qty"))
    exchange_trade_at = _parse_trade_timestamp_ms(transport_payload.get("exchange_trade_at_ms"))
    missing_reason: str | None = None
    if symbol is None:
        missing_reason = "missing_symbol"
    elif side is None:
        missing_reason = "missing_side"
    elif trade_id is None:
        missing_reason = "missing_trade_id"
    elif price is None:
        missing_reason = "missing_price"
    elif size is None:
        missing_reason = "missing_qty"
    elif exchange_trade_at is None:
        missing_reason = "missing_exchange_trade_at_ms"
    if missing_reason is not None:
        return BybitLiveTradeFactBuildResult(
            status="not_mappable",
            trade_fact=None,
            reason=missing_reason,
        )
    return BybitLiveTradeFactBuildResult(
        status="full_mappable",
        trade_fact=BybitLiveTradeFact(
            contour=contour,
            normalized_symbol=symbol,
            exchange_trade_at=exchange_trade_at,
            side=side,
            normalized_price=price,
            normalized_size=size,
            live_trade_id=trade_id,
            is_buyer_maker=bool(transport_payload.get("is_buyer_maker", False)),
            raw_fields={
                "symbol": symbol,
                "trade_id": trade_id,
                "price": str(price),
                "qty": str(size),
                "side": side,
                "exchange_trade_at_ms": str(int(exchange_trade_at.timestamp() * 1000)),
            },
            identity_strength="strong_candidate",
        ),
    )


def _required_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_side(value: object) -> str | None:
    normalized = _required_str(value)
    if normalized is None:
        return None
    lowered = normalized.lower()
    return lowered if lowered in {"buy", "sell"} else None


def _parse_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def _parse_trade_timestamp_ms(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        raw_ms = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(raw_ms / 1000, tz=UTC)
