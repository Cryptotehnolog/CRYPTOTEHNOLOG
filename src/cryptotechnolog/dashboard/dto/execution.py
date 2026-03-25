"""DTO модели для узкого execution summary snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExecutionAvailabilityItemDTO(BaseModel):
    """Краткое read-only представление surfaced execution availability/counter."""

    key: str
    label: str
    value: str
    status: str
    note: str | None = None


class ExecutionSummaryDTO(BaseModel):
    """Узкий read-only snapshot execution summary для dashboard line."""

    module_status: str
    global_status: str
    lifecycle_state: str
    started: bool
    ready: bool
    tracked_context_keys: int
    tracked_intent_keys: int
    executable_intent_keys: int
    last_candidate_id: str | None = None
    last_intent_id: str | None = None
    last_event_type: str | None = None
    active_execution_path: str
    execution_source: str
    freshness_state: str
    summary_note: str
    summary_reason: str | None = None
    availability: list[ExecutionAvailabilityItemDTO] = Field(default_factory=list)
