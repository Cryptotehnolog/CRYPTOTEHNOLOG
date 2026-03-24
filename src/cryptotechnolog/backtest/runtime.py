"""
Узкий explicit runtime foundation для Phase 20 Backtesting / Replay Foundation.

Этот runtime:
- стартует и останавливается явно;
- не делает hidden bootstrap;
- принимает explicit historical inputs;
- собирает typed replay context внутри replay layer;
- поддерживает один минимальный deterministic replay contour;
- хранит query/state-first truth и operator-visible diagnostics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

from .events import (
    HistoricalInputPayload,
    ReplayCandidatePayload,
    ReplayEventType,
)
from .models import (
    HistoricalInputContract,
    ReplayCandidate,
    ReplayContext,
    ReplayDecision,
    ReplayFreshness,
    ReplayReasonCode,
    ReplayRecorderState,
    ReplaySource,
    ReplayStatus,
    ReplayValidity,
    ReplayValidityStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable


type ReplayStateKey = tuple[str, str, str]


class ReplayRuntimeLifecycleState(StrEnum):
    """Lifecycle-состояние replay runtime."""

    NOT_STARTED = "not_started"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(slots=True, frozen=True)
class ReplayRuntimeConfig:
    """Typed runtime-конфигурация replay foundation."""

    contour_name: str = "phase20_replay_contour"
    replay_name: str = "phase20_backtest"
    max_replay_age_seconds: int = 3600

    def __post_init__(self) -> None:
        if self.max_replay_age_seconds <= 0:
            raise ValueError("max_replay_age_seconds должен быть положительным")


@dataclass(slots=True)
class ReplayRuntimeDiagnostics:
    """Operator-visible diagnostics contract replay runtime."""

    started: bool = False
    ready: bool = False
    lifecycle_state: ReplayRuntimeLifecycleState = ReplayRuntimeLifecycleState.NOT_STARTED
    tracked_inputs: int = 0
    tracked_contexts: int = 0
    tracked_active_replays: int = 0
    tracked_historical_replays: int = 0
    last_replay_id: str | None = None
    last_event_type: str | None = None
    last_failure_reason: str | None = None
    readiness_reasons: list[str] = field(default_factory=list)
    degraded_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["lifecycle_state"] = self.lifecycle_state.value
        return result


@dataclass(slots=True, frozen=True)
class ReplayRuntimeUpdate:
    """Typed update contract replay runtime foundation."""

    historical_input: HistoricalInputContract | None
    context: ReplayContext | None
    replay_candidate: ReplayCandidate | None
    event_type: ReplayEventType | None
    emitted_input_payload: HistoricalInputPayload | None = None
    emitted_candidate_payload: ReplayCandidatePayload | None = None


class ReplayRuntime:
    """Explicit runtime foundation для replay/backtest layer Phase 20."""

    _TERMINAL_STATUSES: ClassVar[set[ReplayStatus]] = {
        ReplayStatus.INVALIDATED,
        ReplayStatus.EXPIRED,
    }

    def __init__(
        self,
        config: ReplayRuntimeConfig | None = None,
        *,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.config = config or ReplayRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._diagnostics = ReplayRuntimeDiagnostics()
        self._started = False
        self._inputs: dict[ReplayStateKey, HistoricalInputContract] = {}
        self._contexts: dict[ReplayStateKey, ReplayContext] = {}
        self._active_replays: dict[ReplayStateKey, ReplayCandidate] = {}
        self._historical_replays: dict[ReplayStateKey, ReplayCandidate] = {}
        self._replay_key_by_id: dict[UUID, ReplayStateKey] = {}
        self._push_diagnostics()

    @property
    def is_started(self) -> bool:
        """Проверить, активирован ли runtime."""
        return self._started

    async def start(self) -> None:
        """Поднять runtime без hidden bootstrap."""
        if self._started:
            return
        self._started = True
        self._refresh_diagnostics(
            lifecycle_state=ReplayRuntimeLifecycleState.WARMING,
            ready=False,
            last_failure_reason=None,
            readiness_reasons=("no_replay_processed",),
            degraded_reasons=(),
        )

    async def stop(self) -> None:
        """Остановить runtime и очистить operator-visible state."""
        if not self._started:
            return
        self._started = False
        self._inputs = {}
        self._contexts = {}
        self._active_replays = {}
        self._historical_replays = {}
        self._replay_key_by_id = {}
        self._refresh_diagnostics(
            lifecycle_state=ReplayRuntimeLifecycleState.STOPPED,
            ready=False,
            last_replay_id=None,
            last_event_type=None,
            last_failure_reason=None,
            readiness_reasons=("runtime_stopped",),
            degraded_reasons=(),
        )

    def ingest_historical_input(
        self,
        *,
        historical_input: HistoricalInputContract,
        reference_time: datetime,
    ) -> ReplayRuntimeUpdate:
        """Собрать replay context и обновить replay truth из historical input."""
        self._ensure_started()
        key = self._resolve_state_key(historical_input)
        self._inputs[key] = historical_input
        emitted_input_payload = HistoricalInputPayload.from_input(historical_input)

        validity, reason_code = self._build_validity(historical_input=historical_input)
        context = self._assemble_replay_context(
            historical_input=historical_input,
            validity=validity,
            reference_time=reference_time,
        )
        self._contexts[key] = context

        update = self._build_update_for_context(
            key=key,
            context=context,
            historical_input=historical_input,
            reference_time=reference_time,
            reason_code=reason_code,
            emitted_input_payload=emitted_input_payload,
        )
        self._push_diagnostics()
        return update

    def expire_candidates(self, *, reference_time: datetime) -> tuple[ReplayCandidate, ...]:
        """Перевести устаревшие active replay candidates в EXPIRED."""
        expired: list[ReplayCandidate] = []
        for key, candidate in tuple(self._active_replays.items()):
            if not candidate.freshness.is_expired_at(reference_time):
                continue
            expired_candidate = replace(
                candidate,
                status=ReplayStatus.EXPIRED,
                decision=ReplayDecision.ABSTAIN,
                validity=ReplayValidity(
                    status=ReplayValidityStatus.INVALID,
                    observed_inputs=candidate.validity.observed_inputs,
                    required_inputs=candidate.validity.required_inputs,
                    missing_inputs=candidate.validity.missing_inputs,
                    invalid_reason="replay_candidate_expired",
                ),
                reason_code=ReplayReasonCode.REPLAY_EXPIRED,
            )
            self._move_to_historical(key=key, candidate=expired_candidate)
            expired.append(expired_candidate)
        if expired:
            self._refresh_diagnostics(
                lifecycle_state=ReplayRuntimeLifecycleState.WARMING,
                ready=not self._diagnostics.degraded_reasons and bool(self._active_replays),
                last_replay_id=str(expired[-1].replay_id),
                last_event_type=None,
                last_failure_reason="replay_candidate_expired",
                readiness_reasons=(("no_active_replay",) if not self._active_replays else ()),
            )
        return tuple(expired)

    def get_input(self, key: ReplayStateKey) -> HistoricalInputContract | None:
        """Вернуть tracked historical input по state key."""
        return self._inputs.get(key)

    def list_inputs(self) -> tuple[HistoricalInputContract, ...]:
        """Вернуть все tracked historical inputs."""
        return tuple(self._inputs.values())

    def get_context(self, key: ReplayStateKey) -> ReplayContext | None:
        """Вернуть последний replay context по state key."""
        return self._contexts.get(key)

    def get_candidate(self, key: ReplayStateKey) -> ReplayCandidate | None:
        """Вернуть active replay candidate по state key."""
        return self._active_replays.get(key)

    def get_historical_candidate(self, key: ReplayStateKey) -> ReplayCandidate | None:
        """Вернуть historical replay candidate по state key."""
        return self._historical_replays.get(key)

    def list_active_candidates(self) -> tuple[ReplayCandidate, ...]:
        """Вернуть все active replay candidates."""
        return tuple(self._active_replays.values())

    def list_historical_candidates(self) -> tuple[ReplayCandidate, ...]:
        """Вернуть все historical replay candidates."""
        return tuple(self._historical_replays.values())

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-visible diagnostics truth."""
        return self._diagnostics.to_dict()

    def mark_degraded(self, reason: str) -> None:
        """Явно пометить runtime как degraded без смешения с bootstrap truth."""
        reasons = tuple(dict.fromkeys((*self._diagnostics.degraded_reasons, reason)))
        self._refresh_diagnostics(
            lifecycle_state=ReplayRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_failure_reason=reason,
            degraded_reasons=reasons,
        )

    def _build_update_for_context(
        self,
        *,
        key: ReplayStateKey,
        context: ReplayContext,
        historical_input: HistoricalInputContract,
        reference_time: datetime,
        reason_code: ReplayReasonCode,
        emitted_input_payload: HistoricalInputPayload,
    ) -> ReplayRuntimeUpdate:
        existing = self._active_replays.get(key)
        freshness = self._build_freshness(reference_time=reference_time)
        recorder_state = self._extract_recorder_state(historical_input=historical_input)

        if context.validity.is_warming:
            candidate = ReplayCandidate.candidate(
                contour_name=self.config.contour_name,
                replay_name=self.config.replay_name,
                symbol=context.historical_input.symbol,
                exchange=context.historical_input.exchange,
                source=context.source,
                freshness=freshness,
                coverage_window=context.historical_input.coverage_window,
                validity=context.validity,
                decision=ReplayDecision.ABSTAIN,
                status=ReplayStatus.CANDIDATE,
                historical_input_id=context.historical_input.input_id,
                timeframe=context.historical_input.timeframe,
                validation_review_id=context.validation_review_id,
                paper_rehearsal_id=context.paper_rehearsal_id,
                recorder_state=recorder_state,
                reason_code=reason_code,
            )
            self._active_replays[key] = candidate
            self._replay_key_by_id[candidate.replay_id] = key
            emitted_candidate_payload = ReplayCandidatePayload.from_candidate(candidate)
            self._refresh_diagnostics(
                lifecycle_state=ReplayRuntimeLifecycleState.WARMING,
                ready=False,
                last_replay_id=str(candidate.replay_id),
                last_event_type=ReplayEventType.REPLAY_CANDIDATE_UPDATED.value,
                last_failure_reason=None,
                readiness_reasons=tuple(context.validity.missing_inputs)
                or ("replay_context_incomplete",),
            )
            return ReplayRuntimeUpdate(
                historical_input=historical_input,
                context=context,
                replay_candidate=candidate,
                event_type=ReplayEventType.REPLAY_CANDIDATE_UPDATED,
                emitted_input_payload=emitted_input_payload,
                emitted_candidate_payload=emitted_candidate_payload,
            )

        if context.validity.is_valid:
            candidate = ReplayCandidate.candidate(
                contour_name=self.config.contour_name,
                replay_name=self.config.replay_name,
                symbol=context.historical_input.symbol,
                exchange=context.historical_input.exchange,
                source=context.source,
                freshness=freshness,
                coverage_window=context.historical_input.coverage_window,
                validity=context.validity,
                decision=ReplayDecision.REPLAY,
                status=ReplayStatus.REPLAYED,
                historical_input_id=context.historical_input.input_id,
                timeframe=context.historical_input.timeframe,
                validation_review_id=context.validation_review_id,
                paper_rehearsal_id=context.paper_rehearsal_id,
                recorder_state=recorder_state,
                reason_code=ReplayReasonCode.REPLAY_EXECUTED,
            )
            self._active_replays[key] = candidate
            self._replay_key_by_id[candidate.replay_id] = key
            emitted_candidate_payload = ReplayCandidatePayload.from_candidate(candidate)
            self._refresh_diagnostics(
                lifecycle_state=ReplayRuntimeLifecycleState.READY,
                ready=True,
                last_replay_id=str(candidate.replay_id),
                last_event_type=ReplayEventType.REPLAY_EXECUTED.value,
                last_failure_reason=None,
                readiness_reasons=(),
                degraded_reasons=(),
            )
            return ReplayRuntimeUpdate(
                historical_input=historical_input,
                context=context,
                replay_candidate=candidate,
                event_type=ReplayEventType.REPLAY_EXECUTED,
                emitted_input_payload=emitted_input_payload,
                emitted_candidate_payload=emitted_candidate_payload,
            )

        if existing is not None:
            invalidated = replace(
                existing,
                status=ReplayStatus.INVALIDATED,
                decision=ReplayDecision.ABSTAIN,
                validity=context.validity,
                reason_code=ReplayReasonCode.REPLAY_INVALIDATED,
            )
            self._move_to_historical(key=key, candidate=invalidated)
            emitted_candidate_payload = ReplayCandidatePayload.from_candidate(invalidated)
            self._refresh_diagnostics(
                lifecycle_state=ReplayRuntimeLifecycleState.DEGRADED,
                ready=False,
                last_replay_id=str(invalidated.replay_id),
                last_event_type=ReplayEventType.REPLAY_INVALIDATED.value,
                last_failure_reason=context.validity.invalid_reason,
                degraded_reasons=(context.validity.invalid_reason or "historical_input_invalid",),
                readiness_reasons=("replay_context_invalid",),
            )
            return ReplayRuntimeUpdate(
                historical_input=historical_input,
                context=context,
                replay_candidate=invalidated,
                event_type=ReplayEventType.REPLAY_INVALIDATED,
                emitted_input_payload=emitted_input_payload,
                emitted_candidate_payload=emitted_candidate_payload,
            )

        candidate = ReplayCandidate.candidate(
            contour_name=self.config.contour_name,
            replay_name=self.config.replay_name,
            symbol=context.historical_input.symbol,
            exchange=context.historical_input.exchange,
            source=context.source,
            freshness=freshness,
            coverage_window=context.historical_input.coverage_window,
            validity=context.validity,
            decision=ReplayDecision.ABSTAIN,
            status=ReplayStatus.ABSTAINED,
            historical_input_id=context.historical_input.input_id,
            timeframe=context.historical_input.timeframe,
            validation_review_id=context.validation_review_id,
            paper_rehearsal_id=context.paper_rehearsal_id,
            recorder_state=recorder_state,
            reason_code=ReplayReasonCode.REPLAY_ABSTAINED,
        )
        self._active_replays[key] = candidate
        self._replay_key_by_id[candidate.replay_id] = key
        emitted_candidate_payload = ReplayCandidatePayload.from_candidate(candidate)
        self._refresh_diagnostics(
            lifecycle_state=ReplayRuntimeLifecycleState.DEGRADED,
            ready=False,
            last_replay_id=str(candidate.replay_id),
            last_event_type=ReplayEventType.REPLAY_ABSTAINED.value,
            last_failure_reason=context.validity.invalid_reason,
            degraded_reasons=(context.validity.invalid_reason or "historical_input_invalid",),
            readiness_reasons=("replay_context_invalid",),
        )
        return ReplayRuntimeUpdate(
            historical_input=historical_input,
            context=context,
            replay_candidate=candidate,
            event_type=ReplayEventType.REPLAY_ABSTAINED,
            emitted_input_payload=emitted_input_payload,
            emitted_candidate_payload=emitted_candidate_payload,
        )

    def _build_validity(
        self,
        *,
        historical_input: HistoricalInputContract,
    ) -> tuple[ReplayValidity, ReplayReasonCode]:
        window = historical_input.coverage_window
        if window.expected_events <= 0 or window.observed_events <= 0:
            return (
                ReplayValidity(
                    status=ReplayValidityStatus.INVALID,
                    observed_inputs=0,
                    required_inputs=1,
                    invalid_reason="historical_input_empty_or_invalid",
                ),
                ReplayReasonCode.INPUT_WINDOW_INVALID,
            )
        if window.coverage_ratio < 1:
            return (
                ReplayValidity(
                    status=ReplayValidityStatus.WARMING,
                    observed_inputs=0,
                    required_inputs=1,
                    missing_inputs=("coverage_window_incomplete",),
                ),
                ReplayReasonCode.INPUT_WINDOW_INCOMPLETE,
            )
        return (
            ReplayValidity(
                status=ReplayValidityStatus.VALID,
                observed_inputs=1,
                required_inputs=1,
            ),
            ReplayReasonCode.INPUT_WINDOW_READY,
        )

    def _build_freshness(self, *, reference_time: datetime) -> ReplayFreshness:
        return ReplayFreshness(
            generated_at=reference_time,
            expires_at=reference_time + timedelta(seconds=self.config.max_replay_age_seconds),
        )

    def _assemble_replay_context(
        self,
        *,
        historical_input: HistoricalInputContract,
        validity: ReplayValidity,
        reference_time: datetime,
    ) -> ReplayContext:
        """Собрать typed ReplayContext внутри replay layer."""
        metadata = historical_input.metadata.copy()
        validation_review_id = self._coerce_uuid(metadata.pop("validation_review_id", None))
        paper_rehearsal_id = self._coerce_uuid(metadata.pop("paper_rehearsal_id", None))
        return ReplayContext(
            replay_name=self.config.replay_name,
            contour_name=self.config.contour_name,
            observed_at=reference_time,
            source=ReplaySource.HISTORICAL_INPUTS,
            historical_input=historical_input,
            validity=validity,
            validation_review_id=validation_review_id,
            paper_rehearsal_id=paper_rehearsal_id,
            metadata=metadata,
        )

    @staticmethod
    def _resolve_state_key(historical_input: HistoricalInputContract) -> ReplayStateKey:
        timeframe_or_kind = (
            historical_input.timeframe.value
            if historical_input.timeframe is not None
            else historical_input.kind.value
        )
        return (
            historical_input.symbol,
            historical_input.exchange,
            timeframe_or_kind,
        )

    @staticmethod
    def _coerce_uuid(value: object) -> UUID | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            return UUID(value)
        raise ValueError("validation/paper references должны быть UUID или UUID string")

    @staticmethod
    def _extract_recorder_state(
        historical_input: HistoricalInputContract,
    ) -> ReplayRecorderState | None:
        metadata = historical_input.metadata
        if "recorded_events" not in metadata and "persisted_artifact" not in metadata:
            return None
        last_recorded_at = metadata.get("last_recorded_at")
        if last_recorded_at is not None and not isinstance(last_recorded_at, datetime):
            raise ValueError("last_recorded_at должен быть datetime")
        recorded_events = metadata.get("recorded_events", 0)
        if not isinstance(recorded_events, int):
            raise ValueError("recorded_events должен быть int")
        return ReplayRecorderState(
            recorded_events=recorded_events,
            persisted_artifact=bool(metadata.get("persisted_artifact", False)),
            last_recorded_at=last_recorded_at,
        )

    def _move_to_historical(
        self,
        *,
        key: ReplayStateKey,
        candidate: ReplayCandidate,
    ) -> None:
        self._historical_replays[key] = candidate
        self._replay_key_by_id[candidate.replay_id] = key
        self._active_replays.pop(key, None)

    def _ensure_started(self) -> None:
        if not self._started:
            raise RuntimeError("Replay runtime должен быть явно запущен перед ingest")

    def _refresh_diagnostics(
        self,
        *,
        lifecycle_state: ReplayRuntimeLifecycleState | None = None,
        ready: bool | None = None,
        last_replay_id: str | None = None,
        last_event_type: str | None = None,
        last_failure_reason: str | None = None,
        readiness_reasons: tuple[str, ...] | None = None,
        degraded_reasons: tuple[str, ...] | None = None,
    ) -> None:
        if lifecycle_state is not None:
            self._diagnostics.lifecycle_state = lifecycle_state
        self._diagnostics.started = self._started
        if ready is not None:
            self._diagnostics.ready = ready
        self._diagnostics.tracked_inputs = len(self._inputs)
        self._diagnostics.tracked_contexts = len(self._contexts)
        self._diagnostics.tracked_active_replays = len(self._active_replays)
        self._diagnostics.tracked_historical_replays = len(self._historical_replays)
        if last_replay_id is not None:
            self._diagnostics.last_replay_id = last_replay_id
        if last_event_type is not None:
            self._diagnostics.last_event_type = last_event_type
        self._diagnostics.last_failure_reason = last_failure_reason
        if readiness_reasons is not None:
            self._diagnostics.readiness_reasons = list(readiness_reasons)
        if degraded_reasons is not None:
            self._diagnostics.degraded_reasons = list(degraded_reasons)
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self._diagnostics.to_dict())


def create_replay_runtime(
    config: ReplayRuntimeConfig | None = None,
    *,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> ReplayRuntime:
    """Явный factory runtime entrypoint replay layer."""
    return ReplayRuntime(config, diagnostics_sink=diagnostics_sink)


__all__ = [
    "ReplayRuntime",
    "ReplayRuntimeConfig",
    "ReplayRuntimeDiagnostics",
    "ReplayRuntimeLifecycleState",
    "ReplayRuntimeUpdate",
    "ReplayStateKey",
    "create_replay_runtime",
]
