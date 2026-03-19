"""
Типизированные контракты слоя рыночных данных.

Этот модуль фиксирует только contract layer Фазы 6:
- transport-neutral модели tick/bar/orderbook;
- символ и ликвидностные метрики;
- data quality сигналы;
- raw/admissible/ranked universe snapshots;
- confidence semantics universe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime


type SymbolIdentity = tuple[str, str]


def build_symbol_identity(symbol: str, exchange: str) -> SymbolIdentity:
    """Построить canonical identity ключ для symbol/exchange aware path."""
    return (symbol, exchange)


class MarketDataTimeframe(StrEnum):
    """Поддерживаемые таймфреймы для contract layer."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class InstrumentType(StrEnum):
    """Тип инструмента в universe contracts."""

    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURE = "future"
    OPTION = "option"


class MarketDataSide(StrEnum):
    """Направление сделки в tick contract."""

    BUY = "buy"
    SELL = "sell"


class UniverseMembershipLevel(StrEnum):
    """Уровень принадлежности символа внутри UniverseEngine."""

    RAW = "raw"
    ADMISSIBLE = "admissible"
    RANKED = "ranked"


class UniverseAdmissionReason(StrEnum):
    """Стандартные причины попадания символа в admissible universe."""

    LIQUIDITY_OK = "liquidity_ok"
    DEPTH_OK = "depth_ok"
    QUALITY_OK = "quality_ok"
    COVERAGE_OK = "coverage_ok"
    MANUAL_ALLOWLIST = "manual_allowlist"


class UniverseExclusionReason(StrEnum):
    """Стандартные причины исключения символа из admissible universe."""

    SPREAD_TOO_WIDE = "spread_too_wide"
    DEPTH_TOO_SHALLOW = "depth_too_shallow"
    DATA_STALE = "data_stale"
    DATA_GAP = "data_gap"
    OUTLIER_DETECTED = "outlier_detected"
    LOW_CONFIDENCE = "low_confidence"
    POLICY_DISABLED = "policy_disabled"
    METRICS_UNAVAILABLE = "metrics_unavailable"


class DataQualityIssueType(StrEnum):
    """Типы проблем качества данных."""

    GAP = "gap"
    STALE = "stale"
    OUTLIER = "outlier"
    OUT_OF_ORDER = "out_of_order"
    LOW_COVERAGE = "low_coverage"
    ORDERBOOK_CROSSED = "orderbook_crossed"
    SOURCE_DEGRADED = "source_degraded"


class DataQualitySeverity(StrEnum):
    """Серьёзность проблем качества данных."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class UniverseConfidenceState(StrEnum):
    """Операционная интерпретация качества universe."""

    READY = "ready"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


@dataclass(slots=True, frozen=True)
class SymbolContract:
    """Базовый typed contract для торгового инструмента."""

    symbol: str
    exchange: str
    base_asset: str
    quote_asset: str
    instrument_type: InstrumentType = InstrumentType.PERPETUAL
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def identity(self) -> SymbolIdentity:
        """Вернуть canonical identity инструмента."""
        return build_symbol_identity(self.symbol, self.exchange)


@dataclass(slots=True, frozen=True)
class TickContract:
    """Контракт единичной сделки, прошедшей нормализацию feed layer."""

    symbol: str
    exchange: str
    price: Decimal
    quantity: Decimal
    side: MarketDataSide
    timestamp: datetime
    trade_id: str
    is_buyer_maker: bool = False

    @property
    def identity(self) -> SymbolIdentity:
        """Вернуть canonical identity tick."""
        return build_symbol_identity(self.symbol, self.exchange)


@dataclass(slots=True, frozen=True)
class OHLCVBarContract:
    """Контракт завершённой или промежуточной свечи."""

    symbol: str
    exchange: str
    timeframe: MarketDataTimeframe
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    bid_volume: Decimal = Decimal("0")
    ask_volume: Decimal = Decimal("0")
    trades_count: int = 0
    is_closed: bool = False
    is_gap_affected: bool = False


@dataclass(slots=True, frozen=True)
class OrderBookLevel:
    """Один уровень стакана."""

    price: Decimal
    quantity: Decimal
    orders_count: int | None = None


@dataclass(slots=True, frozen=True)
class OrderBookSnapshotContract:
    """Контракт L2-стакана, пригодный для event publication."""

    symbol: str
    exchange: str
    timestamp: datetime
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    spread_bps: Decimal
    checksum: str | None = None
    is_gap_affected: bool = False

    @property
    def identity(self) -> SymbolIdentity:
        """Вернуть canonical identity orderbook snapshot."""
        return build_symbol_identity(self.symbol, self.exchange)


@dataclass(slots=True, frozen=True)
class SymbolMetricsContract:
    """Консервативно агрегированные метрики ликвидности и качества символа."""

    symbol: str
    exchange: str
    calculated_at: datetime
    spread_bps: Decimal
    top_of_book_depth_usd: Decimal
    depth_5bps_usd: Decimal
    latency_ms: Decimal
    coverage_ratio: Decimal
    data_freshness_ms: int
    quality_score: Decimal
    funding_8h: Decimal | None = None
    volume_24h_usd: Decimal | None = None
    open_interest_usd: Decimal | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def identity(self) -> SymbolIdentity:
        """Вернуть canonical identity symbol metrics."""
        return build_symbol_identity(self.symbol, self.exchange)


@dataclass(slots=True, frozen=True)
class DataQualitySignal:
    """Typed signal о нарушении качества market data."""

    symbol: str
    exchange: str
    issue_type: DataQualityIssueType
    severity: DataQualitySeverity
    detected_at: datetime
    feed: str
    gap_duration_ms: int | None = None
    staleness_ms: int | None = None
    outlier_score: Decimal | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def identity(self) -> SymbolIdentity:
        """Вернуть canonical identity quality signal."""
        return build_symbol_identity(self.symbol, self.exchange)


@dataclass(slots=True, frozen=True)
class AdmissibleSymbolContract:
    """Символ, допущенный к торговле текущим universe policy."""

    symbol: SymbolContract
    metrics: SymbolMetricsContract
    admitted_at: datetime
    admission_reasons: tuple[UniverseAdmissionReason, ...]
    policy_tags: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class ExcludedUniverseSymbol:
    """Identity-aware запись символа, исключённого из admissible universe."""

    symbol: str
    exchange: str

    @property
    def identity(self) -> SymbolIdentity:
        """Вернуть canonical identity исключённого символа."""
        return build_symbol_identity(self.symbol, self.exchange)


@dataclass(slots=True, frozen=True)
class RankedUniverseEntry:
    """Контракт rank-ready записи universe без полной OpportunityEngine логики."""

    symbol: SymbolContract
    rank: int
    score: Decimal
    score_components: dict[str, Decimal] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class RawUniverseSnapshot:
    """Versioned snapshot всех обнаруженных символов."""

    version: int
    created_at: datetime
    symbols: tuple[SymbolContract, ...]


@dataclass(slots=True, frozen=True)
class AdmissibleUniverseSnapshot:
    """Versioned snapshot символов, прошедших admissibility filters."""

    version: int
    created_at: datetime
    symbols: tuple[AdmissibleSymbolContract, ...]
    confidence: Decimal | None = None
    excluded_symbols: tuple[ExcludedUniverseSymbol, ...] = ()

    def is_admissible(self, symbol: str, exchange: str | None = None) -> bool:
        """Проверить, входит ли symbol/exchange в admissible universe текущей версии."""
        if exchange is None:
            return any(item.symbol.symbol == symbol for item in self.symbols)
        return any(
            item.symbol.identity == build_symbol_identity(symbol, exchange)
            for item in self.symbols
        )


@dataclass(slots=True, frozen=True)
class RankedUniverseSnapshot:
    """Versioned snapshot ranked universe как future-ready contract."""

    version: int
    created_at: datetime
    entries: tuple[RankedUniverseEntry, ...]
    upstream_admissible_version: int
    ranking_model: str = "contract_only"


@dataclass(slots=True, frozen=True)
class UniverseQualityAssessment:
    """Операционная оценка качества текущего universe snapshot."""

    version: int
    measured_at: datetime
    confidence: Decimal
    state: UniverseConfidenceState
    raw_count: int
    admissible_count: int
    ranked_count: int = 0
    blocking_reasons: tuple[str, ...] = ()
    worst_symbols: tuple[str, ...] = ()

    def requires_degraded_mode(self) -> bool:
        """Проверить, требует ли текущее состояние деградации runtime."""
        return self.state != UniverseConfidenceState.READY
