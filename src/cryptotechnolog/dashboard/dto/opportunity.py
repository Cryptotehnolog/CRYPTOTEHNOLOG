"""DTO модели для узкого opportunity summary snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OpportunityAvailabilityItemDTO(BaseModel):
    """Краткое read-only представление surfaced opportunity availability/counter."""

    key: str
    label: str
    value: str
    status: str
    note: str | None = None


class OpportunitySummaryDTO(BaseModel):
    """Узкий read-only snapshot opportunity summary для dashboard line."""

    module_status: str
    global_status: str
    lifecycle_state: str
    started: bool
    ready: bool
    tracked_context_keys: int
    tracked_selection_keys: int
    selected_keys: int
    last_intent_id: str | None = None
    last_selection_id: str | None = None
    last_event_type: str | None = None
    active_opportunity_path: str
    opportunity_source: str
    freshness_state: str
    summary_note: str
    summary_reason: str | None = None
    availability: list[OpportunityAvailabilityItemDTO] = Field(default_factory=list)
