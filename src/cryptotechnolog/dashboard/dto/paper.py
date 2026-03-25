"""DTO модели для узкого paper summary snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaperAvailabilityItemDTO(BaseModel):
    """Краткое read-only представление surfaced paper availability/counter."""

    key: str
    label: str
    value: str
    status: str
    note: str | None = None


class PaperSummaryDTO(BaseModel):
    """Узкий read-only snapshot paper summary для dashboard line."""

    module_status: str
    global_status: str
    lifecycle_state: str
    started: bool
    ready: bool
    tracked_contexts: int
    tracked_active_rehearsals: int
    tracked_historical_rehearsals: int
    last_rehearsal_id: str | None = None
    last_event_type: str | None = None
    active_paper_path: str
    paper_source: str
    freshness_state: str
    summary_note: str
    summary_reason: str | None = None
    availability: list[PaperAvailabilityItemDTO] = Field(default_factory=list)
