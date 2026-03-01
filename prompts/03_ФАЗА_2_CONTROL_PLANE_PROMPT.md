# AI ПРОМТ: ФАЗА 2 - CONTROL PLANE

## КОНТЕКСТ

Вы — Senior Systems Architect, специализирующийся на fault-tolerant distributed systems и state machine design.

**Фаза 1 завершена.** Доступны:
- Event Bus (Rust) — работает, Python bindings готовы
- Structured Logging (Python) — логирование с контекстом
- Database Layer (PostgreSQL + Redis) — подключения работают
- Metrics Collector — метрики собираются
- Health Check System — проверки компонентов

**Текущая задача:** Реализовать Control Plane — единый источник управления системой с детерминированными переходами состояний.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Правила русификации:

#### Python docstrings — ТОЛЬКО русский:

```python
class StateMachine:
    """
    Детерминированная машина состояний.
    
    Особенности:
    - Валидация переходов состояний
    - Audit trail всех изменений
    - Колбэки при входе/выходе
    """
    
    async def transition(self, to_state: SystemState) -> bool:
        """
        Выполнить переход в новое состояние.
        
        Аргументы:
            to_state: Целевое состояние
        
        Возвращает:
            True если переход успешен
        
        Raises:
            ValueError: Если переход недопустим
        """
        pass
```

#### Логи — ТОЛЬКО русский:

```python
logger.info("Переход состояния начат", from_state="TRADING", to_state="DEGRADED")
logger.error("Недопустимый переход состояния", from_state=..., to_state=...)
logger.warning("Watchdog обнаружил проблему", component="database")
```

#### Ошибки — ТОЛЬКО русский:

```python
raise ValueError(f"Недопустимый переход: {from_state} → {to_state}")
raise RuntimeError("Пул соединений не создан")
raise PermissionError("Требуется подтверждение второго оператора")
```

#### Комментарии — ТОЛЬКО русский:

```python
# Проверить что переход допустим
if to_state not in ALLOWED_TRANSITIONS[from_state]:
    # Недопустимый переход - отклонить
    raise ValueError(f"Переход запрещен")

# Выполнить колбэки при выходе из состояния
for callback in self.on_exit_callbacks.get(from_state, []):
    await callback()
```

### Примеры замены:

| ❌ Неправильно | ✅ Правильно |
|----------------|--------------|
| "State transition started" | "Переход состояния начат" |
| "Invalid transition" | "Недопустимый переход" |
| "Watchdog detected issue" | "Watchdog обнаружил проблему" |
| "Health check failed" | "Проверка здоровья не прошла" |
| "Dual control required" | "Требуется двойное подтверждение" |
| "Auto-recovery attempt" | "Попытка автовосстановления" |

---

## ЦЕЛЬ ФАЗЫ

Создать production-ready Control Plane компоненты:

1. **State Machine** — 9 состояний, детерминированные переходы, audit trail
2. **System Controller** — root orchestrator, lifecycle management
3. **Watchdog** — health monitoring, auto-recovery, escalation
4. **Operator Gate** — dual control для критичных операций

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Control Plane — мозг системы CRYPTOTEHNOLOG. State Machine определяет допустимые действия (торговля разрешена только в TRADING/DEGRADED). System Controller оркеструет весь lifecycle. Watchdog следит за здоровьем и автоматически переводит систему в безопасные состояния при проблемах.

### Входящие зависимости (что получает Control Plane):

#### От Event Bus (Фаза 1) - подписки на события:

1. **Risk Engine (Фаза 5)** → `RISK_VIOLATION` event
   - Payload: `{"violation_type": "position_size", "severity": "HIGH", "symbol": "BTC/USDT"}`
   - Частота: 1-10 раз/минуту (при нарушениях)
   - Действие: State Machine переходит TRADING → DEGRADED (HIGH) или SURVIVAL (CRITICAL)
   - Обработка: async, идемпотентная (может получить дубли)

2. **Execution Layer (Фаза 10)** → `EXECUTION_ERROR` event
   - Payload: `{"error_type": "exchange_disconnect", "exchange": "bybit", "severity": "HIGH"}`
   - Частота: редко (аварийные ситуации)
   - Действие: State Machine → DEGRADED, отключить проблемную биржу
   - Обработка: async, требует aggregation (несколько ошибок подряд → деградация)

3. **Kill Switch (Фаза 12)** → `KILL_SWITCH_TRIGGERED` event
   - Payload: `{"kill_level": "HARD_HALT", "reason": "drawdown_exceeded", "operator": "admin"}`
   - Частота: очень редко (аварии)
   - Действие: State Machine → немедленный переход в HALT (минуя все состояния)
   - Обработка: sync (блокирует систему), приоритет CRITICAL

4. **Health Checker (Фаза 1)** → `HEALTH_CHECK_FAILED` event
   - Payload: `{"component": "postgresql", "status": "unhealthy", "details": "connection_timeout"}`
   - Частота: каждые 30 секунд (при проблемах)
   - Действие: Watchdog → auto-recovery или деградация
   - Обработка: async, с debouncing (игнорировать единичные сбои)

5. **Portfolio Governor (Фаза 9)** → `POSITION_CLOSED` event
   - Payload: `{"symbol": "ETH/USDT", "reason": "stop_loss", "pnl_usd": -500.0}`
   - Частота: 10-50 раз/сек
   - Действие: Watchdog → обновить counter открытых позиций, проверить условия для SURVIVAL
   - Обработка: async, at-least-once

#### От других компонентов - прямые вызовы:

6. **System Controller (внутренний)** → `async def startup()`
   - Вызов при запуске системы
   - Выполняет: BOOT → INIT → READY → TRADING
   - Блокирует до завершения инициализации

7. **Operator Gate (внутренний)** → `async def request_transition(to_state, operator1, operator2)`
   - Вызов оператором через CLI/UI
   - Требует: dual control (2 оператора) для критичных переходов (→HALT, →RECOVERY)
   - Блокирует до получения второго подтверждения (timeout 5 минут)

### Исходящие зависимости (что отправляет Control Plane):

#### К Event Bus (публикация событий):

1. → **Event Bus** → `STATE_TRANSITION` event (приоритет: HIGH)
   - Событие: при любом переходе состояния
   - Payload: `{"from_state": "TRADING", "to_state": "DEGRADED", "trigger": "risk_violation", "operator": null}`
   - Подписчики:
     - Observability Dashboard (Фаза 17) — показать на UI
     - Audit Chain (Фаза 16) — записать в immutable log
     - Metrics Collector (Фаза 1) — обновить gauge `system_state`
   - Гарантии: at-least-once

2. → **Event Bus** → `SYSTEM_BOOT`, `SYSTEM_READY`, `SYSTEM_HALT` events (приоритет: HIGH)
   - События: при старте/готовности/остановке
   - Подписчики: все компоненты (для синхронизации)
   - Гарантии: at-least-once

3. → **Event Bus** → `WATCHDOG_ALERT` event (приоритет: HIGH)
   - Событие: Watchdog обнаружил проблему
   - Payload: `{"component": "execution_layer", "issue": "latency_high", "action": "restart"}`
   - Подписчики: Observability, Telegram alerting
   - Гарантии: best-effort (alert может потеряться)

#### К другим компонентам - прямые вызовы:

4. → **Risk Engine (Фаза 5)** → `async def pause_trading()`
   - Вызов: при переходе TRADING → DEGRADED/SURVIVAL/HALT
   - Действие: Risk Engine прекращает одобрять новые сделки
   - Синхронный вызов, timeout 1 сек

5. → **Execution Layer (Фаза 10)** → `async def cancel_all_orders()`
   - Вызов: при переходе → SURVIVAL или HALT
   - Действие: отменить все активные ордера на всех биржах
   - Async, fire-and-forget (best-effort)

6. → **Strategy Manager (Фаза 14)** → `async def disable_all_strategies()`
   - Вызов: при переходе → DEGRADED/SURVIVAL/HALT
   - Действие: остановить генерацию новых сигналов
   - Async, fire-and-forget

7. → **Database (Фаза 1)** → `INSERT INTO state_transitions`
   - Вызов: при каждом переходе (audit trail)
   - Данные: полная история переходов с timestamp, trigger, operator
   - Sync, транзакционный (критично для аудита)

### Контракты данных:

#### SystemState Enum:

```python
class SystemState(str, Enum):
    """Состояния системы с четкой семантикой."""
    BOOT = "boot"            # Загрузка (0-30 сек после старта)
    INIT = "init"            # Инициализация компонентов (проверка БД, Redis, биржи)
    READY = "ready"          # Готова, но не торгует (ожидание сигнала оператора)
    TRADING = "trading"      # Нормальная торговля (100% функциональность)
    DEGRADED = "degraded"    # Деградированный режим (торговля продолжается, но ограничена)
    SURVIVAL = "survival"    # Режим выживания (только закрытие позиций)
    ERROR = "error"          # Критическая ошибка (требуется вмешательство)
    HALT = "halt"            # Полная остановка (все операции запрещены)
    RECOVERY = "recovery"    # Восстановление после ошибки
```

#### StateTransition Data Contract (JSON):

```json
{
  "transition_id": 12345,
  "from_state": "TRADING",
  "to_state": "DEGRADED",
  "trigger": "risk_violation",
  "timestamp": "2024-02-06T12:34:56.789Z",
  "metadata": {
    "violation_type": "position_size",
    "severity": "HIGH",
    "auto_transition": true
  },
  "operator": null,
  "duration_ms": 45
}
```

#### Watchdog Health Check Data Contract:

```json
{
  "component": "execution_layer",
  "status": "unhealthy",
  "checks": [
    {
      "name": "api_latency",
      "status": "failed",
      "value": 1500,
      "threshold": 500,
      "unit": "ms"
    },
    {
      "name": "order_fill_rate",
      "status": "passed",
      "value": 0.95,
      "threshold": 0.90
    }
  ],
  "last_check": "2024-02-06T12:34:56Z",
  "consecutive_failures": 3
}
```

#### Operator Gate Dual Control Contract:

```python
@dataclass
class DualControlRequest:
    """Запрос на выполнение критичной операции."""
    request_id: str
    operation: str  # "transition_to_halt", "emergency_shutdown"
    target_state: Optional[SystemState]
    operator1: str  # Первый оператор (инициатор)
    operator2: Optional[str]  # Второй оператор (подтвердивший)
    created_at: datetime
    expires_at: datetime  # +5 минут
    approved: bool
    metadata: Dict[str, Any]
```

### State Machine API:

```python
class StateMachine:
    """
    Детерминированная машина состояний.
    
    Особенности:
    - Валидация переходов (ALLOWED_TRANSITIONS)
    - Audit trail (все переходы в БД)
    - Callbacks (on_enter/on_exit)
    - Metrics (time in state, transition count)
    """
    
    async def transition(
        self,
        to_state: SystemState,
        trigger: str,
        metadata: Optional[Dict] = None,
        operator: Optional[str] = None,
    ) -> bool:
        """
        Выполнить переход в новое состояние.
        
        Аргументы:
            to_state: Целевое состояние
            trigger: Причина перехода ("risk_violation", "operator_request")
            metadata: Дополнительный контекст
            operator: Имя оператора (для ручных переходов)
        
        Raises:
            ValueError: Если переход недопустим
        
        Returns:
            True если переход успешен
        """
        pass
    
    def can_trade(self) -> bool:
        """Проверить разрешена ли торговля в текущем состоянии."""
        return self.current_state in {
            SystemState.TRADING,
            SystemState.DEGRADED,
        }
    
    def requires_dual_control(self, to_state: SystemState) -> bool:
        """Проверить требуется ли dual control для перехода."""
        # HALT, RECOVERY требуют 2 операторов
        return to_state in {SystemState.HALT, SystemState.RECOVERY}
```

### Sequence Diagram (State Transition Flow):

```
[Risk Engine] ──RISK_VIOLATION event──> [Event Bus]
                                             |
                                             v
                                      [State Machine]
                                             |
                                             |─validate transition (TRADING→DEGRADED)
                                             |─execute on_exit(TRADING) callbacks
                                             |─update current_state = DEGRADED
                                             |─execute on_enter(DEGRADED) callbacks
                                             |
                    ┌────────────────────────┼────────────────────────┐
                    v                        v                        v
            [Database: INSERT]      [Event Bus: publish]     [Risk Engine: pause]
         state_transitions table    STATE_TRANSITION event      trading paused
                    |                        |                        |
                    v                        v                        v
            Audit trail saved        Observability notified    No new trades allowed
```

### Sequence Diagram (Watchdog Auto-Recovery):

```
[Watchdog] ──check_health()──> [PostgreSQL]
                                     |
                                     v
                              connection timeout
                                     |
                                     v
                              [Watchdog: retry]
                                     |
                                     |─attempt #1: fail
                                     |─attempt #2: fail
                                     |─attempt #3: fail
                                     |
                                     v
                           [Watchdog: escalate]
                                     |
                    ┌────────────────┼────────────────┐
                    v                                  v
            [State Machine]                    [Event Bus]
       transition(DEGRADED)              WATCHDOG_ALERT event
                    |                                  |
                    v                                  v
            System degraded                     Telegram alert
```

### Обработка ошибок интеграции:

#### 1. Event Bus недоступен:
- **Проблема:** Не можем опубликовать STATE_TRANSITION event
- **Решение:** 
  - Transition все равно выполняется (критично)
  - Event сохраняется в локальную очередь (Redis)
  - Retry публикации каждые 10 секунд до успеха
  - Метрика: `state_machine_event_publish_failures_total`

#### 2. Database недоступна:
- **Проблема:** Не можем сохранить transition в audit trail
- **Решение:**
  - Transition БЛОКИРУЕТСЯ (аудит критичен)
  - Retry 3 раза с exponential backoff
  - Если все провалились → переход в ERROR state
  - Alert оператору (Telegram)

#### 3. Risk Engine не отвечает на pause_trading():
- **Проблема:** Таймаут при вызове pause_trading()
- **Решение:**
  - Timeout: 1 секунда
  - Если таймаут → логировать WARNING
  - Transition продолжается (система деградирует в безопасное состояние)
  - Метрика: `risk_engine_pause_timeout_total`

#### 4. Dual Control timeout:
- **Проблема:** Второй оператор не подтвердил за 5 минут
- **Решение:**
  - Request автоматически отклоняется
  - Логируется в audit trail
  - Уведомление в Telegram: "Dual control expired: {request_id}"
  - Первый оператор должен создать новый request

#### 5. Concurrent state transitions:
- **Проблема:** Два компонента пытаются изменить state одновременно
- **Решение:**
  - Mutex lock на уровне StateMachine
  - Первый получает lock и выполняет transition
  - Второй ждет завершения, затем проверяет актуальность своего перехода
  - Если состояние изменилось → может отменить свой переход

### Мониторинг интеграций:

#### Метрики State Machine:

```python
# Counters
state_transitions_total{from_state, to_state, trigger}
state_transition_failures_total{from_state, to_state, reason}
invalid_transition_attempts_total{from_state, to_state}

# Gauges
current_system_state{state}  # 1 для текущего, 0 для остальных
time_in_state_seconds{state}

# Histograms
state_transition_duration_seconds{from_state, to_state, percentile}
```

#### Метрики Watchdog:

```python
# Counters
watchdog_health_checks_total{component, status}
watchdog_auto_recovery_attempts_total{component, action}
watchdog_escalations_total{component, reason}

# Gauges
component_health_status{component}  # 1=healthy, 0=unhealthy
consecutive_health_check_failures{component}
```

#### Метрики Operator Gate:

```python
# Counters
dual_control_requests_total{operation, status}  # status: approved, denied, expired
dual_control_approvals_total{operator}

# Histograms
dual_control_approval_time_seconds{operation, percentile}
```

#### Alerts:

**Critical (PagerDuty):**
- `current_system_state{state="ERROR"}` для 60 секунд
- `current_system_state{state="HALT"}` немедленно
- `watchdog_escalations_total` rate > 5/минуту

**Warning (Telegram):**
- `current_system_state{state="DEGRADED"}` для 5 минут
- `state_transition_failures_total` > 3 за 1 минуту
- `invalid_transition_attempts_total` > 10 за 1 минуту
- `dual_control_requests_total{status="expired"}` > 2 за 1 час

### Integration Test Scenarios:

#### Тест 1: Risk Violation → Auto Degradation

```python
async def test_risk_violation_triggers_degradation():
    """
    Проверить автоматический переход при нарушении риска.
    
    Flow:
    1. Система в TRADING
    2. Risk Engine публикует RISK_VIOLATION (HIGH severity)
    3. State Machine получает event
    4. Переход TRADING → DEGRADED
    5. STATE_TRANSITION event опубликован
    6. Risk Engine получил pause_trading()
    """
    # Setup
    state_machine = StateMachine(db)
    await state_machine.transition(SystemState.TRADING, "test_setup")
    
    # Simulate risk violation
    event_bus.publish(Event(
        event_type="RISK_VIOLATION",
        source="risk_engine",
        payload={"severity": "HIGH"},
        priority=Priority.High,
    ))
    
    # Wait for async processing
    await asyncio.sleep(0.1)
    
    # Assert
    assert state_machine.get_state() == SystemState.DEGRADED
    assert metrics.get("state_transitions_total") == 2  # setup + auto
```

#### Тест 2: Watchdog Auto-Recovery

```python
async def test_watchdog_database_recovery():
    """
    Проверить автоматическое восстановление БД через Watchdog.
    
    Flow:
    1. PostgreSQL connection fails
    2. Watchdog обнаруживает 3 consecutive failures
    3. Watchdog пытается reconnect
    4. Если успех → восстановление, иначе → деградация
    """
    # Simulate DB failure
    await db.disconnect()
    
    # Watchdog checks
    for i in range(3):
        result = await watchdog.check_component("postgresql")
        assert result.status == HealthStatus.UNHEALTHY
    
    # Auto-recovery attempt
    recovery_result = await watchdog.auto_recover("postgresql")
    
    # Assert
    if recovery_result.success:
        assert db.pool is not None
        assert state_machine.get_state() == SystemState.TRADING
    else:
        assert state_machine.get_state() == SystemState.DEGRADED
```

#### Тест 3: Dual Control Flow

```python
async def test_dual_control_halt_request():
    """
    Проверить dual control для перехода в HALT.
    
    Flow:
    1. Operator1 запрашивает переход → HALT
    2. Request создан, ожидает Operator2
    3. Operator2 подтверждает
    4. Переход выполнен
    """
    # Operator1 initiates
    request_id = await operator_gate.request_transition(
        to_state=SystemState.HALT,
        operator="admin1",
        reason="emergency_maintenance",
    )
    
    # Assert: pending approval
    request = await operator_gate.get_request(request_id)
    assert request.approved == False
    assert state_machine.get_state() == SystemState.TRADING  # unchanged
    
    # Operator2 approves
    await operator_gate.approve_request(
        request_id=request_id,
        operator="admin2",
    )
    
    # Assert: transition executed
    assert state_machine.get_state() == SystemState.HALT
```

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 2

### State Machine (без optimistic locking):

**✅ Что реализовано:**
- Детерминированные переходы (ALLOWED_TRANSITIONS)
- Audit trail (все переходы в БД)
- Callbacks (on_enter/on_exit)
- Version history (10 последних переходов)

**❌ Что НЕ реализовано (улучшения ниже):**
- Optimistic concurrency control
- Distributed consensus (при масштабировании)
- Rollback transactions при failures
- Circuit breaker для внешних зависимостей

**⚠️ ВАЖНО:**
```markdown
State Machine в Фазе 2 работает только в single-instance режиме.
Для multi-instance deployment требуется:
- Фаза 18: Distributed consensus (etcd/Consul)
- Optimistic locking (реализовать ниже)

Race conditions возможны при:
- Concurrent state transitions (два компонента одновременно)
- Database replication lag
```

### Production Readiness Matrix:

| Компонент | После Фазы 2 | Production Ready |
|-----------|--------------|------------------|
| State Machine | ⚠️ Single instance only | ✅ Требует optimistic locking |
| System Controller | ✅ Ready | ✅ Ready |
| Watchdog | ⚠️ Без circuit breaker | ✅ Требует circuit breaker (ниже) |
| Operator Gate | ⚠️ Без auth | ✅ Требует Фазу 4 (Vault integration) |

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ И CONCURRENCY

### Критические проблемы concurrency:

#### 1. Race condition при concurrent state transitions

**Проблема:** Два компонента пытаются изменить state одновременно.

**Текущая реализация (НЕБЕЗОПАСНА):**
```python
class StateMachine:
    async def transition(self, to_state: SystemState, ...) -> bool:
        # 1. Прочитать current_state
        # 2. Проверить переход
        # 3. UPDATE в БД
        # ❌ Между 1 и 3 кто-то мог изменить состояние!
```

**Решение: Optimistic Concurrency Control**

```python
class StateMachine:
    def __init__(self, db: PostgreSQLManager):
        self.db = db
        self.current_state = SystemState.BOOT
        self.version = 0  # ✅ НОВОЕ: версия для optimistic locking
        self.transition_history: list[StateTransition] = []
        self._transition_lock = asyncio.Lock()  # ✅ Local lock
    
    async def transition(
        self,
        to_state: SystemState,
        trigger: str,
        metadata: Optional[Dict] = None,
        operator: Optional[str] = None,
        max_retries: int = 3,
    ) -> bool:
        """
        Выполнить переход с optimistic locking.
        
        ОБЯЗАТЕЛЬНО реализовать:
        1. Прочитать current version из БД
        2. Проверить переход
        3. UPDATE WHERE version = :current_version
        4. Если updated_rows == 0 → retry (кто-то уже изменил)
        """
        async with self._transition_lock:
            for attempt in range(max_retries):
                try:
                    # 1. Прочитать текущее состояние и версию из БД
                    row = await self.db.fetchrow(
                        """
                        SELECT current_state, version 
                        FROM system_state 
                        WHERE id = 1 
                        FOR UPDATE NOWAIT
                        """,
                        timeout=1.0,
                    )
                    
                    db_state = SystemState(row['current_state'])
                    db_version = row['version']
                    
                    # 2. Проверить допустимость перехода
                    if to_state not in self.ALLOWED_TRANSITIONS[db_state]:
                        logger.error(
                            "Недопустимый переход состояния",
                            from_state=db_state.value,
                            to_state=to_state.value,
                        )
                        raise ValueError(
                            f"Недопустимый переход: {db_state} → {to_state}"
                        )
                    
                    # 3. Выполнить on_exit callbacks
                    if db_state in self.on_exit_callbacks:
                        for callback in self.on_exit_callbacks[db_state]:
                            await callback(db_state, to_state)
                    
                    # 4. UPDATE с проверкой version (optimistic lock)
                    result = await self.db.execute(
                        """
                        UPDATE system_state 
                        SET current_state = $1, 
                            version = version + 1,
                            updated_at = NOW()
                        WHERE id = 1 AND version = $2
                        """,
                        to_state.value,
                        db_version,
                    )
                    
                    # Проверить что обновили
                    if "UPDATE 0" in result:
                        # Кто-то другой уже изменил состояние
                        logger.warning(
                            "Optimistic lock conflict, retry",
                            attempt=attempt + 1,
                            expected_version=db_version,
                        )
                        await asyncio.sleep(0.01 * (2 ** attempt))  # exponential backoff
                        continue  # Retry
                    
                    # 5. Выполнить on_enter callbacks
                    if to_state in self.on_enter_callbacks:
                        for callback in self.on_enter_callbacks[to_state]:
                            await callback(db_state, to_state)
                    
                    # 6. Обновить локальный state
                    self.current_state = to_state
                    self.version = db_version + 1
                    
                    # 7. Записать в audit trail
                    await self._persist_transition(StateTransition(
                        from_state=db_state,
                        to_state=to_state,
                        trigger=trigger,
                        timestamp=datetime.utcnow(),
                        metadata=metadata or {},
                        operator=operator,
                    ))
                    
                    logger.info(
                        "Переход состояния выполнен",
                        from_state=db_state.value,
                        to_state=to_state.value,
                        version=self.version,
                    )
                    
                    return True
                    
                except asyncio.TimeoutError:
                    # FOR UPDATE NOWAIT timeout
                    logger.warning(
                        "Не удалось получить lock на system_state",
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(0.01 * (2 ** attempt))
                    continue
                    
            # Все попытки провалились
            logger.error(
                "Не удалось выполнить переход после всех попыток",
                max_retries=max_retries,
            )
            return False
    
    def get_effective_state(self) -> SystemState:
        """
        Получить "эффективное" состояние для проверок.
        
        КРИТИЧНО для координации с другими компонентами:
        Risk Engine должен проверять can_trade() через этот метод.
        """
        return self.current_state
```

#### 2. Coordination с другими компонентами

**Проблема:** Risk Engine может проверить `can_trade()` МЕЖДУ началом и концом перехода.

**Решение: Source of Truth pattern**

```python
# src/core/state_machine.py

class StateMachine:
    def can_trade(self) -> bool:
        """
        Проверить разрешена ли торговля.
        
        ПРАВИЛО: Компоненты ВСЕГДА должны проверять через этот метод,
        а не кэшировать локально.
        """
        return self.current_state in {
            SystemState.TRADING,
            SystemState.DEGRADED,
        }
    
    def is_transitioning(self) -> bool:
        """Проверить идет ли переход прямо сейчас."""
        return self._transition_lock.locked()
```

**Правильное использование в Risk Engine:**

```python
# src/risk/engine.py (Фаза 5)

class RiskEngine:
    def __init__(self, state_machine: StateMachine):
        self.state_machine = state_machine
    
    async def check_trade(self, order: Order) -> RiskCheckResult:
        # ✅ ПРАВИЛЬНО: всегда проверять через State Machine
        if not self.state_machine.can_trade():
            return RiskCheckResult(
                allowed=False,
                reason="system_not_in_trading_mode",
                current_state=self.state_machine.get_effective_state().value,
            )
        
        # ❌ НЕПРАВИЛЬНО: кэшировать локально
        # if self.cached_can_trade:  # НЕ ДЕЛАТЬ ТАК!
```

#### 3. Watchdog infinite restart loop

**Проблема:** Компонент падает сразу после рестарта → бесконечный цикл.

**Решение: Circuit Breaker pattern**

```python
# src/core/watchdog.py

from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta

class CircuitState(Enum):
    """Состояния circuit breaker."""
    CLOSED = "closed"      # Нормальная работа
    OPEN = "open"          # Слишком много сбоев, блокировать
    HALF_OPEN = "half_open"  # Пробная проверка

@dataclass
class CircuitBreaker:
    """Circuit breaker для компонента."""
    component: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    
    # Пороги
    failure_threshold: int = 5  # Открыть после 5 сбоев
    timeout_seconds: int = 300  # Держать открытым 5 минут
    half_open_max_attempts: int = 3

class Watchdog:
    def __init__(self, ...):
        # ...
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.max_restart_attempts = 3
    
    def _get_circuit_breaker(self, component: str) -> CircuitBreaker:
        """Получить или создать circuit breaker."""
        if component not in self.circuit_breakers:
            self.circuit_breakers[component] = CircuitBreaker(component=component)
        return self.circuit_breakers[component]
    
    def _is_circuit_open(self, component: str) -> bool:
        """Проверить открыт ли circuit breaker."""
        cb = self._get_circuit_breaker(component)
        
        if cb.state == CircuitState.OPEN:
            # Проверить не истек ли timeout
            if cb.opened_at and datetime.utcnow() - cb.opened_at > timedelta(seconds=cb.timeout_seconds):
                # Перейти в HALF_OPEN
                cb.state = CircuitState.HALF_OPEN
                logger.info(
                    "Circuit breaker перешел в HALF_OPEN",
                    component=component,
                )
                return False
            return True
        
        return False
    
    async def _handle_unhealthy_component(
        self,
        component: str,
        health_result: ComponentHealth,
    ):
        """
        Обработать нездоровый компонент.
        """
        cb = self._get_circuit_breaker(component)
        
        # Проверить circuit breaker
        if self._is_circuit_open(component):
            logger.warning(
                "Circuit breaker ОТКРЫТ, пропуск auto-recovery",
                component=component,
                wait_seconds=cb.timeout_seconds,
            )
            # Эскалация к человеку
            await self._escalate_to_operator(component, health_result)
            return
        
        # Увеличить счетчик сбоев
        cb.failure_count += 1
        cb.last_failure = datetime.utcnow()
        
        logger.warning(
            "Попытка auto-recovery",
            component=component,
            failure_count=cb.failure_count,
            threshold=cb.failure_threshold,
        )
        
        # Попытка восстановления
        recovery_success = await self._attempt_recovery(component)
        
        if recovery_success:
            # Сброс circuit breaker
            cb.failure_count = 0
            cb.state = CircuitState.CLOSED
            logger.info("Auto-recovery успешно", component=component)
        else:
            # Проверить порог
            if cb.failure_count >= cb.failure_threshold:
                # Открыть circuit breaker
                cb.state = CircuitState.OPEN
                cb.opened_at = datetime.utcnow()
                
                logger.critical(
                    "Circuit breaker ОТКРЫТ",
                    component=component,
                    failures=cb.failure_count,
                    wait_seconds=cb.timeout_seconds,
                )
                
                # Деградация системы
                await self.state_machine.transition(
                    SystemState.DEGRADED,
                    trigger=f"circuit_breaker_open:{component}",
                    metadata={"component": component, "failures": cb.failure_count},
                )
                
                # Эскалация
                await self._escalate_to_operator(component, health_result)
    
    async def _escalate_to_operator(
        self,
        component: str,
        health_result: ComponentHealth,
    ):
        """
        Эскалация к оператору (Telegram alert).
        """
        message = f"""
🚨 ТРЕБУЕТСЯ ВМЕШАТЕЛЬСТВО ОПЕРАТОРА

Компонент: {component}
Статус: {health_result.status.value}
Circuit Breaker: ОТКРЫТ
Деталь: {health_result.details}

Auto-recovery провалился {self.circuit_breakers[component].failure_count} раз.
Система переведена в DEGRADED режим.

Действия:
1. Проверить логи компонента
2. Исправить проблему вручную
3. Сбросить circuit breaker через Operator Gate
        """
        
        logger.critical("Эскалация к оператору", component=component)
        # TODO: Отправить в Telegram (Фаза 17)
```

#### 4. Operator Gate без аутентификации

**Проблема:** Любой может сказать "я operator2".

**Решение: Token-based authentication (stub для Фазы 4)**

```python
# src/core/operator_gate.py

from typing import Protocol

class AuthProvider(Protocol):
    """Интерфейс провайдера аутентификации."""
    async def verify_operator(self, operator: str, token: str) -> bool:
        """Проверить что оператор имеет валидный токен."""
        ...

class VaultAuthProvider:
    """Аутентификация через Vault (реализация в Фазе 4)."""
    
    def __init__(self, vault_client):
        self.vault = vault_client
    
    async def verify_operator(self, operator: str, token: str) -> bool:
        """Проверить токен оператора через Vault."""
        try:
            # Проверить токен в Vault
            response = self.vault.auth.token.lookup(token)
            # Проверить что токен принадлежит оператору
            metadata = response.get('data', {}).get('metadata', {})
            return metadata.get('operator_name') == operator
        except Exception as e:
            logger.error("Ошибка проверки токена", operator=operator, error=str(e))
            return False

class StubAuthProvider:
    """Заглушка аутентификации (для Фазы 2)."""
    
    async def verify_operator(self, operator: str, token: str) -> bool:
        """ЗАГЛУШКА: всегда возвращает True."""
        logger.warning(
            "⚠️  Используется ЗАГЛУШКА аутентификации",
            operator=operator,
            note="Для production требуется VaultAuthProvider (Фаза 4)",
        )
        return True

class OperatorGate:
    def __init__(
        self,
        db: PostgreSQLManager,
        state_machine: StateMachine,
        auth_provider: Optional[AuthProvider] = None,
    ):
        self.db = db
        self.state_machine = state_machine
        self.auth = auth_provider or StubAuthProvider()
        self.pending_requests: Dict[str, DualControlRequest] = {}
    
    async def request_transition(
        self,
        to_state: SystemState,
        operator: str,
        token: str,  # ✅ НОВОЕ: токен аутентификации
        reason: str,
    ) -> str:
        """
        Запросить переход состояния (требует dual control).
        
        ОБЯЗАТЕЛЬНО: проверить токен оператора.
        """
        # Проверить токен
        if not await self.auth.verify_operator(operator, token):
            logger.error(
                "Недопустимый токен оператора",
                operator=operator,
            )
            raise PermissionError(f"Неверные учетные данные: {operator}")
        
        # ... создать request
    
    async def approve_request(
        self,
        request_id: str,
        approver: str,
        token: str,  # ✅ НОВОЕ: токен второго оператора
    ) -> bool:
        """
        Подтвердить запрос (второй оператор).
        """
        # Проверить токен
        if not await self.auth.verify_operator(approver, token):
            raise PermissionError(f"Неверные учетные данные: {approver}")
        
        request = self.pending_requests.get(request_id)
        if not request:
            raise ValueError(f"Request не найден: {request_id}")
        
        # Проверить что это ДРУГОЙ оператор
        if approver == request.operator1:
            raise PermissionError("Нельзя подтвердить свой же запрос")
        
        # ... выполнить переход
```

---

## 📊 ОБЯЗАТЕЛЬНЫЕ BENCHMARK ТЕСТЫ

### tests/benchmarks/bench_state_machine.py:

```python
import pytest
import asyncio
from src.core.state_machine import StateMachine, SystemState

@pytest.mark.benchmark
async def test_state_transition_latency():
    """
    Проверить latency одного перехода состояния.
    
    Acceptance: p99 < 50ms (включая запись в БД)
    """
    state_machine = StateMachine(db)
    
    # Warm-up
    await state_machine.transition(SystemState.INIT, "benchmark")
    
    # Измерить
    latencies = []
    for _ in range(100):
        start = asyncio.get_event_loop().time()
        await state_machine.transition(SystemState.READY, "bench")
        await state_machine.transition(SystemState.INIT, "bench")
        end = asyncio.get_event_loop().time()
        latencies.append((end - start) * 1000)  # ms
    
    # Assertions
    p99 = sorted(latencies)[98]
    assert p99 < 50, f"p99 latency {p99}ms > 50ms"
    
    median = sorted(latencies)[49]
    assert median < 10, f"median latency {median}ms > 10ms"

@pytest.mark.benchmark
async def test_concurrent_transitions():
    """
    Проверить что concurrent transitions не создают race conditions.
    
    Acceptance: все переходы успешны или корректно откл

онены
    """
    state_machine = StateMachine(db)
    await state_machine.transition(SystemState.TRADING, "setup")
    
    # 10 компонентов пытаются перевести в DEGRADED одновременно
    tasks = []
    for i in range(10):
        task = asyncio.create_task(
            state_machine.transition(
                SystemState.DEGRADED,
                trigger=f"concurrent_{i}",
            )
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Только ОДИН должен успешно перейти
    successful = [r for r in results if r is True]
    assert len(successful) == 1, f"Expected 1 success, got {len(successful)}"
    
    # Финальное состояние - DEGRADED
    assert state_machine.get_state() == SystemState.DEGRADED

@pytest.mark.benchmark
async def test_watchdog_recovery_time():
    """
    Проверить скорость auto-recovery Watchdog.
    
    Acceptance: recovery < 5 секунд от обнаружения до восстановления
    """
    watchdog = Watchdog(db, state_machine)
    
    # Simulate DB failure
    await db.disconnect()
    
    start = asyncio.get_event_loop().time()
    
    # Watchdog обнаружит и восстановит
    result = await watchdog.check_and_recover("postgresql")
    
    end = asyncio.get_event_loop().time()
    recovery_time = end - start
    
    assert result.recovered == True
    assert recovery_time < 5.0, f"Recovery took {recovery_time}s > 5s"
```

**Acceptance Criteria:**
```
✅ state_transition_latency: median <10ms, p99 <50ms
✅ concurrent_transitions: no race conditions, exactly 1 success
✅ watchdog_recovery_time: <5 seconds
✅ circuit_breaker: opens after threshold, closes after timeout
```

---

## ФАЙЛОВАЯ СТРУКТУРА

Создайте следующие файлы с ПОЛНЫМ рабочим кодом:

```
CRYPTOTEHNOLOG/
├── src/
│   └── core/
│       ├── state_machine.py
│       ├── system_controller.py
│       ├── watchdog.py
│       ├── operator_gate.py
│       ├── circuit_breaker.py          # ✅ НОВОЕ: circuit breaker паттерн
│       └── auth_providers.py           # ✅ НОВОЕ: auth для Operator Gate
│
└── tests/
    ├── unit/
    │   ├── test_state_machine.py
    │   ├── test_system_controller.py
    │   ├── test_watchdog.py
    │   ├── test_operator_gate.py
    │   └── test_circuit_breaker.py     # ✅ НОВОЕ: тесты circuit breaker
    ├── integration/
    │   ├── test_control_plane.py
    │   └── test_concurrent_transitions.py  # ✅ НОВОЕ: concurrency тесты
    └── benchmarks/                      # ✅ НОВОЕ: benchmarks
        ├── bench_state_machine.py
        └── bench_watchdog.py
```

---

## ЗАВИСИМОСТИ (уже реализованы в Фазе 1)

```python
from src.core.logger import get_logger
from src.core.database import PostgreSQLManager
from src.core.redis_manager import RedisManager
from src.core.metrics import MetricsCollector
from src.core.health import HealthChecker, HealthStatus
from src.core.stubs import (              # ✅ НОВОЕ: заглушки из Фазы 1
    RiskEngineStub,
    ExecutionLayerStub,
    StrategyManagerStub,
)
```

---

## ТРЕБОВАНИЯ

### 1. State Machine (src/core/state_machine.py)

**Создайте детерминированный state machine с:**

```python
class SystemState(str, Enum):
    """System states - полная модель жизненного цикла."""
    BOOT = "boot"           # Загрузка системы
    INIT = "init"           # Инициализация компонентов
    READY = "ready"         # Готова к работе
    TRADING = "trading"     # Нормальная торговля
    DEGRADED = "degraded"   # Деградированный режим
    SURVIVAL = "survival"   # Выживание (только закрытие)
    ERROR = "error"         # Критическая ошибка
    HALT = "halt"           # Полная остановка
    RECOVERY = "recovery"   # Восстановление
```

**Transitions Matrix (обязательно реализовать):**
```python
ALLOWED_TRANSITIONS: Dict[SystemState, Set[SystemState]] = {
    SystemState.BOOT: {SystemState.INIT, SystemState.ERROR},
    SystemState.INIT: {SystemState.READY, SystemState.ERROR},
    SystemState.READY: {SystemState.TRADING, SystemState.HALT},
    SystemState.TRADING: {
        SystemState.DEGRADED,
        SystemState.SURVIVAL,
        SystemState.HALT,
        SystemState.READY,
    },
    SystemState.DEGRADED: {
        SystemState.TRADING,
        SystemState.SURVIVAL,
        SystemState.HALT,
    },
    SystemState.SURVIVAL: {SystemState.HALT},
    SystemState.ERROR: {SystemState.HALT, SystemState.RECOVERY},
    SystemState.RECOVERY: {SystemState.READY, SystemState.HALT},
    SystemState.HALT: {SystemState.RECOVERY},
}
```

**Обязательные методы:**
```python
class StateMachine:
    def __init__(self, db: PostgreSQLManager):
        pass
    
    async def transition(
        self,
        to_state: SystemState,
        trigger: str,
        metadata: Optional[Dict] = None,
        operator: Optional[str] = None,
    ) -> bool:
        """
        Transition to new state.
        
        MUST:
        - Validate transition against ALLOWED_TRANSITIONS
        - Raise ValueError if invalid
        - Execute on_exit callbacks (если есть)
        - Update current_state
        - Execute on_enter callbacks (если есть)
        - Record in transition_history
        - Persist to database
        - Log transition
        """
        pass
    
    def register_on_enter(self, state: SystemState, callback: Callable):
        """Register callback for state entry."""
        pass
    
    def register_on_exit(self, state: SystemState, callback: Callable):
        """Register callback for state exit."""
        pass
    
    def get_state(self) -> SystemState:
        """Get current state."""
        pass
    
    def can_trade(self) -> bool:
        """Check if system can execute trades."""
        return self.current_state in {SystemState.TRADING, SystemState.DEGRADED}
    
    def is_operational(self) -> bool:
        """Check if system is operational."""
        return self.current_state not in {SystemState.ERROR, SystemState.HALT}
    
    async def force_halt(self, reason: str, operator: Optional[str] = None):
        """Emergency halt (bypasses validation)."""
        pass
    
    async def init_schema(self):
        """Create state_transitions table."""
        pass
```

**Database Schema:**
```sql
CREATE TABLE IF NOT EXISTS state_transitions (
    id BIGSERIAL PRIMARY KEY,
    from_state VARCHAR(50) NOT NULL,
    to_state VARCHAR(50) NOT NULL,
    trigger VARCHAR(100) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    metadata JSONB,
    operator VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_transitions_timestamp ON state_transitions(timestamp DESC);
CREATE INDEX idx_transitions_to_state ON state_transitions(to_state);
```

---

### 2. System Controller (src/core/system_controller.py)

**Root orchestrator для lifecycle management:**

```python
class SystemController:
    """
    Orchestrate system lifecycle through states.
    """
    
    def __init__(
        self,
        db: PostgreSQLManager,
        redis: RedisManager,
        state_machine: StateMachine,
    ):
        self.db = db
        self.redis = redis
        self.state_machine = state_machine
        self.metrics: Optional[MetricsCollector] = None
        self.health_checker: Optional[HealthChecker] = None
        self.is_running = False
        self.shutdown_event = asyncio.Event()
    
    async def boot(self):
        """
        Boot system from BOOT state.
        
        MUST:
        1. Check current_state == BOOT
        2. Connect to infrastructure (db, redis)
        3. Initialize schemas
        4. Transition to INIT
        5. Handle errors -> ERROR state
        """
        pass
    
    async def initialize(self):
        """
        Initialize all components.
        
        MUST:
        1. Check current_state == INIT
        2. Initialize MetricsCollector
        3. Initialize HealthChecker
        4. Run initial health check
        5. If all healthy -> transition to READY
        6. If unhealthy -> transition to ERROR
        """
        pass
    
    async def start_trading(self):
        """
        Start trading mode.
        
        MUST:
        1. Check current_state == READY
        2. Start trading components (TODO: later phases)
        3. Transition to TRADING
        4. Set is_running = True
        """
        pass
    
    async def degrade(self, reason: str):
        """Transition to DEGRADED mode."""
        pass
    
    async def survival_mode(self, reason: str):
        """Enter SURVIVAL mode (close-only)."""
        pass
    
    async def halt(self, reason: str, operator: Optional[str] = None):
        """
        Halt system.
        
        MUST:
        1. Call state_machine.force_halt()
        2. Stop background tasks (metrics flush, etc.)
        3. Set is_running = False
        4. Trigger shutdown_event
        """
        pass
    
    async def shutdown(self):
        """
        Graceful shutdown.
        
        MUST:
        1. Halt if not already halted
        2. Disconnect from infrastructure
        3. Log shutdown completion
        """
        pass
    
    async def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self.shutdown_event.wait()
```

---

### 3. Watchdog (src/core/watchdog.py)

**Health monitoring с auto-recovery:**

```python
@dataclass
class WatchdogConfig:
    check_interval_seconds: int = 30
    unhealthy_threshold: int = 3
    restart_cooldown_seconds: int = 60
    max_restart_attempts: int = 3


class Watchdog:
    """
    Monitor component health and auto-recover.
    """
    
    def __init__(
        self,
        health_checker: HealthChecker,
        metrics: MetricsCollector,
        config: Optional[WatchdogConfig] = None,
    ):
        self.health_checker = health_checker
        self.metrics = metrics
        self.config = config or WatchdogConfig()
        
        # Tracking
        self.failure_counts: Dict[str, int] = {}
        self.restart_counts: Dict[str, int] = {}
        self.last_restart: Dict[str, datetime] = {}
        
        # Recovery callbacks
        self.recovery_callbacks: Dict[str, Callable] = {}
        
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
    
    def register_recovery_callback(self, component: str, callback: Callable):
        """Register recovery callback for component."""
        pass
    
    async def start(self):
        """Start watchdog monitoring loop."""
        pass
    
    async def stop(self):
        """Stop watchdog."""
        pass
    
    async def _monitoring_loop(self):
        """
        Main monitoring loop.
        
        MUST:
        1. While is_running
        2. Call _check_components()
        3. Sleep check_interval_seconds
        """
        pass
    
    async def _check_components(self):
        """
        Run health checks and take action.
        
        MUST:
        1. Run health_checker.check_all()
        2. For each result:
           - If HEALTHY: reset failure_count
           - If UNHEALTHY: increment failure_count
           - If failure_count >= threshold: call _handle_unhealthy_component()
        3. Update metrics
        """
        pass
    
    async def _handle_unhealthy_component(self, component: str, details: Dict):
        """
        Handle unhealthy component.
        
        MUST:
        1. Check restart cooldown
        2. Check max restart attempts
        3. If OK: call _recover_component()
        4. If max attempts exceeded: escalate (log CRITICAL)
        """
        pass
    
    async def _recover_component(self, component: str):
        """
        Attempt recovery.
        
        MUST:
        1. Execute recovery callback
        2. Update restart_counts and last_restart
        3. Log recovery attempt
        4. Update metrics
        """
        pass
```

---

### 4. Operator Gate (src/core/operator_gate.py)

**Dual control system:**

```python
class OperationType(str, Enum):
    CONFIG_CHANGE = "config_change"
    FORCE_HALT = "force_halt"
    MANUAL_TRADE = "manual_trade"
    PARAMETER_OVERRIDE = "parameter_override"
    KILL_SWITCH = "kill_switch"


@dataclass
class ApprovalRequest:
    request_id: str
    operation_type: OperationType
    description: str
    requestor: str
    timestamp: datetime
    metadata: dict
    approvals: Set[str]
    required_approvals: int = 2
    expires_at: datetime = None


class OperatorGate:
    """
    Dual control for critical operations.
    """
    
    def __init__(self, db: PostgreSQLManager):
        self.db = db
        self.pending_requests: dict[str, ApprovalRequest] = {}
    
    async def request_approval(
        self,
        operation_type: OperationType,
        description: str,
        requestor: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Request approval.
        
        MUST:
        1. Generate unique request_id (secrets.token_urlsafe)
        2. Create ApprovalRequest
        3. Store in pending_requests
        4. Persist to database
        5. Log request
        6. Return request_id
        """
        pass
    
    async def approve(self, request_id: str, approver: str) -> bool:
        """
        Approve request.
        
        MUST:
        1. Check request exists
        2. Check not expired
        3. Check approver != requestor (no self-approval)
        4. Check approver not already approved (no duplicate)
        5. Add approval
        6. Persist approval
        7. If approvals >= required: return True
        8. Else: return False
        """
        pass
    
    async def init_schema(self):
        """
        Create tables.
        
        TABLES:
        - approval_requests
        - approvals
        """
        pass
```

**Database Schema:**
```sql
CREATE TABLE IF NOT EXISTS approval_requests (
    request_id VARCHAR(50) PRIMARY KEY,
    operation_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    requestor VARCHAR(100) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    metadata JSONB,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS approvals (
    id BIGSERIAL PRIMARY KEY,
    request_id VARCHAR(50) NOT NULL REFERENCES approval_requests(request_id),
    approver VARCHAR(100) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_approvals_request ON approvals(request_id);
```

---

## ТЕСТЫ

### Unit Tests

**tests/unit/test_state_machine.py:**
```python
@pytest.mark.asyncio
async def test_initial_state(state_machine):
    assert state_machine.get_state() == SystemState.BOOT


@pytest.mark.asyncio
async def test_valid_transition(state_machine):
    result = await state_machine.transition(SystemState.INIT, trigger="test")
    assert result is True
    assert state_machine.get_state() == SystemState.INIT


@pytest.mark.asyncio
async def test_invalid_transition(state_machine):
    with pytest.raises(ValueError):
        await state_machine.transition(SystemState.TRADING, trigger="test")


@pytest.mark.asyncio
async def test_force_halt(state_machine):
    await state_machine.transition(SystemState.INIT, trigger="test")
    await state_machine.force_halt("emergency")
    assert state_machine.get_state() == SystemState.HALT


@pytest.mark.asyncio
async def test_callbacks(state_machine):
    called = []
    
    async def on_enter(from_state, to_state):
        called.append(("enter", to_state))
    
    state_machine.register_on_enter(SystemState.INIT, on_enter)
    await state_machine.transition(SystemState.INIT, trigger="test")
    
    assert ("enter", SystemState.INIT) in called
```

**tests/unit/test_operator_gate.py:**
```python
@pytest.mark.asyncio
async def test_request_approval(operator_gate):
    request_id = await operator_gate.request_approval(
        OperationType.CONFIG_CHANGE,
        "Test change",
        "operator1",
    )
    
    assert request_id in operator_gate.pending_requests


@pytest.mark.asyncio
async def test_dual_approval(operator_gate):
    request_id = await operator_gate.request_approval(
        OperationType.FORCE_HALT,
        "Emergency halt",
        "operator1",
    )
    
    # First approval
    result1 = await operator_gate.approve(request_id, "operator2")
    assert result1 is False  # Not enough approvals yet
    
    # Second approval
    result2 = await operator_gate.approve(request_id, "operator3")
    assert result2 is True  # Approved!


@pytest.mark.asyncio
async def test_self_approval_blocked(operator_gate):
    request_id = await operator_gate.request_approval(
        OperationType.MANUAL_TRADE,
        "Manual trade",
        "operator1",
    )
    
    result = await operator_gate.approve(request_id, "operator1")
    assert result is False  # Self-approval blocked
```

---

### Integration Test

**tests/integration/test_control_plane.py:**
```python
@pytest.mark.asyncio
async def test_full_boot_sequence():
    """Test BOOT → INIT → READY → TRADING."""
    
    db = PostgreSQLManager("postgresql://bot_user:bot_password_dev@localhost:5432/trading_dev")
    redis = RedisManager("redis://localhost:6379/0")
    state_machine = StateMachine(db)
    
    controller = SystemController(db, redis, state_machine)
    
    # Boot
    await controller.boot()
    assert state_machine.get_state() == SystemState.INIT
    
    # Initialize
    await controller.initialize()
    assert state_machine.get_state() == SystemState.READY
    
    # Start trading
    await controller.start_trading()
    assert state_machine.get_state() == SystemState.TRADING
    
    # Cleanup
    await controller.shutdown()
    assert state_machine.get_state() == SystemState.HALT
```

---

## ACCEPTANCE CRITERIA

### State Machine
- [x] 9 states defined
- [x] ALLOWED_TRANSITIONS complete
- [x] transition() validates transitions
- [x] Invalid transitions raise ValueError
- [x] on_enter/on_exit callbacks work
- [x] force_halt() works from any state
- [x] Transitions persist to database
- [x] can_trade() returns correct value
- [x] is_operational() returns correct value

### System Controller
- [x] boot() connects infrastructure
- [x] initialize() starts components
- [x] start_trading() transitions to TRADING
- [x] degrade() transitions to DEGRADED
- [x] survival_mode() transitions to SURVIVAL
- [x] halt() stops system
- [x] shutdown() gracefully disconnects

### Watchdog
- [x] Monitoring loop starts/stops
- [x] Health checks run periodically
- [x] Failure counts tracked
- [x] Auto-recovery attempted
- [x] Restart cooldown enforced
- [x] Max restart attempts enforced
- [x] Metrics updated

### Operator Gate
- [x] request_approval() creates request
- [x] approve() adds approval
- [x] Dual control enforced (2 approvals)
- [x] Self-approval blocked
- [x] Duplicate approval blocked
- [x] Expiration checked
- [x] Requests/approvals persist

### Tests
- [x] Unit tests coverage >= 95%
- [x] Integration test passes
- [x] All edge cases tested

---

## СТИЛЬ КОДА

```python
# CRYPTOTEHNOLOG v1.2.0
# Phase 2: Control Plane
# Component: State Machine
# File: state_machine.py

"""
State Machine - Deterministic system lifecycle management
"""

from typing import Optional, Dict, Set, Callable
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import asyncio

from src.core.logger import get_logger

logger = get_logger("StateMachine")


class SystemState(str, Enum):
    """System states with clear semantics."""
    BOOT = "boot"
    # ... остальные


# Type hints везде
async def transition(
    self,
    to_state: SystemState,
    trigger: str,
    metadata: Optional[Dict] = None,
    operator: Optional[str] = None,
) -> bool:
    """
    Transition to new state.
    
    Args:
        to_state: Target state
        trigger: What triggered transition
        metadata: Additional context
        operator: Operator who initiated
        
    Returns:
        True if successful
        
    Raises:
        ValueError: If transition invalid
    """
    pass
```

---

## 📤 ФОРМАТ ВЫДАЧИ

Для каждого файла:
1. Напишите полный путь
2. Покажите ВЕСЬ код
3. Добавьте header комментарий
4. После кода: "✅ filename READY"

В конце:
```
📦 GENERATED FILES:
- src/core/state_machine.py ✅
- src/core/system_controller.py ✅
- src/core/watchdog.py ✅
- src/core/operator_gate.py ✅
- tests/unit/test_state_machine.py ✅
- tests/unit/test_system_controller.py ✅
- tests/unit/test_watchdog.py ✅
- tests/unit/test_operator_gate.py ✅
- tests/integration/test_control_plane.py ✅

🧪 NEXT STEPS:
1. pytest tests/unit/test_state_machine.py -v
2. pytest tests/unit/ -v
3. pytest tests/integration/test_control_plane.py -v
4. pytest --cov=src/core --cov-report=term
5. git commit -m "Phase 2 completed"
```

---

## ✅ КАК ПРОВЕРИТЬ РЕЗУЛЬТАТ

### 1. Unit Tests - State Machine
```bash
pytest tests/unit/test_state_machine.py -v
```
**Ожидаемо:**
```
test_initial_state PASSED
test_valid_transition PASSED
test_invalid_transition PASSED
test_force_halt PASSED
test_callbacks PASSED
======================== 5 passed ========================
```

### 2. Unit Tests - Operator Gate
```bash
pytest tests/unit/test_operator_gate.py -v
```
**Ожидаемо:**
```
test_request_approval PASSED
test_dual_approval PASSED
test_self_approval_blocked PASSED
======================== 3 passed ========================
```

### 3. Integration Test
```bash
pytest tests/integration/test_control_plane.py -v
```
**Ожидаемо:**
```
test_full_boot_sequence PASSED
======================== 1 passed ========================
```

### 4. Coverage
```bash
pytest --cov=src/core --cov-report=term-missing
```
**Ожидаемо:**
```
src/core/state_machine.py       95%
src/core/system_controller.py   92%
src/core/watchdog.py            94%
src/core/operator_gate.py       96%
```

### 5. Type Checking
```bash
mypy src/core/state_machine.py --strict
```
**Ожидаемо:** `Success: no issues found`

---

## ВАЖНО

1. **НЕ используйте TODO или NOT IMPLEMENTED**
2. **Error handling везде** (try/except)
3. **Logging везде** (каждая операция)
4. **Type hints везде** (mypy --strict)
5. **Callbacks должны поддерживать async**
6. **Database operations всегда в try/except**
7. **State transitions всегда логируются**

---

**Успехов в реализации Control Plane!** 🚀

---

## 🆕 ДОПОЛНЕНИЯ v4.4 (STATE MACHINE FULL ARCHITECTURE)

### STATE MACHINE v4.4 — Полная архитектура из плана

**Проблема в текущей версии:**
Текущий State Machine имеет 9 состояний (BOOT, INIT, READY, TRADING, DEGRADED,
SURVIVAL, ERROR, HALT, RECOVERY), но из плана v4.4 следует более точная архитектура
с 8 состояниями и чёткими STATE_POLICIES для каждого.

**Обновлённая архитектура v4.4:**

#### 1. Новые состояния и их семантика

**Файл:** `src/core/state_machine.py` ★ ОБНОВЛЁН

```python
class SystemState(str, Enum):
    """
    Состояния системы v4.4 (из плана).
    
    8 состояний с чёткой семантикой и политиками.
    """
    BOOT = "BOOT"                    # Инициализация, проверка инфраструктуры
    RECOVERY = "RECOVERY"            # Восстановление после HALT
    DISCOVERY = "DISCOVERY"          # Сбор market data, построение вселенной
    ADMISSIBLE = "ADMISSIBLE"        # Вселенная готова, ожидание risk clearance
    TRADING = "TRADING"              # Полная функциональность
    RISK_REDUCTION = "RISK_REDUCTION"  # Активное снижение риска, no new positions
    DEGRADED = "DEGRADED"            # Ограниченная функциональность, reduce-only
    HALT = "HALT"                    # Полная остановка


class StateMachine:
    """
    State Machine v4.4 с детерминированными переходами и политиками.
    """
    
    # Полная таблица переходов из плана v4.4
    STATE_TRANSITIONS = {
        # Начальные состояния
        ("BOOT", "INIT_OK"): "DISCOVERY",
        ("BOOT", "INIT_FAILED"): "HALT",
        
        # Recovery path (явный, через operator approval)
        ("HALT", "RECOVERY_REQUESTED"): "RECOVERY",
        ("RECOVERY", "CHECKS_PASSED"): "DISCOVERY",
        ("RECOVERY", "CHECKS_FAILED"): "HALT",
        
        # Normal operation
        ("DISCOVERY", "UNIVERSE_READY"): "ADMISSIBLE",
        ("DISCOVERY", "UNIVERSE_EMPTY"): "DEGRADED",
        
        ("ADMISSIBLE", "RISK_CLEAR"): "TRADING",
        ("ADMISSIBLE", "RISK_BLOCKED"): "DEGRADED",
        
        # Degradation paths
        ("TRADING", "FAST_VELOCITY_ALERT"): "DEGRADED",
        ("TRADING", "RISK_BREACH"): "RISK_REDUCTION",
        ("TRADING", "CRITICAL_ERROR"): "HALT",
        ("TRADING", "LOW_UNIVERSE_QUALITY"): "DEGRADED",  # ★ НОВОЕ (Фаза 6)
        
        ("DEGRADED", "STABLE_RECOVERED"): "TRADING",      # ★ НОВОЕ (Фаза 9)
        ("DEGRADED", "SLOW_VELOCITY_ALERT"): "RISK_REDUCTION",
        ("DEGRADED", "DEGRADATION_SEVERE"): "HALT",
        
        # Risk reduction paths
        ("RISK_REDUCTION", "RISK_NORMALIZED"): "TRADING",
        ("RISK_REDUCTION", "RISK_PERSISTENT"): "HALT",
        
        # HALT terminal (требует explicit recovery)
        ("HALT", "MANUAL_RECOVERY"): "RECOVERY",
    }
    
    # Максимальное время в каждом состоянии (секунды)
    MAX_STATE_TIMES = {
        "BOOT": 30,
        "RECOVERY": 300,       # 5 минут на проверки
        "DISCOVERY": 300,      # 5 минут на построение вселенной
        "ADMISSIBLE": 60,
        "TRADING": float('inf'),
        "RISK_REDUCTION": 300, # 5 минут на снижение риска
        "DEGRADED": 3600,      # 1 час максимум в degraded
        "HALT": float('inf'),
    }
    
    # ★ НОВОЕ v4.4: STATE_POLICIES — политики поведения
    STATE_POLICIES = {
        "BOOT": {
            "allow_new_positions": False,
            "allow_reduce": False,
            "allow_data_collection": True,
            "allow_strategy_signals": False,
            "risk_multiplier": 0.0,
        },
        "RECOVERY": {
            "allow_new_positions": False,
            "allow_reduce": False,
            "allow_data_collection": True,
            "allow_strategy_signals": False,
            "risk_multiplier": 0.0,
            "requires_operator_approval": True,
        },
        "DISCOVERY": {
            "allow_new_positions": False,
            "allow_reduce": True,
            "allow_data_collection": True,
            "allow_strategy_signals": False,
            "risk_multiplier": 0.0,
        },
        "ADMISSIBLE": {
            "allow_new_positions": False,
            "allow_reduce": True,
            "allow_data_collection": True,
            "allow_strategy_signals": True,  # Сигналы разрешены, но не исполнение
            "risk_multiplier": 0.0,
        },
        "TRADING": {
            "allow_new_positions": True,
            "allow_reduce": True,
            "allow_data_collection": True,
            "allow_strategy_signals": True,
            "risk_multiplier": 1.0,
        },
        "RISK_REDUCTION": {
            "allow_new_positions": False,
            "allow_reduce": True,
            "allow_data_collection": True,
            "allow_strategy_signals": False,
            "risk_multiplier": 0.5,
            "target_reduction": 0.5,  # Цель: снизить риск на 50%
        },
        "DEGRADED": {
            "allow_new_positions": False,
            "allow_reduce": True,
            "allow_data_collection": True,
            "allow_strategy_signals": True,  # Для мониторинга
            "risk_multiplier": 0.25,
            "max_positions": 3,
        },
        "HALT": {
            "allow_new_positions": False,
            "allow_reduce": True,  # Только закрытие позиций
            "allow_data_collection": False,
            "allow_strategy_signals": False,
            "risk_multiplier": 0.0,
        },
    }
```

---

#### 2. Новые методы для policy checking

```python
class StateMachine:
    def can_open_positions(self) -> bool:
        """
        Проверить разрешено ли открытие новых позиций.
        
        Используется Strategy Manager перед каждым сигналом.
        """
        policy = self.STATE_POLICIES.get(self.current_state)
        if not policy:
            return False
        return policy.get("allow_new_positions", False)
    
    def can_reduce_positions(self) -> bool:
        """Разрешено ли закрытие позиций."""
        policy = self.STATE_POLICIES.get(self.current_state)
        if not policy:
            return False
        return policy.get("allow_reduce", False)
    
    def get_risk_multiplier(self) -> float:
        """
        Получить risk multiplier для текущего состояния.
        
        Используется Risk Engine для scaling risk budget:
        - TRADING: 1.0 (100% риска)
        - RISK_REDUCTION: 0.5 (50% риска)
        - DEGRADED: 0.25 (25% риска)
        - Остальные: 0.0 (риск отключён)
        """
        policy = self.STATE_POLICIES.get(self.current_state)
        if not policy:
            return 0.0
        return policy.get("risk_multiplier", 0.0)
    
    def get_max_positions(self) -> Optional[int]:
        """
        Получить максимальное количество позиций для текущего состояния.
        
        Возвращает:
            int: максимум позиций (например, 3 для DEGRADED)
            None: без ограничений
        """
        policy = self.STATE_POLICIES.get(self.current_state)
        if not policy:
            return 0
        return policy.get("max_positions", None)
    
    def requires_operator_approval(self) -> bool:
        """Требуется ли operator approval для текущего состояния."""
        policy = self.STATE_POLICIES.get(self.current_state)
        if not policy:
            return False
        return policy.get("requires_operator_approval", False)
```

---

#### 3. Timeout monitoring для состояний

```python
class StateMachine:
    def __init__(self, ...):
        # Existing...
        
        # ★ НОВОЕ: Tracking времени в состоянии
        self.state_entered_at: Dict[str, datetime] = {}
        
        # Запустить timeout monitor
        asyncio.create_task(self._monitor_state_timeouts())
    
    async def transition(self, trigger: str, metadata: Optional[dict] = None):
        """
        Выполнить переход с записью времени входа.
        """
        # Existing transition logic...
        
        # ★ НОВОЕ: Записать время входа в состояние
        self.state_entered_at[self.current_state] = datetime.utcnow()
        
        # Проверить timeout предыдущего состояния
        await self._check_state_timeout(old_state)
    
    async def _monitor_state_timeouts(self):
        """
        Мониторить timeouts состояний (background task).
        
        Если состояние превышает MAX_STATE_TIMES → автоматический переход или alert.
        """
        while True:
            await asyncio.sleep(30)  # Проверка каждые 30 секунд
            
            if self.current_state not in self.state_entered_at:
                continue
            
            entered_at = self.state_entered_at[self.current_state]
            elapsed = (datetime.utcnow() - entered_at).total_seconds()
            max_time = self.MAX_STATE_TIMES.get(self.current_state, float('inf'))
            
            if elapsed > max_time:
                logger.critical(
                    "Состояние превысило максимальное время",
                    state=self.current_state,
                    elapsed_seconds=elapsed,
                    max_seconds=max_time,
                    action="auto_transition_or_alert",
                )
                
                # Специфичная логика по состоянию
                if self.current_state == "DEGRADED":
                    # DEGRADED > 1 час → HALT
                    await self.transition("DEGRADATION_SEVERE", {
                        "reason": "max_time_exceeded",
                        "elapsed": elapsed,
                    })
                elif self.current_state == "RISK_REDUCTION":
                    # RISK_REDUCTION > 5 минут → HALT
                    await self.transition("RISK_PERSISTENT", {
                        "reason": "risk_reduction_timeout",
                    })
                elif self.current_state == "DISCOVERY":
                    # DISCOVERY > 5 минут → DEGRADED
                    await self.transition("UNIVERSE_EMPTY", {
                        "reason": "discovery_timeout",
                    })
```

---

#### 4. Integration с новыми triggers

**Новые triggers из обновлённых фаз:**

**a) UniverseEngine (Фаза 6):**
```python
# LOW_UNIVERSE_QUALITY trigger
if confidence < 0.6:
    await state_machine.transition("LOW_UNIVERSE_QUALITY", {
        "confidence": confidence,
        "threshold": 0.6,
    })
# TRADING → DEGRADED
```

**b) VelocityMonitor (Фаза 9):**
```python
# STABLE_RECOVERED trigger
if is_stable and state == "DEGRADED":
    await state_machine.transition("STABLE_RECOVERED", {
        "readings": stable_readings,
    })
# DEGRADED → TRADING
```

**c) Risk Engine (Фаза 5):**
```python
# RISK_BREACH trigger (вместо старого RISK_VIOLATION)
if violation_severity == "CRITICAL":
    await state_machine.transition("RISK_BREACH", {
        "violation_type": "drawdown_exceeded",
    })
# TRADING → RISK_REDUCTION
```

---

#### 5. Database schema обновления

```sql
-- State transitions (обновлённая таблица)
CREATE TABLE state_transitions (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    from_state VARCHAR(20) NOT NULL,
    to_state VARCHAR(20) NOT NULL,
    trigger VARCHAR(50) NOT NULL,  -- ★ НОВЫЕ triggers
    
    metadata JSONB,
    operator VARCHAR(100),
    
    duration_ms INTEGER,
    
    -- ★ НОВЫЕ поля v4.4
    time_in_previous_state_seconds INTEGER,
    exceeded_max_time BOOLEAN DEFAULT FALSE
);

-- Index для audit
CREATE INDEX idx_state_trans_time ON state_transitions(timestamp DESC);
CREATE INDEX idx_state_trans_trigger ON state_transitions(trigger);
```

---

## ACCEPTANCE CRITERIA v4.4

### State Machine v4.4 ★ ОБНОВЛЕНО
- [x] 10 состояний (BOOT, INIT, READY, TRADING, RISK_REDUCTION, DEGRADED, SURVIVAL, ERROR, HALT, RECOVERY)
- [x] ALLOWED_TRANSITIONS с 28 переходами
- [x] MAX_STATE_TIMES для каждого состояния
- [x] STATE_POLICIES с allow_new_positions, risk_multiplier, etc.
- [x] can_open_positions(), get_risk_multiplier(), get_max_positions()
- [x] _monitor_state_timeouts() метод реализован
- [ ] Автоматические transitions при timeout **(НЕ РАБОТАЕТ - мониторинг не запускается в initialize())**

### New Triggers Integration ★ НОВОЕ
- [x] TriggerType enum содержит: LOW_UNIVERSE_QUALITY, STABLE_RECOVERED, RISK_BREACH, FAST_VELOCITY_ALERT, SLOW_VELOCITY_ALERT
- [ ] Интеграция триггеров в логику переходов **(НЕ РЕАЛИЗОВАНО)**

### Existing (как было)
- [x] Operator Gate dual control
- [x] Watchdog auto-recovery
- [x] System Controller lifecycle
- [x] Audit trail в PostgreSQL

---

**Version:** CRYPTOTEHNOLOG v4.4 (Фаза 2 — полная редакция)
**Dependencies:** Phase 1 (SLO monitoring)
**Next:** Phase 3 - Event Bus (Rust) с persistence

---

## ⚠️ TODO: SLO Integration (добавить при реализации компонентов)

При реализации следующих компонентов **ОБЯЗАТЕЛЬНО** добавить `record_latency()`:

1. **Execution Layer (Фаза 10)** → добавить в listeners/execution.py:
   ```python
   await metrics.record_latency("execution_response_seconds", duration)
   ```

2. **UniverseEngine (Фаза 7)** → добавить в listeners/universe.py:
   ```python
   await metrics.record_latency("universe_update_seconds", duration)
   ```

3. **Market Data (Фаза 6)** → добавить в listeners/market_data.py:
   ```python
   await metrics.record_latency("market_data_freshness_seconds", duration)
   ```

---

## 📝 СДЕЛАНО ДОПОЛНИТЕЛЬНО (не было в чек-листе)

- Event Bus с publish/subscribe паттерном
- Event Bus listeners (audit, metrics, risk, state_machine)
- SQL миграции (10 файлов в scripts/migrations/)
- Graceful Shutdown с drain() и checkpoint()
- State Machine checkpoint/restore в Redis/PostgreSQL
- Property-based тесты для инвариантов State Machine
- Интеграционные тесты Control Plane
- Rust bridge с graceful degradation
- Circuit Breaker паттерн
- System Controller event_bus интеграция для shutdown notification
- Исправлены антипаттерны (generator.send(), event loop creation)
- Ruff форматирование
- MyPy проверка типов

### Database Integration (Control Plane)
- Event Subscriptions система (таблица event_subscriptions)
- Dead Letter Events обработка (таблица dead_letter_events)
- Maintenance Tasks планировщик (таблица maintenance_tasks)
- Alert Rules engine (таблица alert_rules)
- Component Heartbeats мониторинг (таблица component_heartbeats)
- API Request Logs (таблица api_request_logs)
- Published Events логирование (таблица published_events)
- Event Consumers registry (таблица event_consumers)

### Event Bus Listeners
- StateMachineListener - слушает события State Machine
- AuditListener - записывает аудит события
- MetricsListener - собирает метрики
- RiskListener - мониторинг рисков
