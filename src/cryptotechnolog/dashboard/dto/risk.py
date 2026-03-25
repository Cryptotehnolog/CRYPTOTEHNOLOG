"""DTO модели для узкого risk summary snapshot панели."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RiskConstraintDTO(BaseModel):
    """Краткое read-only представление одного risk constraint."""

    key: str
    label: str
    value: str
    status: str
    note: str | None = None


class RiskSummaryDTO(BaseModel):
    """Узкий read-only snapshot risk summary для dashboard line."""

    module_status: str
    current_state: str
    global_status: str
    limiting_state: str
    trading_blocked: bool
    active_risk_path: str | None = None
    state_note: str
    summary_reason: str | None = None
    constraints: list[RiskConstraintDTO] = Field(default_factory=list)
