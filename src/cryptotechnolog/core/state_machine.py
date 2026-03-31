"""
State Machine - детерминированная машина состояний.

Особенности:
- Валидация переходов (ALLOWED_TRANSITIONS)
- Audit trail (все переходы в БД)
- Callbacks (on_enter/on_exit)
- Optimistic locking для concurrency
- Метрики (time in state, transition count)
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
import json
from typing import Any, ClassVar

from cryptotechnolog.config import get_logger

from .event import Event, SystemEventSource, SystemEventType
from .state_machine_enums import (
    ALLOWED_TRANSITIONS,
    SystemState,
    get_state_policy,
    get_state_timeout_limit,
    is_transition_allowed,
)
from .state_transition import (
    StateHistory,
    StateTransition,
    TransitionResult,
)

logger = get_logger(__name__)

# Тип колбэка
StateCallback = Callable[[SystemState, SystemState], Any]


class StateMachineError(Exception):
    """Ошибка при работе State Machine."""

    pass


class InvalidTransitionError(StateMachineError):
    """Недопустимый переход состояния."""

    pass


class TransitionTimeoutError(StateMachineError):
    """Таймаут при выполнении перехода."""

    pass


class DatabaseError(StateMachineError):
    """Ошибка базы данных."""

    pass


class StateMachine:
    """
    Детерминированная машина состояний.

    Управляет состоянием системы с гарантией:
    - Все переходы валидны
    - Audit trail всех изменений
    - Callbacks при входе/выходе из состояний
    - Optimistic locking для concurrency

    Атрибуты:
        current_state: Текущее состояние системы
        version: Версия состояния для optimistic locking
        transition_history: История переходов

    Пример использования:
        >>> sm = StateMachine()
        >>> result = await sm.transition(SystemState.TRADING, TriggerType.OPERATOR_REQUEST)
        >>> print(sm.can_trade())  # True
    """

    def __init__(
        self,
        db_manager: Any | None = None,
        metrics_collector: Any | None = None,
        event_bus: Any | None = None,
    ) -> None:
        """
        Инициализировать State Machine.

        Аргументы:
            db_manager: Менеджер БД для audit trail (опционально)
            metrics_collector: Коллектор метрик (опционально)
            event_bus: Event Bus для публикации событий (опционально)
        """
        self._db = db_manager
        self._metrics = metrics_collector
        self._event_bus = event_bus

        # Текущее состояние
        self._current_state: SystemState = SystemState.BOOT
        self._version: int = 0

        # История переходов
        self._history = StateHistory(max_size=100)
        self._transition_counter: int = 0

        # Блокировка для concurrency
        self._transition_lock = asyncio.Lock()

        # Колбэки
        self._on_enter_callbacks: dict[SystemState, list[StateCallback]] = {}
        self._on_exit_callbacks: dict[SystemState, list[StateCallback]] = {}

        # Время входа в текущее состояние
        self._state_entered_at: datetime = datetime.now(UTC)

        # Режим работы
        self._initialized: bool = False

        logger.info(
            "State Machine инициализирована",
            initial_state=self._current_state.value,
        )

    # ==================== Свойства ====================

    @property
    def current_state(self) -> SystemState:
        """Получить текущее состояние."""
        return self._current_state

    @property
    def version(self) -> int:
        """Получить версию состояния."""
        return self._version

    @property
    def is_initialized(self) -> bool:
        """Проверить инициализирована ли State Machine."""
        return self._initialized

    # ==================== Публичные методы ====================

    def can_trade(self) -> bool:
        """
        Проверить разрешена ли торговля в текущем состоянии.

        Возвращает:
            True если торговля разрешена

        Пример:
            >>> if sm.can_trade():
            ...     await risk_engine.check_order(order)
        """
        return self._current_state.is_trading_allowed

    def is_transitioning(self) -> bool:
        """
        Проверить идет ли переход прямо сейчас.

        Возвращает:
            True если выполняется переход
        """
        return self._transition_lock.locked()

    def is_trade_allowed(self) -> bool:
        """
        Проверить разрешена ли торговля (алиас can_trade).

        Возвращает:
            True если торговля разрешена
        """
        return self.can_trade()

    def get_allowed_transitions(self) -> set[SystemState]:
        """
        Получить все допустимые переходы из текущего состояния.

        Возвращает:
            Множество допустимых целевых состояний
        """
        transitions = ALLOWED_TRANSITIONS.get(self._current_state)
        return set(transitions) if transitions else set()

    def can_transition_to(self, to_state: SystemState) -> bool:
        """
        Проверить можно ли перейти в указанное состояние.

        Аргументы:
            to_state: Целевое состояние

        Возвращает:
            True если переход допустим
        """
        return is_transition_allowed(self._current_state, to_state)

    def requires_dual_control(self, to_state: SystemState) -> bool:
        """
        Проверить требуется ли dual control для перехода.

        Аргументы:
            to_state: Целевое состояние

        Возвращает:
            True если требуется подтверждение двух операторов
        """
        # HALT, RECOVERY требуют dual control
        return to_state in {SystemState.HALT, SystemState.RECOVERY}

    async def initialize(self) -> bool:
        """
        Инициализировать State Machine.

        Загружает текущее состояние из БД если доступно.

        Возвращает:
            True если инициализация успешна
        """
        if self._initialized:
            logger.warning("State Machine уже инициализирована")
            return True

        # Пробуем загрузить состояние из БД
        if self._db:
            try:
                state = await self._load_state_from_db()
                if state:
                    self._current_state = state["current_state"]
                    self._version = state["version"]
                    logger.info(
                        "Загружено состояние из БД",
                        state=self._current_state.value,
                        version=self._version,
                    )
            except Exception as e:
                logger.warning(
                    "Не удалось загрузить состояние из БД",
                    error=str(e),
                )

        self._initialized = True
        self._state_entered_at = datetime.now(UTC)

        logger.info(
            "State Machine инициализирована",
            state=self._current_state.value,
        )

        return True

    async def transition(
        self,
        to_state: SystemState,
        trigger: str,
        metadata: dict[str, Any] | None = None,
        operator: str | None = None,
        max_retries: int = 3,
    ) -> TransitionResult:
        """
        Выполнить переход в новое состояние.

        Аргументы:
            to_state: Целевое состояние
            trigger: Причина перехода
            metadata: Дополнительный контекст
            operator: Имя оператора (для ручных переходов)

        Возвращает:
            TransitionResult с результатом перехода

        Raises:
            InvalidTransitionError: Если переход недопустим

        Пример:
            >>> result = await sm.transition(
            ...     SystemState.TRADING,
            ...     TriggerType.OPERATOR_REQUEST,
            ...     operator="admin"
            ... )
            >>> if result.success:
            ...     print("Переход выполнен")
        """
        start_time = datetime.now(UTC)

        # Используем lock для предотвращения concurrent transitions в одном инстансе
        async with self._transition_lock:
            from_state = self._current_state
            expected_version = self._version

            # Проверить допустимость перехода
            if not is_transition_allowed(from_state, to_state):
                error_msg = f"Недопустимый переход: {from_state.value} → {to_state.value}"
                logger.error(
                    "Недопустимый переход состояния",
                    from_state=from_state.value,
                    to_state=to_state.value,
                    trigger=trigger,
                )

                # Записать неудачную попытку в метрики
                self._record_invalid_transition(from_state, to_state)

                return TransitionResult(
                    success=False,
                    error=error_msg,
                    reason="invalid_transition",
                )

            logger.info(
                "Переход состояния начат",
                from_state=from_state.value,
                to_state=to_state.value,
                trigger=trigger,
                operator=operator,
            )

            # Цикл с retry для optimistic locking
            for attempt in range(max_retries):
                try:
                    # 1. Выполнить on_exit callbacks
                    await self._execute_exit_callbacks(from_state, to_state)

                    # 2. Обновить состояние в памяти
                    self._current_state = to_state
                    self._version += 1
                    self._transition_counter += 1

                    # 3. Выполнить on_enter callbacks
                    await self._execute_enter_callbacks(from_state, to_state)

                    # 4. Создать запись о переходе
                    transition = StateTransition(
                        transition_id=self._transition_counter,
                        from_state=from_state,
                        to_state=to_state,
                        trigger=trigger,
                        timestamp=start_time,
                        metadata=metadata or {},
                        operator=operator,
                    )

                    # 5. Сохранить в историю
                    self._history.add(transition)

                    # 6. Сохранить в БД (audit trail) с optimistic locking
                    if self._db:
                        db_success = await self._save_transition_with_optimistic_lock(
                            transition=transition,
                            to_state=to_state,
                            expected_version=expected_version,
                        )

                        if not db_success:
                            # Конфликт версий - откат локальных изменений и retry
                            logger.warning(
                                "Конфликт версий при optimistic locking, повторная попытка",
                                attempt=attempt + 1,
                                max_retries=max_retries,
                                expected_version=expected_version,
                            )

                            # Откат локального состояния
                            self._current_state = from_state
                            self._version = expected_version

                            # Экспоненциальный backoff
                            await asyncio.sleep(0.01 * (2**attempt))
                            continue

                    # 7. Опубликовать событие
                    if self._event_bus:
                        try:
                            await self._publish_transition_event(transition)
                        except Exception as e:
                            logger.warning(
                                "Не удалось опубликовать событие",
                                error=str(e),
                            )

                    # 8. Записать метрики
                    self._record_transition_metrics(from_state, to_state, trigger)

                    # Вычислить длительность
                    duration_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
                    transition.duration_ms = duration_ms

                    # Обновить время входа в состояние
                    self._state_entered_at = datetime.now(UTC)

                    logger.info(
                        "Переход состояния выполнен",
                        from_state=from_state.value,
                        to_state=to_state.value,
                        version=self._version,
                        duration_ms=duration_ms,
                    )

                    return TransitionResult(
                        success=True,
                        transition=transition,
                    )

                except Exception as e:
                    # При ошибке пробуем следующую попытку
                    logger.warning(
                        "Ошибка при переходе, повторная попытка",
                        attempt=attempt + 1,
                        error=str(e),
                    )

                    # Откат локального состояния при ошибке
                    self._current_state = from_state
                    self._version = expected_version

                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.01 * (2**attempt))
                        continue

                    # Все попытки исчерпаны
                    error_msg = f"Не удалось выполнить переход после {max_retries} попыток: {e!s}"
                    logger.critical(
                        "Критическая ошибка при переходе состояния",
                        from_state=from_state.value,
                        to_state=to_state.value,
                        attempts=max_retries,
                        error=str(e),
                    )

                    return TransitionResult(
                        success=False,
                        error=error_msg,
                        reason="transition_error",
                    )

            # Если мы здесь - все попытки исчерпаны
            error_msg = f"Не удалось выполнить переход: конфликт версий после {max_retries} попыток"
            return TransitionResult(
                success=False,
                error=error_msg,
                reason="optimistic_lock_conflict",
            )

    # ==================== Callbacks ====================

    def register_on_enter(
        self,
        state: SystemState,
        callback: StateCallback,
        name: str | None = None,
    ) -> None:
        """
        Зарегистрировать колбэк при входе в состояние.

        Аргументы:
            state: Состояние для колбэка
            callback: Функция колбэка (async или sync)
            name: Имя колбэка для логирования
        """
        if state not in self._on_enter_callbacks:
            self._on_enter_callbacks[state] = []

        callback_name = name or callback.__name__
        self._on_enter_callbacks[state].append(callback)

        logger.debug(
            "Зарегистрирован on_enter callback",
            state=state.value,
            callback=callback_name,
        )

    def register_on_exit(
        self,
        state: SystemState,
        callback: StateCallback,
        name: str | None = None,
    ) -> None:
        """
        Зарегистрировать колбэк при выходе из состояния.

        Аргументы:
            state: Состояние для колбэка
            callback: Функция колбэка (async или sync)
            name: Имя колбэка для логирования
        """
        if state not in self._on_exit_callbacks:
            self._on_exit_callbacks[state] = []

        callback_name = name or callback.__name__
        self._on_exit_callbacks[state].append(callback)

        logger.debug(
            "Зарегистрирован on_exit callback",
            state=state.value,
            callback=callback_name,
        )

    def unregister_on_enter(self, state: SystemState, callback: StateCallback) -> bool:
        """
        Удалить on_enter колбэк.

        Аргументы:
            state: Состояние
            callback: Колбэк для удаления

        Возвращает:
            True если колбэк был удален
        """
        if state in self._on_enter_callbacks:
            try:
                self._on_enter_callbacks[state].remove(callback)
                return True
            except ValueError:
                pass
        return False

    def unregister_on_exit(self, state: SystemState, callback: StateCallback) -> bool:
        """
        Удалить on_exit колбэк.

        Аргументы:
            state: Состояние
            callback: Колбэк для удаления

        Возвращает:
            True если колбэк был удален
        """
        if state in self._on_exit_callbacks:
            try:
                self._on_exit_callbacks[state].remove(callback)
                return True
            except ValueError:
                pass
        return False

    # ==================== История ====================

    def get_history(self, count: int = 10) -> list[StateTransition]:
        """
        Получить последние N переходов.

        Аргументы:
            count: Количество переходов

        Возвращает:
            Список переходов
        """
        return self._history.get_recent(count)

    def get_transition_count(self) -> int:
        """
        Получить общее количество переходов.

        Возвращает:
            Количество переходов
        """
        return self._transition_counter

    def get_time_in_current_state(self) -> int:
        """
        Получить время в текущем состоянии (секунды).

        Возвращает:
            Время в секундах
        """
        return int((datetime.now(UTC) - self._state_entered_at).total_seconds())

    # ==================== State Policies ====================

    def can_open_positions(self) -> bool:
        """
        Проверить разрешено ли открытие новых позиций.

        Возвращает:
            True если разрешено
        """
        policy = get_state_policy(self._current_state)
        return policy.allow_new_positions

    def can_increase_size(self) -> bool:
        """
        Проверить разрешено ли увеличение существующих позиций.

        Возвращает:
            True если разрешено
        """
        policy = get_state_policy(self._current_state)
        return policy.allow_increase_size

    def can_place_orders(self) -> bool:
        """
        Проверить разрешена ли отправка новых ордеров.

        Возвращает:
            True если разрешено
        """
        policy = get_state_policy(self._current_state)
        return policy.allow_new_orders

    def get_risk_multiplier(self) -> float:
        """
        Получить множитель риска для текущего состояния.

        Возвращает:
            Множитель (1.0 = нормальный риск, 0.5 = половинный, 0 = запрещено)
        """
        policy = get_state_policy(self._current_state)
        return policy.risk_multiplier

    def get_max_positions(self) -> int:
        """
        Получить максимальное количество позиций для текущего состояния.

        Возвращает:
            Максимальное количество позиций
        """
        policy = get_state_policy(self._current_state)
        return policy.max_positions

    def get_max_order_size(self) -> float:
        """
        Получить максимальный размер ордера (% от портфеля).

        Returns:
            Максимальный размер (0.1 = 10%)
        """
        policy = get_state_policy(self._current_state)
        return policy.max_order_size

    def is_short_selling_allowed(self) -> bool:
        """
        Проверить разрешен ли short selling.

        Returns:
            True если разрешён
        """
        policy = get_state_policy(self._current_state)
        return policy.allow_short_selling

    def requires_manual_approval(self) -> bool:
        """
        Проверить требуется ли ручное одобрение для операций.

        Returns:
            True если требуется
        """
        policy = get_state_policy(self._current_state)
        return policy.require_manual_approval

    def get_state_policy_description(self) -> str:
        """
        Получить описание политики текущего состояния.

        Returns:
            Описание
        """
        policy = get_state_policy(self._current_state)
        return policy.description

    # ==================== State Timeout Monitoring ====================

    def get_state_timeout(self) -> int | None:
        """
        Получить таймаут для текущего состояния.

        Returns:
            Таймаут в секундах или None если без ограничений
        """
        return get_state_timeout_limit(self._current_state)

    def is_state_timeout_exceeded(self) -> bool:
        """
        Проверить превышен ли таймаут состояния.

        Returns:
            True если превышен
        """
        timeout = self.get_state_timeout()
        if timeout is None:
            return False

        time_in_state = self.get_time_in_current_state()
        return time_in_state >= timeout

    async def _monitor_state_timeouts(
        self,
        check_interval: int = 30,
    ) -> None:
        """
        Мониторить таймауты состояний и выполнять автоматические переходы.

        Запускается как background task. При превышении настроенного таймаута состояния
        выполняет автоматический переход в следующее состояние.

        Аргументы:
            check_interval: Интервал проверки в секундах
        """
        logger.info("Запущен мониторинг таймаутов состояний", interval=check_interval)

        while True:
            try:
                await asyncio.sleep(check_interval)

                timeout = self.get_state_timeout()
                if timeout is None:
                    continue  # Без ограничений

                if self.is_state_timeout_exceeded():
                    time_in_state = self.get_time_in_current_state()
                    logger.warning(
                        "Превышен таймаут состояния",
                        state=self._current_state.value,
                        time_in_state=time_in_state,
                        timeout=timeout,
                    )

                    # Определить следующее состояние при таймауте
                    next_state = self._get_next_state_on_timeout()

                    if next_state:
                        logger.info(
                            "Автоматический переход по таймауту",
                            from_state=self._current_state.value,
                            to_state=next_state.value,
                        )

                        result = await self.transition(
                            next_state,
                            trigger="state_timeout_exceeded",
                            metadata={
                                "time_in_state": time_in_state,
                                "timeout": timeout,
                            },
                        )

                        if not result.success:
                            logger.error(
                                "Не удалось выполнить автоматический переход",
                                error=result.error,
                            )
                    else:
                        logger.warning(
                            "Нет доступного состояния для перехода по таймауту",
                            state=self._current_state.value,
                        )

            except asyncio.CancelledError:
                logger.info("Мониторинг таймаутов остановлен")
                break
            except Exception as e:
                logger.error("Ошибка в мониторинге таймаутов", error=str(e))
                await asyncio.sleep(5)

    # Маппинг состояний на следующее при таймауте
    _TIMEOUT_TRANSITIONS: ClassVar[dict[SystemState, SystemState]] = {
        SystemState.DEGRADED: SystemState.HALT,
        SystemState.SURVIVAL: SystemState.HALT,
        SystemState.ERROR: SystemState.HALT,
        SystemState.RECOVERY: SystemState.HALT,
        SystemState.RISK_REDUCTION: SystemState.HALT,
        SystemState.BOOT: SystemState.ERROR,
        SystemState.INIT: SystemState.ERROR,
    }

    def _get_next_state_on_timeout(self) -> SystemState | None:
        """
        Определить следующее состояние при автоматическом переходе по таймауту.

        Returns:
            Следующее состояние или None
        """
        return self._TIMEOUT_TRANSITIONS.get(self._current_state)

    # ==================== Checkpoint ====================

    async def checkpoint(self, redis_client: Any | None = None) -> bool:
        """
        Создать checkpoint состояния в Redis.

        Сохраняет текущее состояние в Redis для быстрого восстановления
        при перезапуске. Используется при graceful shutdown.

        Аргументы:
            redis_client: Redis клиент для сохранения (опционально)

        Returns:
            True если checkpoint создан успешно
        """
        checkpoint_data = {
            "current_state": self._current_state.value,
            "version": self._version,
            "transition_counter": self._transition_counter,
            "state_entered_at": self._state_entered_at.isoformat(),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Пробуем сохранить в Redis
        if redis_client:
            try:
                key = "cryptotechnolog:state_machine:checkpoint"
                await redis_client.set(
                    key,
                    json.dumps(checkpoint_data),
                    ex=86400 * 7,  # 7 дней TTL
                )
                logger.info(
                    "Checkpoint создан в Redis",
                    state=self._current_state.value,
                    version=self._version,
                )
                return True
            except Exception as e:
                logger.error("Ошибка создания checkpoint в Redis", error=str(e))

        # Fallback - сохраняем в БД
        if self._db:
            try:
                await self._db.execute(
                    """
                    INSERT INTO state_machine_checkpoints
                    (current_state, version, transition_counter, metadata, created_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                    current_state = EXCLUDED.current_state,
                    version = EXCLUDED.version,
                    transition_counter = EXCLUDED.transition_counter,
                    metadata = EXCLUDED.metadata,
                    created_at = NOW()
                    """,
                    self._current_state.value,
                    self._version,
                    self._transition_counter,
                    json.dumps(checkpoint_data),
                )
                await self._db.execute("COMMIT")

                logger.info(
                    "Checkpoint создан в БД",
                    state=self._current_state.value,
                    version=self._version,
                )
                return True
            except Exception as e:
                logger.error("Ошибка создания checkpoint в БД", error=str(e))

        logger.warning("Checkpoint не сохранён - нет доступных хранилищ")
        return False

    async def restore_from_checkpoint(
        self,
        redis_client: Any | None = None,
    ) -> bool:
        """
        Восстановить состояние из checkpoint.

        Аргументы:
            redis_client: Redis клиент для восстановления

        Returns:
            True если восстановление успешно
        """
        # Пробуем восстановить из Redis
        if redis_client:
            try:
                key = "cryptotechnolog:state_machine:checkpoint"
                data = await redis_client.get(key)
                if data:
                    checkpoint = json.loads(data)
                    self._current_state = SystemState(checkpoint["current_state"])
                    self._version = checkpoint["version"]
                    self._transition_counter = checkpoint["transition_counter"]
                    self._state_entered_at = datetime.fromisoformat(checkpoint["state_entered_at"])

                    logger.info(
                        "Состояние восстановлено из Redis",
                        state=self._current_state.value,
                        version=self._version,
                    )
                    return True
            except Exception as e:
                logger.error("Ошибка восстановления из Redis", error=str(e))

        # Fallback - пробуем из БД
        if self._db:
            try:
                row = await self._db.fetchrow("""
                    SELECT current_state, version, transition_counter, metadata
                    FROM state_machine_checkpoints
                    ORDER BY created_at DESC
                    LIMIT 1
                    """)
                if row:
                    self._current_state = SystemState(row["current_state"])
                    self._version = row["version"]
                    self._transition_counter = row["transition_counter"]

                    logger.info(
                        "Состояние восстановлено из БД",
                        state=self._current_state.value,
                        version=self._version,
                    )
                    return True
            except Exception as e:
                logger.error("Ошибка восстановления из БД", error=str(e))

        logger.warning("Checkpoint не найден")
        return False

    # ==================== Приватные методы ====================

    async def _execute_enter_callbacks(
        self,
        from_state: SystemState,
        to_state: SystemState,
    ) -> None:
        """Выполнить on_enter колбэки."""
        if to_state not in self._on_enter_callbacks:
            return

        for callback in self._on_enter_callbacks[to_state]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(from_state, to_state)
                else:
                    callback(from_state, to_state)

                logger.debug(
                    "Выполнен on_enter callback",
                    state=to_state.value,
                    callback=callback.__name__,
                )
            except Exception as e:
                logger.error(
                    "Ошибка в on_enter callback",
                    state=to_state.value,
                    callback=callback.__name__,
                    error=str(e),
                )

    async def _execute_exit_callbacks(
        self,
        from_state: SystemState,
        to_state: SystemState,
    ) -> None:
        """Выполнить on_exit колбэки."""
        if from_state not in self._on_exit_callbacks:
            return

        for callback in self._on_exit_callbacks[from_state]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(from_state, to_state)
                else:
                    callback(from_state, to_state)

                logger.debug(
                    "Выполнен on_exit callback",
                    state=from_state.value,
                    callback=callback.__name__,
                )
            except Exception as e:
                logger.error(
                    "Ошибка в on_exit callback",
                    state=from_state.value,
                    callback=callback.__name__,
                    error=str(e),
                )

    async def _load_state_from_db(self) -> dict[str, Any] | None:
        """Загрузить состояние из БД."""
        if not self._db:
            return None

        try:
            row = await self._db.fetchrow(
                "SELECT current_state, version FROM state_machine_states WHERE id = 1"
            )
            if row:
                return {
                    "current_state": SystemState(row["current_state"]),
                    "version": row["version"],
                }
        except Exception as e:
            logger.warning("Ошибка при загрузке состояния из БД", error=str(e))

        return None

    async def _save_transition_to_db(self, transition: StateTransition) -> None:
        """Сохранить переход в БД."""
        if not self._db:
            return

        # Сериализуем metadata в JSON строку
        metadata_json = json.dumps(transition.metadata) if transition.metadata else "{}"

        # Конвертируем timestamp в naive datetime для совместимости с PostgreSQL
        timestamp_naive = transition.timestamp.replace(tzinfo=None)

        try:
            await self._db.execute(
                """
                INSERT INTO state_transitions
                (from_state, to_state, trigger, metadata, operator, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                transition.from_state.value,
                transition.to_state.value,
                transition.trigger,
                metadata_json,
                transition.operator,
                timestamp_naive,
            )
            # Явный commit для гарантии сохранения
            await self._db.execute("COMMIT")
        except Exception as e:
            logger.error("Ошибка при сохранении перехода в БД", error=str(e))
            await self._db.execute("ROLLBACK")

    async def _save_transition_with_optimistic_lock(
        self,
        transition: StateTransition,
        to_state: SystemState,
        expected_version: int,
    ) -> bool:
        """
        Сохранить переход в БД с использованием optimistic locking.

        Использует транзакцию с проверкой версии:
        - Если версия совпала - переход сохраняется
        - Если версия не совпала (конфликт) - возвращает False для retry

        Аргументы:
            transition: Запись о переходе
            to_state: Новое состояние
            expected_version: Ожидаемая версия для проверки

        Возвращает:
            True если сохранение успешно, False при конфликте версий
        """
        if not self._db:
            return True

        # Сериализуем metadata в JSON строку
        metadata_json = json.dumps(transition.metadata) if transition.metadata else "{}"

        # Конвертируем timestamp в naive datetime для совместимости с PostgreSQL
        timestamp_naive = transition.timestamp.replace(tzinfo=None)

        try:
            # Начинаем транзакцию
            await self._db.execute("BEGIN")

            # Вставляем запись о переходе
            await self._db.execute(
                """
                INSERT INTO state_transitions
                (from_state, to_state, trigger, metadata, operator, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                transition.from_state.value,
                transition.to_state.value,
                transition.trigger,
                metadata_json,
                transition.operator,
                timestamp_naive,
            )

            # Обновляем состояние с проверкой версии (OPTIMISTIC LOCKING)
            result = await self._db.execute(
                """
                UPDATE state_machine_states
                SET current_state = $1, version = version + 1, updated_at = NOW()
                WHERE id = 1 AND version = $2
                """,
                to_state.value,
                expected_version,
            )

            # Проверяем сколько строк обновлено
            # "UPDATE 0" означает что версия не совпала - конфликт
            updated_rows = int(result.split()[-1]) if result else 0

            if updated_rows == 0:
                # Конфликт версий - откатываем транзакцию
                await self._db.execute("ROLLBACK")
                logger.warning(
                    "Конфликт optimistic locking - версия не совпала",
                    expected_version=expected_version,
                    from_state=transition.from_state.value,
                    to_state=to_state.value,
                )
                return False

            # Успех - коммитим транзакцию
            await self._db.execute("COMMIT")

            logger.debug(
                "Сохранен переход с optimistic locking",
                from_state=transition.from_state.value,
                to_state=to_state.value,
                version=expected_version + 1,
            )

            return True

        except Exception as e:
            logger.error("Ошибка при сохранении перехода с optimistic locking", error=str(e))
            await self._db.execute("ROLLBACK")
            raise

    async def _update_state_in_db(self, state: SystemState) -> None:
        """Обновить состояние в БД."""
        if not self._db:
            return

        try:
            await self._db.execute(
                """
                UPDATE state_machine_states
                SET current_state = $1, version = version + 1, updated_at = NOW()
                WHERE id = 1
                """,
                state.value,
            )
            # Явный commit для гарантии сохранения
            await self._db.execute("COMMIT")
        except Exception as e:
            logger.error("Ошибка при обновлении состояния в БД", error=str(e))
            await self._db.execute("ROLLBACK")

    async def _publish_transition_event(self, transition: StateTransition) -> None:
        """Опубликовать событие перехода."""
        if not self._event_bus:
            return

        event = Event.new(
            event_type=SystemEventType.STATE_TRANSITION,
            source=SystemEventSource.STATE_MACHINE,
            payload=transition.to_dict(),
        )

        await self._event_bus.publish(event)

    def _record_transition_metrics(
        self,
        from_state: SystemState,
        to_state: SystemState,
        trigger: str,
    ) -> None:
        """Записать метрики перехода."""
        if not self._metrics:
            return

        try:
            # Counter для переходов
            counter = self._metrics.get_counter("state_transitions_total")
            counter.inc()

            # Gauge для текущего состояния
            gauge = self._metrics.get_gauge("current_system_state")
            gauge.set(self._current_state.value)

        except Exception as e:
            logger.warning("Не удалось записать метрики", error=str(e))

    def _record_invalid_transition(
        self,
        from_state: SystemState,
        to_state: SystemState,
    ) -> None:
        """Записать неудачную попытку перехода."""
        if not self._metrics:
            return

        try:
            counter = self._metrics.get_counter("invalid_transition_attempts_total")
            counter.inc()
        except Exception:
            pass

    # ====================repr ====================

    def __repr__(self) -> str:
        """Строковое представление."""
        return (
            f"StateMachine(state={self._current_state.value}, "
            f"version={self._version}, transitions={self._transition_counter})"
        )

    def __str__(self) -> str:
        """Строковое представление для пользователя."""
        return f"State: {self._current_state.value} (v{self._version})"
