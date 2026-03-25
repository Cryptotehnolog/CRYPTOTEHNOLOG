"""DTO модели для узкого orchestration summary snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OrchestrationAvailabilityItemDTO(BaseModel):
    """Краткое read-only представление surfaced orchestration availability/counter."""

    key: str
    label: str
    value: str
    status: str
    note: str | None = None


class OrchestrationSummaryDTO(BaseModel):
    """Узкий read-only snapshot orchestration summary для dashboard line."""

    module_status: str
    global_status: str
    lifecycle_state: str
    started: bool
    ready: bool
    tracked_context_keys: int
    tracked_decision_keys: int
    forwarded_keys: int
    abstained_keys: int
    invalidated_decision_keys: int
    expired_decision_keys: int
    last_selection_id: str | None = None
    last_decision_id: str | None = None
    last_event_type: str | None = None
    active_orchestration_path: str
    orchestration_source: str
    freshness_state: str
    summary_note: str
    summary_reason: str | None = None
    availability: list[OrchestrationAvailabilityItemDTO] = Field(default_factory=list)
