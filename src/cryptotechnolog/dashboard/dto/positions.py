"""DTO модели для read-only open positions snapshot панели."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class OpenPositionDTO(BaseModel):
    """Узкое read-only представление одной открытой позиции."""

    position_id: str
    symbol: str
    exchange: str
    strategy: str | None = None
    side: str
    entry_price: Decimal
    quantity: Decimal
    initial_stop: Decimal
    current_stop: Decimal
    current_risk_usd: Decimal
    current_risk_r: Decimal
    current_price: Decimal
    unrealized_pnl_usd: Decimal
    unrealized_pnl_percent: Decimal
    trailing_state: str
    opened_at: str
    updated_at: str


class OpenPositionsDTO(BaseModel):
    """Узкий read-only snapshot списка открытых позиций."""

    positions: list[OpenPositionDTO] = Field(default_factory=list)


class PositionHistoryRecordDTO(BaseModel):
    """Узкое read-only представление одной записи истории закрытой позиции."""

    position_id: str
    symbol: str
    exchange: str
    strategy: str | None = None
    side: str
    entry_price: Decimal
    quantity: Decimal
    initial_stop: Decimal
    current_stop: Decimal
    trailing_state: str
    opened_at: str
    closed_at: str
    realized_pnl_r: Decimal | None = None
    realized_pnl_usd: Decimal | None = None
    realized_pnl_percent: Decimal | None = None


class PositionHistoryDTO(BaseModel):
    """Узкий read-only snapshot истории закрытых позиций."""

    positions: list[PositionHistoryRecordDTO] = Field(default_factory=list)
