"""
Контракты persistence foundation для canonical Bybit trade ledger.

Модуль намеренно не зависит от `asyncpg` и не содержит
инфраструктурной логики wiring/reconciliation/cutover.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol

if TYPE_CHECKING:
    from decimal import Decimal

    from .bybit_trade_overlap import BybitTradeOverlapResult


BybitTradeLedgerProvenanceState = Literal[
    "live_only",
    "archive_only",
    "live_and_archive",
]


class IBybitTradeLedgerRepository(Protocol):
    """Узкий persistence contract для foundation-слоя Bybit trade ledger."""

    async def upsert_trade_fact(self, record: BybitTradeLedgerRecord) -> None:
        """Сохранить или обновить canonical trade fact по dedup identity."""

    async def converge_trade_fact_pair(
        self,
        *,
        archive_record: BybitTradeLedgerRecord,
        live_record: BybitTradeLedgerRecord,
        overlap_result: BybitTradeOverlapResult,
    ) -> BybitTradeLedgerConvergenceResult:
        """Сконвергировать archive/live pair в storage-level representation."""

    async def get_trade_fact(
        self,
        *,
        exchange: str,
        contour: str,
        identity_contract_version: int,
        canonical_dedup_identity: str,
    ) -> BybitTradeLedgerRecord | None:
        """Получить одну canonical trade row по её identity."""

    async def delete_trade_fact(
        self,
        *,
        exchange: str,
        contour: str,
        identity_contract_version: int,
        canonical_dedup_identity: str,
    ) -> None:
        """Удалить одну canonical trade row по её identity."""

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
        """Получить canonical trade rows по symbol/contour/time window."""

    async def prefetch_materialization_window(
        self,
        *,
        exchange: str,
        contour: str,
        normalized_symbol: str,
        window_started_at: datetime,
        window_ended_at: datetime,
    ) -> "BybitTradeLedgerMaterializationPrefetch":
        """Получить только данные, нужные bulk-materialization prefetch path."""


@dataclass(slots=True, frozen=True)
class BybitTradeLedgerConvergenceResult:
    """Результат repository-level convergence для archive/live pair."""

    status: Literal["merged", "stored_separately"]
    stored_records: tuple["BybitTradeLedgerRecord", ...]
    overlap_verdict: str


@dataclass(slots=True, frozen=True)
class BybitTradeLedgerMaterializationPrefetch:
    """Минимальный prefetch payload для archive bulk-materialization."""

    archive_source_identities: tuple[str, ...]
    live_rows: tuple["BybitTradeLedgerRecord", ...]


@dataclass(slots=True, frozen=True)
class BybitTradeLedgerRecord:
    """Минимальная canonical trade row первой trade-DB фазы."""

    exchange: str
    contour: str
    normalized_symbol: str
    source: str
    source_trade_identity: str
    canonical_dedup_identity: str
    identity_contract_version: int
    exchange_trade_at: datetime
    side: str
    normalized_price: Decimal
    normalized_size: Decimal
    source_symbol_raw: str | None = None
    source_metadata: dict[str, Any] = field(default_factory=dict)
    provenance_state: BybitTradeLedgerProvenanceState | None = None
    provenance_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.exchange.strip():
            raise ValueError("exchange не может быть пустым")
        if not self.contour.strip():
            raise ValueError("contour не может быть пустым")
        if not self.normalized_symbol.strip():
            raise ValueError("normalized_symbol не может быть пустым")
        if not self.source.strip():
            raise ValueError("source не может быть пустым")
        if not self.source_trade_identity.strip():
            raise ValueError("source_trade_identity не может быть пустым")
        if not self.canonical_dedup_identity.strip():
            raise ValueError("canonical_dedup_identity не может быть пустым")
        if self.identity_contract_version <= 0:
            raise ValueError("identity_contract_version должен быть положительным")
        if not self.side.strip():
            raise ValueError("side не может быть пустым")
        if self.provenance_state is None:
            object.__setattr__(self, "provenance_state", _default_provenance_state(self.source))
        if self.provenance_state not in {"live_only", "archive_only", "live_and_archive"}:
            raise ValueError("provenance_state должен быть одним из supported source states")
        if not self.provenance_metadata:
            object.__setattr__(
                self,
                "provenance_metadata",
                _build_single_source_provenance_payload(
                    source=self.source,
                    source_trade_identity=self.source_trade_identity,
                    source_metadata=self.source_metadata,
                ),
            )
        object.__setattr__(self, "exchange_trade_at", self.exchange_trade_at.astimezone(UTC))
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        object.__setattr__(self, "updated_at", self.updated_at.astimezone(UTC))


def _default_provenance_state(source: str) -> BybitTradeLedgerProvenanceState:
    normalized_source = source.strip().lower()
    if normalized_source == "live_public_trade":
        return "live_only"
    return "archive_only"


def _build_single_source_provenance_payload(
    *,
    source: str,
    source_trade_identity: str,
    source_metadata: dict[str, Any],
) -> dict[str, Any]:
    slot = "live" if source.strip().lower() == "live_public_trade" else "archive"
    return {
        slot: {
            "source": source,
            "source_trade_identity": source_trade_identity,
            "source_metadata": dict(source_metadata),
        }
    }
