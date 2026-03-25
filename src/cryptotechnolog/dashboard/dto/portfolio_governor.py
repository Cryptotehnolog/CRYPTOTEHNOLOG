"""DTO модели для узкого portfolio-governor summary snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PortfolioGovernorAvailabilityItemDTO(BaseModel):
    """Краткое read-only представление surfaced availability/counter."""

    key: str
    label: str
    value: str
    status: str
    note: str | None = None


class PortfolioGovernorSummaryDTO(BaseModel):
    """Узкий read-only snapshot portfolio-governor summary для dashboard line."""

    module_status: str
    global_status: str
    lifecycle_state: str
    started: bool
    ready: bool
    tracked_context_keys: int
    tracked_governor_keys: int
    approved_keys: int
    abstained_keys: int
    rejected_keys: int
    invalidated_governor_keys: int
    expired_governor_keys: int
    last_expansion_id: str | None = None
    last_governor_id: str | None = None
    last_event_type: str | None = None
    active_portfolio_governor_path: str
    portfolio_governor_source: str
    freshness_state: str
    summary_note: str
    summary_reason: str | None = None
    availability: list[PortfolioGovernorAvailabilityItemDTO] = Field(default_factory=list)
