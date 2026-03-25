"""DTO модели для узкого strategy summary snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StrategyAvailabilityItemDTO(BaseModel):
    """Краткое read-only представление surfaced strategy availability/counter."""

    key: str
    label: str
    value: str
    status: str
    note: str | None = None


class StrategySummaryDTO(BaseModel):
    """Узкий read-only snapshot strategy summary для dashboard line."""

    module_status: str
    global_status: str
    lifecycle_state: str
    started: bool
    ready: bool
    tracked_context_keys: int
    tracked_candidate_keys: int
    actionable_candidate_keys: int
    last_signal_id: str | None = None
    last_candidate_id: str | None = None
    last_event_type: str | None = None
    active_strategy_path: str
    strategy_source: str
    freshness_state: str
    summary_note: str
    summary_reason: str | None = None
    availability: list[StrategyAvailabilityItemDTO] = Field(default_factory=list)
