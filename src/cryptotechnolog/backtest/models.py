"""
Contract-first модели Phase 20 для narrow backtesting / replay layer.

Этот модуль фиксирует минимальный foundation scope:
- typed replay validity / window semantics;
- typed historical-input contract;
- typed replay context contract;
- typed replay candidate contract;
- replay semantics без analytics / reporting / dashboard / optimization ownership
  и без re-ownership соседних runtime layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from datetime import datetime

    from cryptotechnolog.market_data import MarketDataTimeframe


class ReplayDecision(StrEnum):
    """Нормализованный decision foundation replay layer."""

    REPLAY = "replay"
    ABSTAIN = "abstain"


class ReplayStatus(StrEnum):
    """Lifecycle-состояние replay candidate."""

    CANDIDATE = "candidate"
    REPLAYED = "replayed"
    ABSTAINED = "abstained"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class ReplayValidityStatus(StrEnum):
    """Состояние готовности replay context или candidate."""

    VALID = "valid"
    WARMING = "warming"
    INVALID = "invalid"


class ReplayIntegrityStatus(StrEnum):
    """Integrity-статус для narrow replay input/replay truth."""

    CLEAN = "clean"
    REGRESSED = "regressed"
    DRIFTED = "drifted"


class HistoricalInputKind(StrEnum):
    """Тип historical input для replay foundation."""

    TICK_STREAM = "tick_stream"
    BAR_STREAM = "bar_stream"
    RUNTIME_EVENT_STREAM = "runtime_event_stream"


class ReplayReasonCode(StrEnum):
    """Узкие reason semantics для foundation replay layer."""

    INPUT_WINDOW_READY = "input_window_ready"
    INPUT_WINDOW_INCOMPLETE = "input_window_incomplete"
    INPUT_WINDOW_INVALID = "input_window_invalid"
    INPUT_WINDOW_LOOKAHEAD = "input_window_lookahead"
    INPUT_WINDOW_REGRESSED = "input_window_regressed"
    INPUT_WINDOW_DRIFTED = "input_window_drifted"
    RECORDER_STATE_MISSING = "recorder_state_missing"
    VALIDATION_TRUTH_EXTERNAL = "validation_truth_external"
    PAPER_TRUTH_EXTERNAL = "paper_truth_external"
    REPLAY_EXECUTED = "replay_executed"
    REPLAY_ABSTAINED = "replay_abstained"
    REPLAY_INVALIDATED = "replay_invalidated"
    REPLAY_EXPIRED = "replay_expired"


class ReplaySource(StrEnum):
    """Нормализованный source для replay foundation."""

    HISTORICAL_INPUTS = "historical_inputs"


@dataclass(slots=True, frozen=True)
class ReplayValidity:
    """Typed semantics готовности replay context или candidate."""

    status: ReplayValidityStatus
    observed_inputs: int
    required_inputs: int
    missing_inputs: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.status == ReplayValidityStatus.VALID

    @property
    def is_warming(self) -> bool:
        return self.status == ReplayValidityStatus.WARMING

    @property
    def missing_inputs_count(self) -> int:
        return len(self.missing_inputs)

    @property
    def readiness_ratio(self) -> Decimal:
        if self.required_inputs <= 0:
            return Decimal("1")
        ratio = Decimal(self.observed_inputs) / Decimal(self.required_inputs)
        if ratio <= 0:
            return Decimal("0")
        if ratio >= 1:
            return Decimal("1")
        return ratio.quantize(Decimal("0.0001"))


@dataclass(slots=True, frozen=True)
class ReplayCoverageWindow:
    """Coverage window semantics для historical replay inputs."""

    start_at: datetime
    end_at: datetime
    observed_events: int
    expected_events: int

    def __post_init__(self) -> None:
        if self.end_at < self.start_at:
            raise ValueError("ReplayCoverageWindow требует end_at >= start_at")
        if self.observed_events < 0:
            raise ValueError("observed_events не может быть отрицательным")
        if self.expected_events < 0:
            raise ValueError("expected_events не может быть отрицательным")
        if self.observed_events > self.expected_events and self.expected_events > 0:
            raise ValueError("observed_events не может превышать expected_events")

    @property
    def duration_seconds(self) -> float:
        return (self.end_at - self.start_at).total_seconds()

    @property
    def coverage_ratio(self) -> Decimal:
        if self.expected_events <= 0:
            return Decimal("1")
        ratio = Decimal(self.observed_events) / Decimal(self.expected_events)
        if ratio <= 0:
            return Decimal("0")
        if ratio >= 1:
            return Decimal("1")
        return ratio.quantize(Decimal("0.0001"))


@dataclass(slots=True, frozen=True)
class ReplayFreshness:
    """Freshness semantics replay candidate."""

    generated_at: datetime
    expires_at: datetime | None = None

    @property
    def has_structurally_valid_expiry_window(self) -> bool:
        return self.expires_at is None or self.expires_at >= self.generated_at

    def is_expired_at(self, reference_time: datetime) -> bool:
        return self.expires_at is not None and reference_time >= self.expires_at


@dataclass(slots=True, frozen=True)
class ReplayIntegrity:
    """Typed integrity truth для replay foundation."""

    status: ReplayIntegrityStatus = ReplayIntegrityStatus.CLEAN
    reason: str | None = None
    reference_input_id: UUID | None = None

    @property
    def is_clean(self) -> bool:
        return self.status == ReplayIntegrityStatus.CLEAN


@dataclass(slots=True, frozen=True)
class HistoricalInputContract:
    """
    Typed historical-input contract для replay foundation.

    Контракт intentionally не описывает analytics, optimization или
    simulated execution ownership. Он только фиксирует deterministic
    ingest boundary для historical inputs.
    """

    input_id: UUID
    input_name: str
    symbol: str
    exchange: str
    source: ReplaySource
    kind: HistoricalInputKind
    coverage_window: ReplayCoverageWindow
    timeframe: MarketDataTimeframe | None = None
    source_reference: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source != ReplaySource.HISTORICAL_INPUTS:
            raise ValueError("HistoricalInputContract source должен быть HISTORICAL_INPUTS")

    @classmethod
    def candidate(
        cls,
        *,
        input_name: str,
        symbol: str,
        exchange: str,
        kind: HistoricalInputKind,
        coverage_window: ReplayCoverageWindow,
        timeframe: MarketDataTimeframe | None = None,
        source_reference: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> HistoricalInputContract:
        return cls(
            input_id=uuid4(),
            input_name=input_name,
            symbol=symbol,
            exchange=exchange,
            source=ReplaySource.HISTORICAL_INPUTS,
            kind=kind,
            coverage_window=coverage_window,
            timeframe=timeframe,
            source_reference=source_reference,
            metadata={} if metadata is None else metadata.copy(),
        )


@dataclass(slots=True, frozen=True)
class ReplayRecorderState:
    """Минимальный recorder/state contract для replay foundation."""

    recorded_events: int
    persisted_artifact: bool
    last_recorded_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.recorded_events < 0:
            raise ValueError("recorded_events не может быть отрицательным")


@dataclass(slots=True, frozen=True)
class ReplayContext:
    """
    Typed replay context поверх historical inputs.

    Replay layer может ссылаться на adjacent validation/paper truth,
    но не забирает ownership у Validation или Paper.
    """

    replay_name: str
    contour_name: str
    observed_at: datetime
    source: ReplaySource
    historical_input: HistoricalInputContract
    validity: ReplayValidity
    integrity: ReplayIntegrity = field(default_factory=ReplayIntegrity)
    validation_review_id: UUID | None = None
    paper_rehearsal_id: UUID | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source != ReplaySource.HISTORICAL_INPUTS:
            raise ValueError("ReplayContext source должен быть HISTORICAL_INPUTS")


@dataclass(slots=True, frozen=True)
class ReplayCandidate:
    """
    Typed replay/backtest output contract для Phase 20 foundation.

    Контракт intentionally не включает:
    - analytics / reporting ownership;
    - dashboard / operator semantics;
    - paper/live comparison ownership;
    - simulated Execution / OMS takeover;
    - research / optimization semantics.
    """

    replay_id: UUID
    contour_name: str
    replay_name: str
    symbol: str
    exchange: str
    source: ReplaySource
    freshness: ReplayFreshness
    coverage_window: ReplayCoverageWindow
    validity: ReplayValidity
    status: ReplayStatus
    decision: ReplayDecision
    historical_input_id: UUID | None = None
    timeframe: MarketDataTimeframe | None = None
    validation_review_id: UUID | None = None
    paper_rehearsal_id: UUID | None = None
    recorder_state: ReplayRecorderState | None = None
    reason_code: ReplayReasonCode | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.freshness.has_structurally_valid_expiry_window:
            raise ValueError("Replay output требует expires_at >= generated_at")
        self._validate_status_invariants()
        if (
            self.status in {ReplayStatus.EXPIRED, ReplayStatus.INVALIDATED}
            and self.validity.is_valid
        ):
            raise ValueError("EXPIRED/INVALIDATED replay candidate не может иметь VALID")

    def _validate_status_invariants(self) -> None:
        if self.status == ReplayStatus.REPLAYED:
            if self.decision != ReplayDecision.REPLAY:
                raise ValueError("REPLAYED candidate обязан иметь decision=REPLAY")
            if not self.validity.is_valid:
                raise ValueError("REPLAYED candidate требует validity=VALID")
            if self.historical_input_id is None:
                raise ValueError("REPLAYED candidate обязан ссылаться на historical input")
            return
        if self.status == ReplayStatus.ABSTAINED and self.decision != ReplayDecision.ABSTAIN:
            raise ValueError("ABSTAINED candidate обязан иметь decision=ABSTAIN")

    @property
    def is_replayed(self) -> bool:
        return (
            self.validity.is_valid
            and self.status == ReplayStatus.REPLAYED
            and self.decision == ReplayDecision.REPLAY
        )

    @property
    def is_abstained(self) -> bool:
        return self.status == ReplayStatus.ABSTAINED

    @classmethod
    def candidate(
        cls,
        *,
        contour_name: str,
        replay_name: str,
        symbol: str,
        exchange: str,
        source: ReplaySource,
        freshness: ReplayFreshness,
        coverage_window: ReplayCoverageWindow,
        validity: ReplayValidity,
        decision: ReplayDecision,
        status: ReplayStatus = ReplayStatus.CANDIDATE,
        historical_input_id: UUID | None = None,
        timeframe: MarketDataTimeframe | None = None,
        validation_review_id: UUID | None = None,
        paper_rehearsal_id: UUID | None = None,
        recorder_state: ReplayRecorderState | None = None,
        reason_code: ReplayReasonCode | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ReplayCandidate:
        return cls(
            replay_id=uuid4(),
            contour_name=contour_name,
            replay_name=replay_name,
            symbol=symbol,
            exchange=exchange,
            source=source,
            freshness=freshness,
            coverage_window=coverage_window,
            validity=validity,
            status=status,
            decision=decision,
            historical_input_id=historical_input_id,
            timeframe=timeframe,
            validation_review_id=validation_review_id,
            paper_rehearsal_id=paper_rehearsal_id,
            recorder_state=recorder_state,
            reason_code=reason_code,
            metadata={} if metadata is None else metadata.copy(),
        )


__all__ = [
    "HistoricalInputContract",
    "HistoricalInputKind",
    "ReplayCandidate",
    "ReplayContext",
    "ReplayCoverageWindow",
    "ReplayDecision",
    "ReplayFreshness",
    "ReplayIntegrity",
    "ReplayIntegrityStatus",
    "ReplayReasonCode",
    "ReplayRecorderState",
    "ReplaySource",
    "ReplayStatus",
    "ReplayValidity",
    "ReplayValidityStatus",
]
