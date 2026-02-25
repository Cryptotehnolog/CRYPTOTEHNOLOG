"""
Перечисления и константы для State Machine.

Определяет:
- SystemState: все возможные состояния системы
- ALLOWED_TRANSITIONS: допустимые переходы между состояниями
- TriggerType: типы триггеров для переходов
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Set


class SystemState(str, Enum):
    """
    Состояния системы с четкой семантикой.
    
    Состояния (от безопасного к опасному):
    - BOOT: Загрузка (0-30 сек после старта)
    - INIT: Инициализация компонентов (проверка БД, Redis, биржи)
    - READY: Готова, но не торгует (ожидание сигнала оператора)
    - TRADING: Нормальная торговля (100% функциональность)
    - DEGRADED: Деградированный режим (торговля продолжается, но ограничена)
    - SURVIVAL: Режим выживания (только закрытие позиций)
    - ERROR: Критическая ошибка (требуется вмешательство)
    - HALT: Полная остановка (все операции запрещены)
    - RECOVERY: Восстановление после ошибки
    """

    BOOT = "boot"
    INIT = "init"
    READY = "ready"
    TRADING = "trading"
    DEGRADED = "degraded"
    SURVIVAL = "survival"
    ERROR = "error"
    HALT = "halt"
    RECOVERY = "recovery"

    def __str__(self) -> str:
        """Вернуть строковое представление."""
        return self.value

    @property
    def is_trading_allowed(self) -> bool:
        """
        Проверить разрешена ли торговля в данном состоянии.
        
        Возвращает:
            True если торговля разрешена
        """
        return self in {
            SystemState.TRADING,
            SystemState.DEGRADED,
        }

    @property
    def is_critical(self) -> bool:
        """
        Проверить является ли состояние критическим.
        
        Возвращает:
            True если состояние критическое
        """
        return self in {
            SystemState.ERROR,
            SystemState.HALT,
            SystemState.SURVIVAL,
        }

    @property
    def requires_manual_intervention(self) -> bool:
        """
        Проверить требуется ли ручное вмешательство.
        
        Возвращает:
            True если требуется вмешательство оператора
        """
        return self in {
            SystemState.ERROR,
            SystemState.HALT,
        }


class TriggerType(str, Enum):
    """
    Типы триггеров для переходов состояний.
    
    Используются для логирования и аудита.
    """

    # Автоматические триггеры
    SYSTEM_STARTUP = "system_startup"
    INITIALIZATION_COMPLETE = "initialization_complete"
    OPERATOR_READY = "operator_ready"
    RISK_VIOLATION = "risk_violation"
    EXECUTION_ERROR = "execution_error"
    HEALTH_CHECK_FAILED = "health_check_failed"
    KILL_SWITCH_TRIGGERED = "kill_switch_triggered"
    POSITION_CLOSED = "position_closed"
    WATCHDOG_ALERT = "watchdog_alert"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"

    # Ручные триггеры
    OPERATOR_REQUEST = "operator_request"
    DUAL_CONTROL_APPROVED = "dual_control_approved"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"
    RECOVERY_COMPLETE = "recovery_complete"

    # Тестовые триггеры
    TEST = "test"


# Допустимые переходы между состояниями
# Ключ: текущее состояние
# Значение: множество допустимых целевых состояний
ALLOWED_TRANSITIONS: dict[SystemState, Set[SystemState]] = {
    # Загрузка системы
    SystemState.BOOT: {
        SystemState.INIT,
        SystemState.ERROR,  # Если ошибка при загрузке
    },
    
    # Инициализация компонентов
    SystemState.INIT: {
        SystemState.READY,
        SystemState.ERROR,  # Если ошибка при инициализации
    },
    
    # Готова к торговле
    SystemState.READY: {
        SystemState.TRADING,
        SystemState.HALT,
    },
    
    # Нормальная торговля
    SystemState.TRADING: {
        SystemState.DEGRADED,
        SystemState.SURVIVAL,
        SystemState.HALT,
        SystemState.ERROR,
    },
    
    # Деградированный режим
    SystemState.DEGRADED: {
        SystemState.TRADING,  # Восстановление
        SystemState.SURVIVAL,
        SystemState.HALT,
        SystemState.ERROR,
    },
    
    # Режим выживания
    SystemState.SURVIVAL: {
        SystemState.HALT,
        SystemState.ERROR,
    },
    
    # Критическая ошибка
    SystemState.ERROR: {
        SystemState.RECOVERY,
        SystemState.HALT,
    },
    
    # Полная остановка
    SystemState.HALT: {
        SystemState.RECOVERY,
    },
    
    # Восстановление
    SystemState.RECOVERY: {
        SystemState.READY,
        SystemState.ERROR,
    },
}


def is_transition_allowed(from_state: SystemState, to_state: SystemState) -> bool:
    """
    Проверить допустимость перехода между состояниями.
    
    Аргументы:
        from_state: Текущее состояние
        to_state: Целевое состояние
    
    Возвращает:
        True если переход допустим
    """
    return to_state in ALLOWED_TRANSITIONS.get(from_state, set())


def get_allowed_transitions(from_state: SystemState) -> Set[SystemState]:
    """
    Получить все допустимые переходы из состояния.
    
    Аргументы:
        from_state: Текущее состояние
    
    Возвращает:
        Множество допустимых целевых состояний
    """
    return ALLOWED_TRANSITIONS.get(from_state, set())
