"""
Dual Control Data Classes.

Дата-классы для реализации dual control (двойного контроля) -
механизма требующего подтверждения от двух операторов для
критических операций в торговой системе.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum, StrEnum
from typing import Any
import uuid

from cryptotechnolog.config import get_settings


class OperationType(Enum):
    """Типы операций требующих dual control."""

    SYSTEM_HALT = "system_halt"
    SYSTEM_RESUME = "system_resume"
    EMERGENCY_STOP = "emergency_stop"
    STATE_TRANSITION = "state_transition"
    CONFIG_CHANGE = "config_change"
    RISK_LIMIT_OVERRIDE = "risk_limit_override"


class RequestStatus(Enum):
    """Статус запроса dual control."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class Operator:
    """
    Оператор системы.

    Атрибуты:
        id: Уникальный идентификатор оператора
        name: Имя оператора
        role: Роль оператора (ADMIN, TRADER, VIEWER)
        token: Токен аутентификации (в реальной системе - хэш)
        is_active: Активен ли оператор
    """

    id: uuid.UUID
    name: str
    role: OperatorRole
    token: str
    is_active: bool = True


@dataclass
class DualControlRequest:
    """
    Запрос на выполнение критической операции.

    Требует подтверждения от второго оператора.

    Атрибуты:
        id: Уникальный идентификатор запроса
        operation_type: Тип операции
        requested_by: Оператор, запросивший операцию
        target_state: Целевое состояние (для state transition)
        status: Статус запроса
        requested_at: Время создания запроса
        expires_at: Время истечения (5 минут по умолчанию)
        approved_by: Оператор, подтвердивший операцию
        approved_at: Время подтверждения
        rejected_by: Оператор, отклонивший операцию
        rejected_at: Время отклонения
        rejection_reason: Причина отклонения
        metadata: Дополнительные метаданные
    """

    operation_type: OperationType
    requested_by: Operator
    target_state: str | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: RequestStatus = RequestStatus.PENDING
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC) + timedelta(minutes=5))
    approved_by: Operator | None = None
    approved_at: datetime | None = None
    rejected_by: Operator | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Проверить, истёк ли запрос."""
        return datetime.now(UTC) > self.expires_at

    def is_pending(self) -> bool:
        """Проверить, находится ли запрос в ожидании."""
        return self.status == RequestStatus.PENDING and not self.is_expired()

    def approve(self, operator: Operator) -> bool:
        """
        Подтвердить запрос.

        Аргументы:
            operator: Оператор, подтверждающий запрос

        Возвращает:
            True если подтверждение успешно
        """
        if not self.is_pending():
            return False

        if operator.id == self.requested_by.id:
            # Нельзя подтверждать свой собственный запрос
            return False

        self.status = RequestStatus.APPROVED
        self.approved_by = operator
        self.approved_at = datetime.now(UTC)
        return True

    def reject(self, operator: Operator, reason: str) -> bool:
        """
        Отклонить запрос.

        Аргументы:
            operator: Оператор, отклоняющий запрос
            reason: Причина отклонения

        Возвращает:
            True если отклонение успешно
        """
        if not self.is_pending():
            return False

        self.status = RequestStatus.REJECTED
        self.rejected_by = operator
        self.rejected_at = datetime.now(UTC)
        self.rejection_reason = reason
        return True

    def cancel(self) -> bool:
        """
        Отменить запрос (может только инициатор).

        Возвращает:
            True если отмена успешна
        """
        if not self.is_pending():
            return False

        self.status = RequestStatus.CANCELLED
        return True

    def expire(self) -> None:
        """Отметить запрос как истёкший."""
        if self.is_pending():
            self.status = RequestStatus.EXPIRED

    def to_dict(self) -> dict[str, Any]:
        """Конвертировать в словарь."""
        return {
            "id": str(self.id),
            "operation_type": self.operation_type.value,
            "requested_by": self.requested_by.name,
            "target_state": self.target_state,
            "status": self.status.value,
            "requested_at": self.requested_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "approved_by": self.approved_by.name if self.approved_by else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejected_by": self.rejected_by.name if self.rejected_by else None,
            "rejection_reason": self.rejection_reason,
            "metadata": self.metadata,
        }


# ==================== Constants ====================

DEFAULT_REQUEST_TIMEOUT_MINUTES = 5
MAX_REQUEST_TIMEOUT_MINUTES = 30
MIN_APPROVERS_FOR_CRITICAL = 2


# Роли операторов
class OperatorRole(StrEnum):
    """Роли операторов."""

    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"
    RISK_MANAGER = "risk_manager"


# Операции по уровню критичности
CRITICAL_OPERATIONS = {
    OperationType.EMERGENCY_STOP,
    OperationType.SYSTEM_HALT,
}

HIGH_RISK_OPERATIONS = {
    OperationType.RISK_LIMIT_OVERRIDE,
    OperationType.CONFIG_CHANGE,
}

LOW_RISK_OPERATIONS = {
    OperationType.SYSTEM_RESUME,
    OperationType.STATE_TRANSITION,
}

# All operations that require dual control
DUAL_CONTROL_OPERATIONS = CRITICAL_OPERATIONS | HIGH_RISK_OPERATIONS | LOW_RISK_OPERATIONS


# ==================== Dual Control Manager (заглушка для совместимости) ====================


class DualControlManager:
    """
    Менеджер dual control (двойного контроля).

    Заглушечная реализация для совместимости.
    Полная реализация будет в будущих фазах.
    """

    def __init__(self) -> None:
        """Инициализировать менеджер."""
        self.requests: dict[uuid.UUID, DualControlRequest] = {}

    def create_request(
        self,
        operation_type: OperationType,
        requested_by: Operator,
        target_state: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DualControlRequest:
        """
        Создать запрос на dual control.

        Аргументы:
            operation_type: Тип операции
            requested_by: Оператор, запросивший операцию
            target_state: Целевое состояние (для state transition)
            metadata: Дополнительные метаданные

        Возвращает:
            Созданный запрос
        """
        request_timeout_minutes = get_settings().manual_approval_timeout_minutes
        request = DualControlRequest(
            operation_type=operation_type,
            requested_by=requested_by,
            target_state=target_state,
            expires_at=datetime.now(UTC) + timedelta(minutes=request_timeout_minutes),
            metadata=metadata or {},
        )
        self.requests[request.id] = request
        return request

    def get_request(self, request_id: uuid.UUID) -> DualControlRequest | None:
        """Получить запрос по ID."""
        return self.requests.get(request_id)

    def approve_request(self, request_id: uuid.UUID, operator: Operator) -> bool:
        """Подтвердить запрос."""
        request = self.requests.get(request_id)
        if not request:
            return False
        return request.approve(operator)

    def reject_request(self, request_id: uuid.UUID, operator: Operator, reason: str) -> bool:
        """Отклонить запрос."""
        request = self.requests.get(request_id)
        if not request:
            return False
        return request.reject(operator, reason)

    def cancel_request(self, request_id: uuid.UUID) -> bool:
        """Отменить запрос."""
        request = self.requests.get(request_id)
        if not request:
            return False
        return request.cancel()

    def cleanup_expired(self) -> list[DualControlRequest]:
        """Очистить истёкшие запросы и вернуть список очищенных."""
        expired = []
        for request in list(self.requests.values()):
            if request.is_expired():
                request.expire()
                expired.append(request)
        return expired
