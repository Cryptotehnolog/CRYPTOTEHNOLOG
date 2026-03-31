"""
Перечисления и константы для State Machine.

Определяет:
- SystemState: все возможные состояния системы
- ALLOWED_TRANSITIONS: допустимые переходы между состояниями
- TriggerType: типы триггеров для переходов
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from cryptotechnolog.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Set


class SystemState(StrEnum):
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
    RISK_REDUCTION = "risk_reduction"  # Фаза 5 - снижение риска
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


class TriggerType(StrEnum):
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

    # Новые триггеры v4.4
    LOW_UNIVERSE_QUALITY = "low_universe_quality"  # Фаза 6
    STABLE_RECOVERED = "stable_recovered"  # Фаза 9
    RISK_BREACH = "risk_breach"  # Фаза 5
    FAST_VELOCITY_ALERT = "fast_velocity_alert"  # Фаза 9
    SLOW_VELOCITY_ALERT = "slow_velocity_alert"  # Фаза 9
    STATE_TIMEOUT_EXCEEDED = "state_timeout_exceeded"  # Автоматический переход

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
        SystemState.RISK_REDUCTION,  # RISK_BREACH → RISK_REDUCTION
        SystemState.DEGRADED,  # LOW_UNIVERSE_QUALITY, FAST_VELOCITY_ALERT → DEGRADED
        SystemState.SURVIVAL,
        SystemState.HALT,
        SystemState.ERROR,
    },
    # Снижение риска (Фаза 5)
    SystemState.RISK_REDUCTION: {
        SystemState.TRADING,  # Восстановление после стабилизации
        SystemState.DEGRADED,  # Ухудшение
        SystemState.SURVIVAL,  # Критическое ухудшение
        SystemState.HALT,
        SystemState.ERROR,
    },
    # Деградированный режим
    SystemState.DEGRADED: {
        SystemState.TRADING,  # STABLE_RECOVERED → TRADING
        SystemState.RISK_REDUCTION,  # SLOW_VELOCITY_ALERT → RISK_REDUCTION
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


# ==================== MAX_STATE_TIMES ====================
# Максимальное время нахождения в каждом состоянии (секунды)
# Если время превышено - автоматический переход в следующее состояние

MAX_STATE_TIMES: dict[SystemState, int] = {
    SystemState.BOOT: 60,  # 1 минута на загрузку
    SystemState.INIT: 120,  # 2 минуты на инициализацию
    SystemState.READY: 3600,  # 1 час ожидания (можно долго ждать сигнала)
    SystemState.TRADING: -1,  # Без ограничений
    SystemState.RISK_REDUCTION: 1800,  # 30 минут - потом HALT
    SystemState.DEGRADED: 3600,  # 1 час - потом HALT
    SystemState.SURVIVAL: 1800,  # 30 минут - потом HALT
    SystemState.ERROR: 300,  # 5 минут на ручное вмешательство
    SystemState.HALT: -1,  # Без ограничений (ждёт восстановления)
    SystemState.RECOVERY: 600,  # 10 минут на восстановление
}


# ==================== STATE_POLICIES ====================
# Политики для каждого состояния


@dataclass(frozen=True)
class StatePolicy:
    """Политика состояния системы."""

    allow_new_positions: bool  # Разрешены ли новые позиции
    allow_increase_size: bool  # Разрешено ли увеличение позиций
    allow_new_orders: bool  # Разрешены ли новые ордера
    risk_multiplier: float  # Множитель риска (1.0 = норма, 0.5 = половинный)
    max_positions: int  # Максимальное количество позиций
    max_order_size: float  # Максимальный размер ордера (% от портфеля)
    allow_short_selling: bool  # Разрешен ли шорт
    require_manual_approval: bool  # Требуется ли ручное одобрение
    description: str  # Описание политики


STATE_POLICIES: dict[SystemState, StatePolicy] = {
    SystemState.BOOT: StatePolicy(
        allow_new_positions=False,
        allow_increase_size=False,
        allow_new_orders=False,
        risk_multiplier=0.0,
        max_positions=0,
        max_order_size=0.0,
        allow_short_selling=False,
        require_manual_approval=True,
        description="Система загружается, торговля запрещена",
    ),
    SystemState.INIT: StatePolicy(
        allow_new_positions=False,
        allow_increase_size=False,
        allow_new_orders=False,
        risk_multiplier=0.0,
        max_positions=0,
        max_order_size=0.0,
        allow_short_selling=False,
        require_manual_approval=True,
        description="Инициализация компонентов, торговля запрещена",
    ),
    SystemState.READY: StatePolicy(
        allow_new_positions=False,
        allow_increase_size=False,
        allow_new_orders=False,
        risk_multiplier=0.0,
        max_positions=0,
        max_order_size=0.0,
        allow_short_selling=False,
        require_manual_approval=True,
        description="Готова к торговле, ожидает сигнала оператора",
    ),
    SystemState.TRADING: StatePolicy(
        allow_new_positions=True,
        allow_increase_size=True,
        allow_new_orders=True,
        risk_multiplier=1.0,
        max_positions=100,
        max_order_size=0.1,  # 10% от портфеля
        allow_short_selling=True,
        require_manual_approval=False,
        description="Нормальная торговля, полная функциональность",
    ),
    SystemState.DEGRADED: StatePolicy(
        allow_new_positions=False,
        allow_increase_size=False,
        allow_new_orders=True,  # Только закрытие
        risk_multiplier=0.5,
        max_positions=50,
        max_order_size=0.05,  # 5% от портфеля
        allow_short_selling=False,
        require_manual_approval=True,
        description="Деградированный режим, ограниченная торговля",
    ),
    SystemState.RISK_REDUCTION: StatePolicy(
        allow_new_positions=False,
        allow_increase_size=False,
        allow_new_orders=True,  # Только закрытие позиций
        risk_multiplier=0.25,  # Минимальный риск
        max_positions=20,
        max_order_size=0.02,  # 2% от портфеля
        allow_short_selling=False,
        require_manual_approval=True,
        description="Режим снижения риска, минимальная торговля",
    ),
    SystemState.SURVIVAL: StatePolicy(
        allow_new_positions=False,
        allow_increase_size=False,
        allow_new_orders=True,  # Только закрытие позиций
        risk_multiplier=0.1,
        max_positions=0,
        max_order_size=0.01,  # 1% от портфеля
        allow_short_selling=False,
        require_manual_approval=True,
        description="Режим выживания, только закрытие позиций",
    ),
    SystemState.ERROR: StatePolicy(
        allow_new_positions=False,
        allow_increase_size=False,
        allow_new_orders=False,
        risk_multiplier=0.0,
        max_positions=0,
        max_order_size=0.0,
        allow_short_selling=False,
        require_manual_approval=True,
        description="Критическая ошибка, торговля остановлена",
    ),
    SystemState.HALT: StatePolicy(
        allow_new_positions=False,
        allow_increase_size=False,
        allow_new_orders=False,
        risk_multiplier=0.0,
        max_positions=0,
        max_order_size=0.0,
        allow_short_selling=False,
        require_manual_approval=True,
        description="Полная остановка, требуется ручное восстановление",
    ),
    SystemState.RECOVERY: StatePolicy(
        allow_new_positions=False,
        allow_increase_size=False,
        allow_new_orders=False,
        risk_multiplier=0.0,
        max_positions=0,
        max_order_size=0.0,
        allow_short_selling=False,
        require_manual_approval=True,
        description="Восстановление, торговля запрещена",
    ),
}


def get_state_policy(state: SystemState) -> StatePolicy:
    """Получить политику для состояния."""
    base_policy = STATE_POLICIES.get(state, STATE_POLICIES[SystemState.HALT])
    settings = get_settings()

    match state:
        case SystemState.TRADING:
            return StatePolicy(
                allow_new_positions=base_policy.allow_new_positions,
                allow_increase_size=base_policy.allow_increase_size,
                allow_new_orders=base_policy.allow_new_orders,
                risk_multiplier=settings.system_trading_risk_multiplier,
                max_positions=settings.system_trading_max_positions,
                max_order_size=settings.system_trading_max_order_size,
                allow_short_selling=base_policy.allow_short_selling,
                require_manual_approval=base_policy.require_manual_approval,
                description=base_policy.description,
            )
        case SystemState.DEGRADED:
            return StatePolicy(
                allow_new_positions=base_policy.allow_new_positions,
                allow_increase_size=base_policy.allow_increase_size,
                allow_new_orders=base_policy.allow_new_orders,
                risk_multiplier=settings.system_degraded_risk_multiplier,
                max_positions=settings.system_degraded_max_positions,
                max_order_size=settings.system_degraded_max_order_size,
                allow_short_selling=base_policy.allow_short_selling,
                require_manual_approval=base_policy.require_manual_approval,
                description=base_policy.description,
            )
        case SystemState.RISK_REDUCTION:
            return StatePolicy(
                allow_new_positions=base_policy.allow_new_positions,
                allow_increase_size=base_policy.allow_increase_size,
                allow_new_orders=base_policy.allow_new_orders,
                risk_multiplier=settings.system_risk_reduction_risk_multiplier,
                max_positions=settings.system_risk_reduction_max_positions,
                max_order_size=settings.system_risk_reduction_max_order_size,
                allow_short_selling=base_policy.allow_short_selling,
                require_manual_approval=base_policy.require_manual_approval,
                description=base_policy.description,
            )
        case SystemState.SURVIVAL:
            return StatePolicy(
                allow_new_positions=base_policy.allow_new_positions,
                allow_increase_size=base_policy.allow_increase_size,
                allow_new_orders=base_policy.allow_new_orders,
                risk_multiplier=settings.system_survival_risk_multiplier,
                max_positions=settings.system_survival_max_positions,
                max_order_size=settings.system_survival_max_order_size,
                allow_short_selling=base_policy.allow_short_selling,
                require_manual_approval=base_policy.require_manual_approval,
                description=base_policy.description,
            )
        case _:
            return base_policy


def get_state_timeout_limit(state: SystemState) -> int | None:
    """Получить таймаут состояния с учётом settings-based overrides."""
    baseline_timeout = MAX_STATE_TIMES.get(state, -1)
    settings = get_settings()

    timeout = baseline_timeout
    match state:
        case SystemState.BOOT:
            timeout = settings.system_boot_max_seconds
        case SystemState.INIT:
            timeout = settings.system_init_max_seconds
        case SystemState.READY:
            timeout = settings.system_ready_max_seconds
        case SystemState.RISK_REDUCTION:
            timeout = settings.system_risk_reduction_max_seconds
        case SystemState.DEGRADED:
            timeout = settings.system_degraded_max_seconds
        case SystemState.SURVIVAL:
            timeout = settings.system_survival_max_seconds
        case SystemState.ERROR:
            timeout = settings.system_error_max_seconds
        case SystemState.RECOVERY:
            timeout = settings.system_recovery_max_seconds
        case _:
            timeout = baseline_timeout

    return timeout if timeout != -1 else None
