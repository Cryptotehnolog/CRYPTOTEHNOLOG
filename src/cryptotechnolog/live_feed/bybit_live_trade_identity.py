"""
Live-side canonical identity construction for Bybit trade facts.

Модуль работает только поверх typed live trade facts и не делает
runtime/ledger wiring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from decimal import Decimal

    from .bybit_live_trade_fact import BybitLiveTradeFactBuildResult

BYBIT_LIVE_TRADE_IDENTITY_CONTRACT_VERSION = 1

BybitLiveTradeIdentityVerdict = Literal["exact_candidate", "not_identifiable"]


@dataclass(slots=True, frozen=True)
class BybitLiveTradeIdentityResult:
    """Result of live-side canonical identity construction."""

    source: str
    contour: str
    normalized_symbol: str | None
    source_trade_identity: str | None
    canonical_dedup_identity: str | None
    identity_contract_version: int
    verdict: BybitLiveTradeIdentityVerdict
    reason: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def build_bybit_live_trade_identity(
    fact_result: BybitLiveTradeFactBuildResult,
) -> BybitLiveTradeIdentityResult:
    if fact_result.trade_fact is None:
        return BybitLiveTradeIdentityResult(
            source="live_public_trade",
            contour="unknown",
            normalized_symbol=None,
            source_trade_identity=None,
            canonical_dedup_identity=None,
            identity_contract_version=BYBIT_LIVE_TRADE_IDENTITY_CONTRACT_VERSION,
            verdict="not_identifiable",
            reason=fact_result.reason or "live_trade_fact_unavailable",
            metadata={"build_status": fact_result.status},
        )
    trade_fact = fact_result.trade_fact
    source_trade_identity = (
        f"live_public_trade:{trade_fact.contour}:{trade_fact.normalized_symbol}:"
        f"{trade_fact.live_trade_id}"
    )
    canonical_basis = "|".join((
        "bybit",
        trade_fact.contour,
        trade_fact.normalized_symbol,
        trade_fact.live_trade_id,
    ))
    canonical_digest = sha256(canonical_basis.encode("utf-8")).hexdigest()
    return BybitLiveTradeIdentityResult(
        source="live_public_trade",
        contour=trade_fact.contour,
        normalized_symbol=trade_fact.normalized_symbol,
        source_trade_identity=source_trade_identity,
        canonical_dedup_identity=(
            f"live_strong:v{BYBIT_LIVE_TRADE_IDENTITY_CONTRACT_VERSION}:{canonical_digest}"
        ),
        identity_contract_version=BYBIT_LIVE_TRADE_IDENTITY_CONTRACT_VERSION,
        verdict="exact_candidate",
        reason="live_trade_id_strong_source_candidate",
        metadata={
            "live_trade_id": trade_fact.live_trade_id,
            "identity_strength": trade_fact.identity_strength,
            "exchange_trade_at": trade_fact.exchange_trade_at.isoformat(),
            "side": trade_fact.side,
            "normalized_price": _decimal_identity_repr(trade_fact.normalized_price),
            "normalized_size": _decimal_identity_repr(trade_fact.normalized_size),
        },
    )


def _decimal_identity_repr(value: Decimal) -> str:
    normalized = format(value.normalize(), "f")
    normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"
