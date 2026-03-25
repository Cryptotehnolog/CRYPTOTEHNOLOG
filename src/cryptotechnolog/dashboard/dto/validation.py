"""DTO модели для узкого validation summary snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationAvailabilityItemDTO(BaseModel):
    """Краткое read-only представление surfaced validation availability/counter."""

    key: str
    label: str
    value: str
    status: str
    note: str | None = None


class ValidationSummaryDTO(BaseModel):
    """Узкий read-only snapshot validation summary для dashboard line."""

    module_status: str
    global_status: str
    lifecycle_state: str
    started: bool
    ready: bool
    tracked_contexts: int
    tracked_active_reviews: int
    tracked_historical_reviews: int
    last_review_id: str | None = None
    last_event_type: str | None = None
    active_validation_path: str
    validation_source: str
    freshness_state: str
    summary_note: str
    summary_reason: str | None = None
    availability: list[ValidationAvailabilityItemDTO] = Field(default_factory=list)
