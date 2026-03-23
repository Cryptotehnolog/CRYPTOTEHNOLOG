"""
Runtime boundary shape для Phase 20 Backtesting / Replay Foundation.

Этот модуль intentionally не реализует full replay engine.
Он фиксирует только:
- explicit runtime lifecycle shape;
- ingestion boundary для historical inputs;
- query/state-first surface;
- operator-visible diagnostics contract
для следующего шага `Replay Runtime Foundation`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from .events import HistoricalInputPayload, ReplayCandidatePayload, ReplayEventType
    from .models import HistoricalInputContract, ReplayCandidate, ReplayContext


type ReplayStateKey = str


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


class ReplayRuntime(Protocol):
    """Протокол explicit runtime boundary для будущего replay layer."""

    @property
    def is_started(self) -> bool:
        """Проверить, активирован ли runtime."""

    async def start(self) -> None:
        """Поднять runtime без hidden bootstrap."""

    async def stop(self) -> None:
        """Остановить runtime и очистить operator-visible state."""

    def ingest_historical_input(
        self,
        *,
        historical_input: HistoricalInputContract,
        reference_time: datetime,
    ) -> ReplayRuntimeUpdate:
        """Собрать replay context и обновить replay truth из historical input."""

    def get_context(self, key: ReplayStateKey) -> ReplayContext | None:
        """Вернуть последний replay context по state key."""

    def get_candidate(self, key: ReplayStateKey) -> ReplayCandidate | None:
        """Вернуть active replay candidate по state key."""

    def get_historical_candidate(self, key: ReplayStateKey) -> ReplayCandidate | None:
        """Вернуть historical replay candidate по state key."""

    def list_active_candidates(self) -> tuple[ReplayCandidate, ...]:
        """Вернуть все active replay candidates."""

    def list_historical_candidates(self) -> tuple[ReplayCandidate, ...]:
        """Вернуть все historical replay candidates."""

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-visible diagnostics truth."""

    def mark_degraded(self, reason: str) -> None:
        """Явно пометить runtime как degraded без смешения с bootstrap truth."""


def create_replay_runtime(
    config: ReplayRuntimeConfig | None = None,
) -> ReplayRuntime:
    """Явный runtime entrypoint replay layer для следующего implementation-step."""
    _ = config or ReplayRuntimeConfig()
    raise NotImplementedError(
        "Replay Runtime Foundation ещё не реализована; "
        "Phase 20 contract lock фиксирует только boundary shape."
    )


__all__ = [
    "ReplayRuntime",
    "ReplayRuntimeConfig",
    "ReplayRuntimeDiagnostics",
    "ReplayRuntimeLifecycleState",
    "ReplayRuntimeUpdate",
    "ReplayStateKey",
    "create_replay_runtime",
]
