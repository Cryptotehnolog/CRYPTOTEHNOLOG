"""FastAPI router для read-only dashboard snapshot endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from cryptotechnolog.config import get_logger

from ..dto.overview import OverviewSnapshotDTO

if TYPE_CHECKING:
    from ..facade.overview_facade import OverviewFacade

logger = get_logger(__name__)


def create_dashboard_router(facade: OverviewFacade) -> APIRouter:
    """
    Создать router панели управления.

    Аргументы:
        facade: Facade для агрегации overview snapshot.
    """
    router = APIRouter(prefix="/dashboard", tags=["dashboard"])

    @router.get(
        "/overview",
        response_model=OverviewSnapshotDTO,
        summary="Получить snapshot overview панели",
    )
    async def get_overview_snapshot() -> OverviewSnapshotDTO:
        logger.debug("Запрошен overview snapshot панели")
        return await facade.get_overview_snapshot()

    return router
