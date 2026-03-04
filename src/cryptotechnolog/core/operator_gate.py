"""
Operator Gate Implementation.

Шлюз оператора - механизм двойного контроля (dual control) для
критических операций в торговой системе CRYPTOTEHNOLOG.

Особенности:
- Требуется подтверждение от двух операторов для критических операций
- Request/approval workflow
- Timeout 5 минут по умолчанию
- Интеграция с Event Bus
- Все на РУССКОМ языке
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
import threading
from typing import TYPE_CHECKING, Any
import uuid

from cryptotechnolog.config import get_logger

# Верхнеуровневый импорт EnhancedEventBus
from .enhanced_event_bus import EnhancedEventBus

from .dual_control import (
    CRITICAL_OPERATIONS,
    DEFAULT_REQUEST_TIMEOUT_MINUTES,
    DUAL_CONTROL_OPERATIONS,
    DualControlRequest,
    OperationType,
    Operator,
    OperatorRole,
)
from .event import Event, Priority, SystemEventSource, SystemEventType
from .enhanced_event_bus import EnhancedEventBus
from .event_publisher import publish_event

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)


# ==================== Auth Stub ====================


class TokenAuthenticator:
    """
    Stub аутентификации по токену.

    В Фазе 4 заменить на реальную аутентификацию.
    """

    def __init__(self) -> None:
        self._operators: dict[str, Operator] = {}
        self._lock = threading.Lock()
        self._initialize_stub_operators()

    def _initialize_stub_operators(self) -> None:
        """Инициализировать stub операторов."""
        # Создаём тестовых операторов
        stub_operators = [
            Operator(
                id=uuid.uuid4(),
                name="Admin1",
                role=OperatorRole.ADMIN,
                token="admin_token_1",
            ),
            Operator(
                id=uuid.uuid4(),
                name="Admin2",
                role=OperatorRole.ADMIN,
                token="admin_token_2",
            ),
            Operator(
                id=uuid.uuid4(),
                name="Trader1",
                role=OperatorRole.TRADER,
                token="trader_token_1",
            ),
            Operator(
                id=uuid.uuid4(),
                name="RiskManager",
                role=OperatorRole.RISK_MANAGER,
                token="risk_token_1",
            ),
        ]

        with self._lock:
            for op in stub_operators:
                self._operators[op.token] = op

        logger.info("Инициализированы stub операторы", count=len(stub_operators))

    def authenticate(self, token: str) -> Operator | None:
        """
        Аутентифицировать по токену.

        Аргументы:
            token: Токен аутентификации

        Возвращает:
            Operator если токен валиден, иначе None
        """
        with self._lock:
            return self._operators.get(token)

    def get_operator(self, token: str) -> Operator | None:
        """Получить оператора по токену."""
        return self.authenticate(token)

    def validate_operator_role(self, operator: Operator, required_role: OperatorRole) -> bool:
        """
        Проверить роль оператора.

        Аргументы:
            operator: Оператор для проверки
            required_role: Требуемая роль

        Возвращает:
            True если роль достаточна
        """
        role_hierarchy: dict[OperatorRole, int] = {
            OperatorRole.ADMIN: 3,
            OperatorRole.RISK_MANAGER: 2,
            OperatorRole.TRADER: 1,
            OperatorRole.VIEWER: 0,
        }

        operator_level = role_hierarchy.get(operator.role, 0)
        required_level = role_hierarchy.get(required_role, 0)

        return bool(operator_level >= required_level)


# ==================== Operator Gate ====================


class OperatorGate:
    """
    Шлюз оператора с dual control.

    Обеспечивает двойной контроль для критических операций:
    - Требуется подтверждение от второго оператора
    - Timeout 5 минут по умолчанию
    - Логирование всех операций
    - Интеграция с Event Bus

    Аргументы:
        event_bus: Опциональный Event Bus
        authenticator: Опциональный аутентификатор
        request_timeout: Timeout запроса в минутах

    Пример:
        >>> gate = OperatorGate()
        >>> # Запрос на остановку системы
        >>> request = gate.create_request(
        ...     operator_token="admin_token_1",
        ...     operation=OperationType.SYSTEM_HALT
        ... )
        >>> # Подтверждение от второго оператора
        >>> gate.approve_request(request.id, "admin_token_2")
    """

    def __init__(
        self,
        event_bus: EnhancedEventBus | None = None,
        authenticator: TokenAuthenticator | None = None,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT_MINUTES,
    ) -> None:
        # Верхнеуровневый импорт get_event_bus для избежания циклических зависимостей
        from . import get_event_bus
        self._event_bus = event_bus or get_event_bus()
        self._authenticator = authenticator or TokenAuthenticator()
        self._request_timeout = request_timeout

        # Active requests
        self._requests: dict[uuid.UUID, DualControlRequest] = {}
        self._requests_lock = threading.Lock()

        # Callbacks
        self._on_request_created: list[Callable[[DualControlRequest], Any]] = []
        self._on_request_approved: list[Callable[[DualControlRequest], Any]] = []
        self._on_request_rejected: list[Callable[[DualControlRequest], Any]] = []
        self._on_request_expired: list[Callable[[DualControlRequest], Any]] = []

        # Statistics
        self._total_requests = 0
        self._total_approved = 0
        self._total_rejected = 0
        self._total_expired = 0

        # Background task for expiration check
        self._expiration_task: asyncio.Task | None = None
        self._running = False

        logger.info(
            "OperatorGate инициализирован",
            request_timeout=request_timeout,
        )

    @property
    def request_timeout(self) -> int:
        """Получить timeout запроса в минутах."""
        return self._request_timeout

    @property
    def active_request_count(self) -> int:
        """Получить количество активных запросов."""
        with self._requests_lock:
            return sum(1 for r in self._requests.values() if r.is_pending())

    def authenticate(self, token: str) -> Operator | None:
        """
        Аутентифицировать оператора.

        Аргументы:
            token: Токен оператора

        Возвращает:
            Operator если валиден, иначе None
        """
        return self._authenticator.authenticate(token)

    def create_request(
        self,
        operator_token: str,
        operation: OperationType,
        target_state: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DualControlRequest | None:
        """
        Создать запрос на критическую операцию.

        Аргументы:
            operator_token: Токен запрашивающего оператора
            operation: Тип операции
            target_state: Целевое состояние (для state transition)
            metadata: Дополнительные метаданные

        Возвращает:
            DualControlRequest или None если аутентификация неуспешна
        """
        # Аутентифицировать оператора
        operator = self._authenticator.get_operator(operator_token)
        if not operator:
            logger.warning(
                "Неудачная попытка создания запроса: неверный токен",
                operation=operation.value,
            )
            return None

        # Проверить права на создание запроса
        if not self._can_create_request(operator, operation):
            logger.warning(
                "Оператор не имеет прав на создание запроса",
                operator=operator.name,
                operation=operation.value,
            )
            return None

        # Создать запрос
        request = DualControlRequest(
            operation_type=operation,
            requested_by=operator,
            target_state=target_state,
            metadata=metadata or {},
        )

        # Сохранить запрос
        with self._requests_lock:
            self._requests[request.id] = request

        self._total_requests += 1

        logger.info(
            "Создан запрос dual control",
            request_id=str(request.id),
            operation=operation.value,
            requested_by=operator.name,
            expires_at=request.expires_at.isoformat(),
        )

        # Publish event
        publish_event(
            event_type="DUAL_CONTROL_REQUEST",
            source="OPERATOR_GATE",
            payload={
                "subtype": "request_created",
                "request": request.to_dict(),
            },
            priority=Priority.NORMAL,
        )

        # Callbacks
        for callback in self._on_request_created:
            try:
                callback(request)
            except Exception as e:
                logger.error("Ошибка в callback request_created", error=str(e))

        return request

    def _can_create_request(self, operator: Operator, operation: OperationType) -> bool:
        """Проверить права на создание запроса."""
        if operation in CRITICAL_OPERATIONS:
            # Для критических операций требуется ADMIN
            return self._authenticator.validate_operator_role(operator, OperatorRole.ADMIN)
        elif operation in DUAL_CONTROL_OPERATIONS:
            # Для высокорисковых - ADMIN или RISK_MANAGER
            return self._authenticator.validate_operator_role(operator, OperatorRole.RISK_MANAGER)
        else:
            # Для низкорисковых - любой авторизованный
            return operator.role != OperatorRole.VIEWER

    def approve_request(
        self,
        request_id: uuid.UUID,
        approver_token: str,
    ) -> bool:
        """
        Подтвердить запрос.

        Аргументы:
            request_id: ID запроса
            approver_token: Токен подтверждающего оператора

        Возвращает:
            True если подтверждение успешно
        """
        # Аутентифицировать подтверждающего
        approver = self._authenticator.get_operator(approver_token)
        if not approver:
            logger.warning(
                "Неудачная попытка подтверждения: неверный токен",
                request_id=str(request_id),
            )
            return False

        # Получить запрос
        with self._requests_lock:
            request = self._requests.get(request_id)

        if not request:
            logger.warning("Запрос не найден", request_id=str(request_id))
            return False

        # Подтвердить
        if not request.approve(approver):
            logger.warning(
                "Неудачное подтверждение запроса",
                request_id=str(request_id),
                reason=f"status={request.status.value}, expired={request.is_expired()}",
            )
            return False

        self._total_approved += 1

        logger.info(
            "Запрос подтверждён",
            request_id=str(request_id),
            operation=request.operation_type.value,
            approved_by=approver.name,
        )

        # Publish event
        publish_event(
            event_type="DUAL_CONTROL_REQUEST",
            source="OPERATOR_GATE",
            payload={
                "subtype": "request_approved",
                "request": request.to_dict(),
            },
            priority=Priority.NORMAL,
        )

        # Callbacks
        for callback in self._on_request_approved:
            try:
                callback(request)
            except Exception as e:
                logger.error("Ошибка в callback request_approved", error=str(e))

        return True

    def reject_request(
        self,
        request_id: uuid.UUID,
        rejecter_token: str,
        reason: str,
    ) -> bool:
        """
        Отклонить запрос.

        Аргументы:
            request_id: ID запроса
            rejecter_token: Токен отклоняющего оператора
            reason: Причина отклонения

        Возвращает:
            True если отклонение успешно
        """
        rejecter = self._authenticator.get_operator(rejecter_token)
        if not rejecter:
            return False

        with self._requests_lock:
            request = self._requests.get(request_id)

        if not request:
            return False

        if not request.reject(rejecter, reason):
            return False

        self._total_rejected += 1

        logger.info(
            "Запрос отклонён",
            request_id=str(request_id),
            rejected_by=rejecter.name,
            reason=reason,
        )

        # Publish event
        publish_event(
            event_type="DUAL_CONTROL_REQUEST",
            source="OPERATOR_GATE",
            payload={
                "subtype": "request_rejected",
                "request": request.to_dict(),
            },
            priority=Priority.NORMAL,
        )

        for callback in self._on_request_rejected:
            try:
                callback(request)
            except Exception as e:
                logger.error("Ошибка в callback request_rejected", error=str(e))

        return True

    def cancel_request(
        self,
        request_id: uuid.UUID,
        operator_token: str,
    ) -> bool:
        """
        Отменить запрос (только инициатор).

        Аргументы:
            request_id: ID запроса
            operator_token: Токен оператора

        Возвращает:
            True если отмена успешна
        """
        operator = self._authenticator.get_operator(operator_token)
        if not operator:
            return False

        with self._requests_lock:
            request = self._requests.get(request_id)

        if not request:
            return False

        # Только инициатор может отменить
        if request.requested_by.id != operator.id:
            logger.warning(
                "Отмена не разрешена: не инициатор",
                request_id=str(request_id),
                operator=operator.name,
            )
            return False

        if not request.cancel():
            return False

        logger.info(
            "Запрос отменён",
            request_id=str(request_id),
            cancelled_by=operator.name,
        )

        # Publish event
        publish_event(
            event_type="DUAL_CONTROL_REQUEST",
            source="OPERATOR_GATE",
            payload={
                "subtype": "request_cancelled",
                "request": request.to_dict(),
            },
            priority=Priority.NORMAL,
        )
        return True

    def get_request(self, request_id: uuid.UUID) -> DualControlRequest | None:
        """Получить запрос по ID."""
        with self._requests_lock:
            return self._requests.get(request_id)

    def get_pending_requests(self) -> list[DualControlRequest]:
        """Получить все ожидающие запросы."""
        with self._requests_lock:
            return [r for r in self._requests.values() if r.is_pending()]

    def get_requests_by_operator(self, operator_token: str) -> list[DualControlRequest]:
        """Получить запросы созданные оператором."""
        operator = self._authenticator.get_operator(operator_token)
        if not operator:
            return []

        with self._requests_lock:
            return [r for r in self._requests.values() if r.requested_by.id == operator.id]

    def _check_expiration(self) -> None:
        """Проверить истечение запросов."""
        with self._requests_lock:
            expired = [r for r in self._requests.values() if r.is_pending() and r.is_expired()]

        for request in expired:
            request.expire()
            self._total_expired += 1

            logger.info(
                "Запрос истёк",
                request_id=str(request.id),
                operation=request.operation_type.value,
            )

            # Publish event
            publish_event(
                event_type="DUAL_CONTROL_REQUEST",
                source="OPERATOR_GATE",
                payload={
                    "subtype": "request_expired",
                    "request": request.to_dict(),
                },
                priority=Priority.NORMAL,
            )

            for callback in self._on_request_expired:
                try:
                    callback(request)
                except Exception as e:
                    logger.error("Ошибка в callback request_expired", error=str(e))

    async def _expiration_loop(self) -> None:
        """Фоновый цикл проверки истечения."""
        while self._running:
            try:
                self._check_expiration()
                await asyncio.sleep(10)  # Проверять каждые 10 секунд
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Ошибка в expiration loop", error=str(e))

    async def _publish_request_event(self, request: DualControlRequest, event_subtype: str) -> None:
        """Опубликовать событие о запросе."""
        event = Event.new(
            SystemEventType.WATCHDOG_ALERT,  # Переиспользуем тип
            SystemEventSource.WATCHDOG,
            {
                "subtype": event_subtype,
                "request": request.to_dict(),
            },
        )
        await self._event_bus.publish(event)

    def on_request_created(self, callback: Callable[[DualControlRequest], Any]) -> None:
        """Зарегистрировать callback при создании запроса."""
        self._on_request_created.append(callback)

    def on_request_approved(self, callback: Callable[[DualControlRequest], Any]) -> None:
        """Зарегистрировать callback при подтверждении запроса."""
        self._on_request_approved.append(callback)

    def on_request_rejected(self, callback: Callable[[DualControlRequest], Any]) -> None:
        """Зарегистрировать callback при отклонении запроса."""
        self._on_request_rejected.append(callback)

    def on_request_expired(self, callback: Callable[[DualControlRequest], Any]) -> None:
        """Зарегистрировать callback при истечении запроса."""
        self._on_request_expired.append(callback)

    async def start(self) -> None:
        """Запустить OperatorGate."""
        if self._running:
            return

        self._running = True
        self._expiration_task = asyncio.create_task(self._expiration_loop())

        logger.info("OperatorGate запущен")

    async def stop(self) -> None:
        """Остановить OperatorGate."""
        if not self._running:
            return

        self._running = False

        if self._expiration_task:
            self._expiration_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._expiration_task

        logger.info("OperatorGate остановлен")

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику."""
        return {
            "running": self._running,
            "active_requests": self.active_request_count,
            "total_requests": self._total_requests,
            "total_approved": self._total_approved,
            "total_rejected": self._total_rejected,
            "total_expired": self._total_expired,
            "request_timeout": self._request_timeout,
        }

    def __repr__(self) -> str:
        return f"OperatorGate(active={self.active_request_count}, total={self._total_requests})"


# ==================== Convenience Functions ====================


def create_halt_request(gate: OperatorGate, operator_token: str) -> DualControlRequest | None:
    """
    Создать запрос на остановку системы.

    Аргументы:
        gate: Экземпляр OperatorGate
        operator_token: Токен оператора

    Возвращает:
        DualControlRequest или None
    """
    return gate.create_request(
        operator_token=operator_token,
        operation=OperationType.SYSTEM_HALT,
        target_state="HALT",
    )


def create_state_transition_request(
    gate: OperatorGate,
    operator_token: str,
    target_state: str,
) -> DualControlRequest | None:
    """
    Создать запрос на переход состояния.

    Аргументы:
        gate: Экземпляр OperatorGate
        operator_token: Токен оператора
        target_state: Целевое состояние

    Возвращает:
        DualControlRequest или None
    """
    return gate.create_request(
        operator_token=operator_token,
        operation=OperationType.STATE_TRANSITION,
        target_state=target_state,
    )
