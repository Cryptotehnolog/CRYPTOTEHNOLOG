"""DTO модели для узкого signals summary snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SignalAvailabilityItemDTO(BaseModel):
    """Краткое read-only представление surfaced signal availability/counter."""

    key: str
    label: str
    value: str
    status: str
    note: str | None = None


class SignalsSummaryDTO(BaseModel):
    """Узкий read-only snapshot signal summary для dashboard line."""

    module_status: str
    global_status: str
    lifecycle_state: str
    started: bool
    ready: bool
    tracked_signal_keys: int
    active_signal_keys: int
    last_signal_id: str | None = None
    last_event_type: str | None = None
    last_context_at: str | None = None
    active_signal_path: str
    freshness_state: str
    summary_note: str
    summary_reason: str | None = None
    availability: list[SignalAvailabilityItemDTO] = Field(default_factory=list)
