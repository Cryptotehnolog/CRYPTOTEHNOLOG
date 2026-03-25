"""DTO модели для узкого position-expansion summary snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PositionExpansionAvailabilityItemDTO(BaseModel):
    """Краткое read-only представление surfaced availability/counter."""

    key: str
    label: str
    value: str
    status: str
    note: str | None = None


class PositionExpansionSummaryDTO(BaseModel):
    """Узкий read-only snapshot position-expansion summary для dashboard line."""

    module_status: str
    global_status: str
    lifecycle_state: str
    started: bool
    ready: bool
    tracked_context_keys: int
    tracked_expansion_keys: int
    expandable_keys: int
    abstained_keys: int
    rejected_keys: int
    invalidated_expansion_keys: int
    expired_expansion_keys: int
    last_decision_id: str | None = None
    last_expansion_id: str | None = None
    last_event_type: str | None = None
    active_position_expansion_path: str
    position_expansion_source: str
    freshness_state: str
    summary_note: str
    summary_reason: str | None = None
    availability: list[PositionExpansionAvailabilityItemDTO] = Field(default_factory=list)
