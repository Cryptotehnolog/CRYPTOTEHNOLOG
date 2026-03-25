"""DTO модели для узкого OMS summary snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OmsAvailabilityItemDTO(BaseModel):
    """Краткое read-only представление surfaced OMS availability/counter."""

    key: str
    label: str
    value: str
    status: str
    note: str | None = None


class OmsSummaryDTO(BaseModel):
    """Узкий read-only snapshot OMS summary для dashboard line."""

    module_status: str
    global_status: str
    lifecycle_state: str
    started: bool
    ready: bool
    tracked_contexts: int
    tracked_active_orders: int
    tracked_historical_orders: int
    last_intent_id: str | None = None
    last_order_id: str | None = None
    last_event_type: str | None = None
    active_oms_path: str
    oms_source: str
    freshness_state: str
    summary_note: str
    summary_reason: str | None = None
    availability: list[OmsAvailabilityItemDTO] = Field(default_factory=list)
