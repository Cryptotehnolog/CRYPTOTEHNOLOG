"""
Canonical identity construction layer for Bybit trade facts.

Модуль работает только поверх уже extracted trade facts и не содержит
ledger write/runtime wiring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from decimal import Decimal

    from .bybit_trade_backfill import (
        BybitArchiveTradeFact,
        BybitArchiveTradeFactExtraction,
    )

BYBIT_TRADE_IDENTITY_CONTRACT_VERSION = 1

BybitTradeIdentityVerdict = Literal["exact_candidate", "fallback_candidate", "not_identifiable"]


@dataclass(slots=True, frozen=True)
class BybitTradeIdentityResult:
    """Result of canonical identity construction for one extracted trade fact."""

    source: str
    contour: str
    normalized_symbol: str | None
    source_trade_identity: str | None
    canonical_dedup_identity: str | None
    identity_contract_version: int
    verdict: BybitTradeIdentityVerdict
    reason: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def build_bybit_trade_identity(
    extraction: BybitArchiveTradeFactExtraction,
) -> BybitTradeIdentityResult:
    if extraction.trade_fact is None:
        return BybitTradeIdentityResult(
            source="bybit_public_archive",
            contour="unknown",
            normalized_symbol=None,
            source_trade_identity=None,
            canonical_dedup_identity=None,
            identity_contract_version=BYBIT_TRADE_IDENTITY_CONTRACT_VERSION,
            verdict="not_identifiable",
            reason=extraction.reason or "archive_trade_fact_unavailable",
            metadata={"extraction_status": extraction.status},
        )
    trade_fact = extraction.trade_fact
    source_trade_identity = _build_source_trade_identity(trade_fact)
    canonical_dedup_identity = _build_canonical_dedup_identity(trade_fact)
    verdict = (
        "exact_candidate"
        if trade_fact.contour == "linear" and trade_fact.identity_strength == "strong_candidate"
        else "fallback_candidate"
    )
    return BybitTradeIdentityResult(
        source="bybit_public_archive",
        contour=trade_fact.contour,
        normalized_symbol=trade_fact.normalized_symbol,
        source_trade_identity=source_trade_identity,
        canonical_dedup_identity=canonical_dedup_identity,
        identity_contract_version=BYBIT_TRADE_IDENTITY_CONTRACT_VERSION,
        verdict=verdict,
        reason=(
            "linear_archive_strong_candidate"
            if verdict == "exact_candidate"
            else "fallback_first_archive_identity"
        ),
        metadata={
            "archive_trade_id": trade_fact.archive_trade_id or "",
            "identity_strength": trade_fact.identity_strength,
            "exchange_trade_at": trade_fact.exchange_trade_at.isoformat(),
            "side": trade_fact.side,
            "normalized_price": _decimal_identity_repr(trade_fact.normalized_price),
            "normalized_size": _decimal_identity_repr(trade_fact.normalized_size),
        },
    )


def build_bybit_archive_source_trade_identity(
    extraction: BybitArchiveTradeFactExtraction,
) -> str | None:
    if extraction.trade_fact is None:
        return None
    return _build_source_trade_identity(extraction.trade_fact)


def _build_source_trade_identity(trade_fact: BybitArchiveTradeFact) -> str:
    if trade_fact.contour == "linear" and trade_fact.archive_trade_id is not None:
        return (
            f"bybit_public_archive:{trade_fact.contour}:{trade_fact.normalized_symbol}:"
            f"{trade_fact.archive_trade_id}"
        )
    fallback_basis = "|".join((
        "bybit_public_archive",
        trade_fact.contour,
        trade_fact.normalized_symbol,
        trade_fact.exchange_trade_at.isoformat(),
        trade_fact.side,
        _decimal_identity_repr(trade_fact.normalized_price),
        _decimal_identity_repr(trade_fact.normalized_size),
        trade_fact.archive_trade_id or "",
    ))
    fallback_digest = sha256(fallback_basis.encode("utf-8")).hexdigest()
    return (
        f"bybit_public_archive:{trade_fact.contour}:{trade_fact.normalized_symbol}:"
        f"fallback:{fallback_digest}"
    )


def _build_canonical_dedup_identity(trade_fact: BybitArchiveTradeFact) -> str:
    if trade_fact.archive_trade_id is not None:
        strong_basis = "|".join((
            "bybit",
            trade_fact.contour,
            trade_fact.normalized_symbol,
            trade_fact.archive_trade_id,
        ))
        strong_digest = sha256(strong_basis.encode("utf-8")).hexdigest()
        return f"archive_strong:v{BYBIT_TRADE_IDENTITY_CONTRACT_VERSION}:{strong_digest}"
    canonical_basis = "|".join((
        "bybit",
        trade_fact.contour,
        trade_fact.normalized_symbol,
        trade_fact.exchange_trade_at.isoformat(),
        trade_fact.side,
        _decimal_identity_repr(trade_fact.normalized_price),
        _decimal_identity_repr(trade_fact.normalized_size),
    ))
    digest = sha256(canonical_basis.encode("utf-8")).hexdigest()
    return f"fallback:v{BYBIT_TRADE_IDENTITY_CONTRACT_VERSION}:{digest}"


def _decimal_identity_repr(value: Decimal) -> str:
    normalized = format(value.normalize(), "f")
    normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"
