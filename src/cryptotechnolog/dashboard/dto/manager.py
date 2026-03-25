"""DTO модели для узкого manager summary snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ManagerAvailabilityItemDTO(BaseModel):
    """Краткое read-only представление surfaced manager availability/counter."""

    key: str
    label: str
    value: str
    status: str
    note: str | None = None


class ManagerSummaryDTO(BaseModel):
    """Узкий read-only snapshot manager summary для dashboard line."""

    module_status: str
    global_status: str
    lifecycle_state: str
    started: bool
    ready: bool
    tracked_contexts: int
    tracked_active_workflows: int
    tracked_historical_workflows: int
    last_workflow_id: str | None = None
    last_event_type: str | None = None
    active_manager_path: str
    manager_source: str
    freshness_state: str
    summary_note: str
    summary_reason: str | None = None
    availability: list[ManagerAvailabilityItemDTO] = Field(default_factory=list)
