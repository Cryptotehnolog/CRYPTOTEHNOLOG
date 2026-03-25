"""DTO модели для узкого backtest summary snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BacktestAvailabilityItemDTO(BaseModel):
    """Краткое read-only представление surfaced backtest availability/counter."""

    key: str
    label: str
    value: str
    status: str
    note: str | None = None


class BacktestSummaryDTO(BaseModel):
    """Узкий read-only snapshot backtest summary для dashboard line."""

    module_status: str
    global_status: str
    lifecycle_state: str
    started: bool
    ready: bool
    tracked_inputs: int
    tracked_contexts: int
    tracked_active_replays: int
    tracked_historical_replays: int
    last_replay_id: str | None = None
    last_event_type: str | None = None
    active_backtest_path: str
    backtest_source: str
    freshness_state: str
    summary_note: str
    summary_reason: str | None = None
    availability: list[BacktestAvailabilityItemDTO] = Field(default_factory=list)
