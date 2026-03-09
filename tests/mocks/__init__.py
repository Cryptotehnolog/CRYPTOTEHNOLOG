"""
Mocks — Заглушки для тестирования.

Содержит mock-реализации интерфейсов из core.interfaces:
- MockLogger — мок логгера
- InMemoryOrderRepository — in-memory репозиторий ордеров
- InMemoryPositionRepository — in-memory репозиторий позиций
"""

from tests.mocks.logger import MockLogger
from tests.mocks.order_repository import InMemoryOrderRepository
from tests.mocks.position_repository import InMemoryPositionRepository
from tests.mocks.risk_limit_repository import InMemoryRiskLimitRepository

__all__ = [
    "InMemoryOrderRepository",
    "InMemoryPositionRepository",
    "InMemoryRiskLimitRepository",
    "MockLogger",
]
