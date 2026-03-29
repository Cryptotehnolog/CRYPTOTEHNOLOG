# AI ПРОМТ: ФАЗА 12 - KILL SWITCH & EMERGENCY CONTROLS

## КОНТЕКСТ

Вы — Senior Trading Risk Officer, специализирующийся на risk controls, emergency procedures, и trading system safety.

**Фазы 0-11 завершены.** Доступны:
- Event Bus (Rust + Python) — работает с persistence
- Control Plane (State Machine, Watchdog) — работает
- Config Manager — hot reload, GPG signatures, Vault
- Risk Engine — R-unit sizing, correlation, drawdown
- Market Data Layer — WebSocket, ticks, OHLCV bars
- Technical Indicators — 20+ индикаторов
- Signal Generator — торговые стратегии
- Portfolio Governor — position tracking, P&L
- Execution Layer — multi-exchange execution
- Order Management System — order lifecycle
- Database Layer, Logging, Metrics — готовы

**Текущая задача:** Реализовать production-ready Kill Switch & Emergency Controls с automatic circuit breakers, manual emergency stop, position liquidation, и comprehensive safety mechanisms.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class KillSwitch:
    """
    Система аварийного управления с автоматическими и ручными защитами.
    
    Особенности:
    - Automatic circuit breakers (drawdown, loss rate, error rate)
    - Manual emergency stop (operator-triggered)
    - Immediate position liquidation (close all positions)
    - Order cancellation (cancel all pending orders)
    - System freeze (stop new trades, keep monitoring)
    - Multi-level triggers (warning, critical, emergency)
    - Dual control для critical actions (require 2 operators)
    - Automatic recovery (after conditions normalize)
    """
    
    async def trigger_kill_switch(
        self,
        reason: str,
        severity: EmergencySeverity,
        triggered_by: str,
    ):
        """
        Активировать kill switch.
        
        Аргументы:
            reason: Причина активации
            severity: Уровень серьезности (WARNING, CRITICAL, EMERGENCY)
            triggered_by: Кто/что активировало (auto_drawdown, operator_john)
        
        Действия по severity:
        
        WARNING:
        - Pause new positions
        - Alert operators
        - Continue monitoring
        
        CRITICAL:
        - Cancel all pending orders
        - Close losing positions
        - Pause trading
        
        EMERGENCY:
        - Cancel ALL orders
        - Close ALL positions (market orders)
        - Freeze system
        - Alert PagerDuty
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.critical("🔴 KILL SWITCH АКТИВИРОВАН", reason="drawdown_exceeded", severity="EMERGENCY")
logger.warning("⚠️  Circuit breaker сработал", trigger="loss_rate_5min", threshold=0.05)
logger.info("✅ Все позиции закрыты", closed_count=15, total_value_usd=125000)
logger.error("❌ Не удалось закрыть позицию", position_id="pos_123", error="exchange_timeout")
```

### Примеры замены:

| ❌ Неправильно | ✅ Правильно |
|----------------|--------------|
| "Kill switch activated" | "Kill switch активирован" |
| "Circuit breaker triggered" | "Circuit breaker сработал" |
| "All positions closed" | "Все позиции закрыты" |
| "Emergency mode" | "Аварийный режим" |
| "System frozen" | "Система заморожена" |

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Kill Switch — последняя линия защиты торговой системы. Автоматически мониторит критические параметры (drawdown, loss rate, error rate). При превышении порогов немедленно останавливает торговлю, закрывает позиции, отменяет ордера. Предоставляет manual emergency stop для операторов. Prevents catastrophic losses через multi-level circuit breakers.

### Входящие зависимости (кто может trigger kill switch):

#### 1. **Risk Engine (Фаза 5)** → automatic triggers
   - Trigger: Drawdown exceeded
     - Частота: continuous monitoring
     - Условие: `current_drawdown > max_drawdown_hard`
     - Severity: EMERGENCY
     - Критичность: CRITICAL (защита капитала)

#### 2. **Portfolio Governor (Фаза 9)** → loss rate triggers
   - Trigger: High loss rate
     - Частота: каждую минуту
     - Условие: `losses_last_5min > 5%` of equity
     - Severity: CRITICAL
     - Критичность: HIGH

#### 3. **Execution Layer (Фаза 10)** → error rate triggers
   - Trigger: High execution error rate
     - Частота: каждую минуту
     - Условие: `errors_last_1min > 50%` of attempts
     - Severity: CRITICAL (system malfunction)
     - Критичность: HIGH

#### 4. **Market Data Layer (Фаза 6)** → data quality triggers
   - Trigger: Market data failure
     - Частота: continuous
     - Условие: No ticks for 60 seconds
     - Severity: WARNING → CRITICAL
     - Критичность: HIGH (blind trading dangerous)

#### 5. **Operator Gate (Фаза 2)** → manual triggers
   - Trigger: Manual emergency stop
     - Частота: очень редко (operator decision)
     - Условие: Operator command (с dual control для EMERGENCY)
     - Severity: по выбору оператора
     - Критичность: CRITICAL

#### 6. **State Machine (Фаза 2)** → system health triggers
   - Trigger: Repeated crashes
     - Частота: при каждом restart
     - Условие: >3 crashes за 5 минут
     - Severity: EMERGENCY
     - Критичность: CRITICAL

### Исходящие зависимости (что делает Kill Switch):

#### 1. → State Machine (Фаза 2)
   - Command: `transition_to(SystemState.SURVIVAL)`
     - Действие: Переключить в аварийный режим
     - Частота: при trigger
     - Критичность: CRITICAL

#### 2. → Order Management System (Фаза 11)
   - Command: `cancel_all_orders(reason="kill_switch")`
     - Действие: Отменить все pending orders
     - Частота: при CRITICAL/EMERGENCY
     - Критичность: CRITICAL

#### 3. → Portfolio Governor (Фаза 9)
   - Command: `close_all_positions(urgency="immediate")`
     - Действие: Закрыть все открытые позиции
     - Order type: MARKET (для speed)
     - Частота: при EMERGENCY
     - Критичность: CRITICAL

#### 4. → Execution Layer (Фаза 10)
   - Command: `stop_accepting_new_orders()`
     - Действие: Pause execution engine
     - Частота: при WARNING/CRITICAL
     - Критичность: HIGH

#### 5. → Event Bus (Фаза 3)
   - **Event: `KILL_SWITCH_TRIGGERED`** (приоритет: CRITICAL)
     - Payload:
       ```json
       {
         "trigger_id": "ks_uuid",
         "reason": "drawdown_exceeded",
         "severity": "EMERGENCY",
         "triggered_by": "auto_drawdown",
         "triggered_at": 1704067200000000,
         "current_state": {
           "drawdown_percent": 25,
           "open_positions": 10,
           "pending_orders": 5
         },
         "actions_taken": [
           "cancel_all_orders",
           "close_all_positions",
           "freeze_system"
         ]
       }
       ```
     - Подписчики: ALL components (для awareness)

   - **Event: `EMERGENCY_POSITIONS_CLOSED`** (приоритет: CRITICAL)
     - Payload: `{"closed_count": 10, "total_value_usd": 125000, "duration_ms": 5000}`

   - **Event: `KILL_SWITCH_RECOVERY_STARTED`** (приоритет: HIGH)
     - Payload: `{"recovery_id": "...", "conditions_met": true, "approval_required": true}`

#### 6. → Alerting (PagerDuty, Telegram)
   - Alert: CRITICAL incident
     - Channel: PagerDuty (immediate)
     - Channel: Telegram (операторы)
     - Channel: Email (management)
     - Частота: немедленно при trigger

#### 7. → PostgreSQL (audit trail)
   - **Table: `kill_switch_events`**
     ```sql
     CREATE TABLE kill_switch_events (
         event_id SERIAL PRIMARY KEY,
         triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
         
         reason TEXT NOT NULL,
         severity VARCHAR(20) NOT NULL,
         triggered_by VARCHAR(100) NOT NULL,
         
         system_state_before JSONB,
         system_state_after JSONB,
         
         actions_taken JSONB,
         
         positions_closed INTEGER,
         orders_cancelled INTEGER,
         
         recovery_started_at TIMESTAMPTZ,
         recovery_completed_at TIMESTAMPTZ,
         recovery_approved_by VARCHAR(100)
     );
     
     CREATE INDEX idx_kill_switch_triggered ON kill_switch_events(triggered_at DESC);
     ```

### Контракты данных:

#### EmergencySeverity:

```python
from enum import Enum

class EmergencySeverity(str, Enum):
    """Уровни серьезности emergency."""
    
    WARNING = "WARNING"       # Pause new trades, alert
    CRITICAL = "CRITICAL"     # Cancel orders, close losing positions
    EMERGENCY = "EMERGENCY"   # Close ALL, freeze system
```

#### CircuitBreaker:

```python
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, Callable

@dataclass
class CircuitBreakerConfig:
    """Конфигурация circuit breaker."""
    
    name: str
    description: str
    
    # Trigger conditions
    check_function: Callable[[], bool]  # Функция проверки
    threshold: Decimal
    
    # Timing
    check_interval: timedelta  # Как часто проверять
    cooldown_period: timedelta  # Как долго ждать после trigger
    
    # Actions
    severity: EmergencySeverity
    auto_recover: bool  # Автоматическое восстановление?

@dataclass
class CircuitBreakerState:
    """Состояние circuit breaker."""
    
    config: CircuitBreakerConfig
    
    is_triggered: bool = False
    triggered_at: Optional[datetime] = None
    trigger_count: int = 0
    
    last_check: Optional[datetime] = None
    last_value: Optional[Decimal] = None
    
    def can_check(self) -> bool:
        """Можно ли проверить сейчас?"""
        if self.last_check is None:
            return True
        
        elapsed = datetime.now(timezone.utc) - self.last_check
        return elapsed >= self.config.check_interval
    
    def can_recover(self) -> bool:
        """Можно ли восстановиться?"""
        if not self.is_triggered:
            return False
        
        if not self.config.auto_recover:
            return False
        
        elapsed = datetime.now(timezone.utc) - self.triggered_at
        return elapsed >= self.config.cooldown_period
    
    async def check(self) -> bool:
        """
        Проверить условие trigger.
        
        Возвращает True если сработал.
        """
        if not self.can_check():
            return False
        
        self.last_check = datetime.now(timezone.utc)
        
        # Выполнить проверку
        triggered = await self.config.check_function()
        
        if triggered and not self.is_triggered:
            # Новый trigger
            self.is_triggered = True
            self.triggered_at = datetime.now(timezone.utc)
            self.trigger_count += 1
            return True
        
        return False
```

#### KillSwitchAction:

```python
@dataclass
class KillSwitchAction:
    """Действие kill switch."""
    
    action_type: str  # "cancel_orders", "close_positions", "freeze_system"
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    success: bool = False
    error_message: Optional[str] = None
    
    # Results
    orders_cancelled: int = 0
    positions_closed: int = 0
    
    metadata: Dict[str, Any] = None
```

### Sequence Diagram (Kill Switch Trigger Flow):

```
[Risk Engine] ──drawdown exceeded──> [Kill Switch]
                                            |
                            [Evaluate Severity]
                            drawdown = 25% > 20% → EMERGENCY
                                            |
                            ┌───────────────┼───────────────┐
                            v               v               v
                    [State Machine]  [Cancel Orders]  [Close Positions]
                    → SURVIVAL       all pending      ALL positions
                                            |               |
                                            v               v
                                    [OMS]           [Portfolio Governor]
                                    cancel_all()    close_all(market)
                                            |               |
                            ┌───────────────┴───────────────┘
                            v
                [Record KillSwitchEvent]
                audit trail в PostgreSQL
                            |
                ┌───────────┼───────────┐
                v           v           v
        [PagerDuty]  [Telegram]  [Event Bus]
        CRITICAL     operators   KILL_SWITCH_TRIGGERED
        incident     notification
                            |
                            v
                [Wait for Recovery Conditions]
                drawdown < 15% для 1 hour
                            |
                ┌───────────┴───────────┐
                v                       v
        [Auto Recovery]         [Manual Recovery]
        если auto_recover       require operator approval
                            
[Operator] ──approve recovery──> [Kill Switch]
                                        |
                            [Transition to OPERATIONAL]
                            [Resume Trading]
```

### Обработка ошибок интеграции:

#### 1. Failed position closure:

```python
class KillSwitch:
    async def _close_all_positions(self) -> KillSwitchAction:
        """
        Закрыть все позиции с error handling.
        """
        action = KillSwitchAction(
            action_type="close_positions",
            started_at=datetime.now(timezone.utc),
        )
        
        # Получить все открытые позиции
        positions = await self.portfolio.get_open_positions()
        
        logger.critical(
            "🔴 Закрытие всех позиций",
            count=len(positions),
            total_value_usd=sum(p.size_usd for p in positions),
        )
        
        # Close параллельно для speed
        close_tasks = [
            self._close_position_emergency(pos)
            for pos in positions
        ]
        
        results = await asyncio.gather(*close_tasks, return_exceptions=True)
        
        # Count successes and failures
        successes = 0
        failures = []
        
        for pos, result in zip(positions, results):
            if isinstance(result, Exception):
                logger.error(
                    "❌ Не удалось закрыть позицию",
                    position_id=pos.position_id,
                    error=str(result),
                )
                failures.append({
                    "position_id": pos.position_id,
                    "error": str(result),
                })
            else:
                successes += 1
        
        action.completed_at = datetime.now(timezone.utc)
        action.success = len(failures) == 0
        action.positions_closed = successes
        
        if failures:
            action.error_message = f"{len(failures)} positions failed to close"
            action.metadata = {"failures": failures}
            
            # CRITICAL alert
            await self._alert_critical(
                f"Failed to close {len(failures)} positions during emergency shutdown",
                failures=failures,
            )
        else:
            logger.info(
                "✅ Все позиции успешно закрыты",
                count=successes,
                duration_ms=(action.completed_at - action.started_at).total_seconds() * 1000,
            )
        
        return action
    
    async def _close_position_emergency(
        self,
        position: Position,
    ) -> bool:
        """
        Закрыть позицию в emergency режиме.
        
        Используется MARKET order для гарантированного исполнения.
        """
        try:
            # Create market order (гарантированное исполнение)
            order = await self.execution.execute_order(
                signal=None,  # No signal (emergency)
                symbol=position.symbol,
                side="SELL" if position.direction == "LONG" else "BUY",
                quantity=position.quantity,
                order_type=OrderType.MARKET,  # MARKET для speed
                reason="kill_switch_emergency",
            )
            
            # Wait for fill (max 30 секунд)
            filled = await self._wait_for_fill(order.order_id, timeout=30)
            
            if not filled:
                raise TimeoutError(f"Order not filled within 30 seconds")
            
            return True
            
        except Exception as e:
            logger.error(
                "Emergency position close failed",
                position_id=position.position_id,
                error=str(e),
            )
            raise
```

**Error handling для position closure:**
- Parallel closes для speed
- MARKET orders (не LIMIT) для guaranteed fill
- Timeout 30 секунд на fill
- Если failed → CRITICAL alert + manual intervention

#### 2. Dual control для emergency actions:

```python
class KillSwitch:
    async def trigger_kill_switch(
        self,
        reason: str,
        severity: EmergencySeverity,
        triggered_by: str,
    ):
        """Trigger с dual control для EMERGENCY."""
        
        # Для EMERGENCY требуется dual control
        if severity == EmergencySeverity.EMERGENCY:
            # Проверить является ли triggered_by оператором
            if triggered_by.startswith("operator_"):
                # Manual trigger → требуется approval
                
                # Создать pending emergency action
                pending_id = await self._create_pending_emergency(
                    reason=reason,
                    triggered_by=triggered_by,
                )
                
                logger.warning(
                    "⚠️  EMERGENCY trigger требует dual control",
                    pending_id=pending_id,
                    triggered_by=triggered_by,
                    awaiting_approval_from="second_operator",
                )
                
                # Уведомить операторов
                await self._notify_operators_approval_required(
                    pending_id=pending_id,
                    reason=reason,
                )
                
                # НЕ выполнять действия пока нет approval
                return
        
        # WARNING/CRITICAL или auto-trigger → выполнить немедленно
        await self._execute_kill_switch_actions(reason, severity, triggered_by)
    
    async def approve_emergency_action(
        self,
        pending_id: str,
        approved_by: str,
    ):
        """
        Подтвердить emergency action (второй оператор).
        """
        # Получить pending action
        pending = await self._get_pending_emergency(pending_id)
        
        if not pending:
            raise ValueError(f"Pending emergency {pending_id} not found")
        
        # Проверить что approver != trigger
        if approved_by == pending["triggered_by"]:
            raise ValueError("Cannot approve own emergency trigger (dual control)")
        
        logger.critical(
            "🔴 EMERGENCY action одобрен вторым оператором",
            pending_id=pending_id,
            triggered_by=pending["triggered_by"],
            approved_by=approved_by,
        )
        
        # Execute
        await self._execute_kill_switch_actions(
            reason=pending["reason"],
            severity=EmergencySeverity.EMERGENCY,
            triggered_by=f"{pending['triggered_by']}_approved_by_{approved_by}",
        )
```

**Dual control policy:**
- EMERGENCY actions требуют 2 операторов
- Approver != trigger (разные люди)
- WARNING/CRITICAL: single operator OK
- Auto-triggers: не требуют approval

#### 3. Recovery conditions:

```python
class KillSwitch:
    async def check_recovery_conditions(self) -> bool:
        """
        Проверить можно ли восстановиться.
        
        Условия recovery:
        - Drawdown < recovery_threshold (15%)
        - No losses последние 30 минут
        - Market data working
        - All exchanges healthy
        - Time elapsed > cooldown (1 hour)
        """
        # Условие 1: Drawdown нормализовался
        current_drawdown = await self.portfolio.get_current_drawdown()
        
        if current_drawdown > self.config.recovery_drawdown_threshold:
            logger.debug(
                "Recovery условие не выполнено: drawdown",
                current=current_drawdown,
                threshold=self.config.recovery_drawdown_threshold,
            )
            return False
        
        # Условие 2: Нет недавних убытков
        recent_pnl = await self.portfolio.get_pnl_last_n_minutes(30)
        
        if recent_pnl < 0:
            logger.debug(
                "Recovery условие не выполнено: недавние убытки",
                pnl_last_30min=recent_pnl,
            )
            return False
        
        # Условие 3: Market data работает
        market_data_healthy = await self.market_data.check_health()
        
        if not market_data_healthy:
            logger.debug("Recovery условие не выполнено: market data")
            return False
        
        # Условие 4: Все биржи healthy
        exchanges_healthy = await self.execution.check_all_exchanges_healthy()
        
        if not exchanges_healthy:
            logger.debug("Recovery условие не выполнено: exchanges")
            return False
        
        # Условие 5: Cooldown period прошел
        if self.triggered_at:
            elapsed = datetime.now(timezone.utc) - self.triggered_at
            
            if elapsed < self.config.cooldown_period:
                logger.debug(
                    "Recovery условие не выполнено: cooldown",
                    elapsed_minutes=elapsed.total_seconds() / 60,
                    required_minutes=self.config.cooldown_period.total_seconds() / 60,
                )
                return False
        
        # Все условия выполнены
        logger.info(
            "✅ Все recovery условия выполнены",
            drawdown=current_drawdown,
            elapsed_minutes=(datetime.now(timezone.utc) - self.triggered_at).total_seconds() / 60 if self.triggered_at else 0,
        )
        
        return True
```

**Recovery conditions:**
- Drawdown < 15% (recovery threshold)
- No losses последние 30 минут
- Market data + exchanges healthy
- Cooldown 1 час прошел
- Для EMERGENCY: require manual approval

### Мониторинг интеграций:

#### Метрики Kill Switch:

```python
# Kill switch triggers
kill_switch_triggers_total{severity, reason}
kill_switch_active{severity}  # gauge: 0 or 1

# Circuit breakers
circuit_breaker_triggers_total{name}
circuit_breaker_active{name}  # gauge

# Actions
positions_emergency_closed_total{}
orders_emergency_cancelled_total{}
kill_switch_action_duration_seconds{action_type}

# Recovery
kill_switch_recovery_attempts_total{outcome}  # outcome: success, failed
kill_switch_downtime_seconds{}  # gauge
```

#### Alerts:

**Critical (PagerDuty):**
- `kill_switch_triggers_total{severity="EMERGENCY"}` > 0
- `kill_switch_active{severity="EMERGENCY"}` == 1
- `positions_emergency_closed_total` > 0

**Warning:**
- `kill_switch_triggers_total{severity="WARNING"}` > 0
- `circuit_breaker_triggers_total` rate > 5/день

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 12

### Kill Switch:

**✅ Что реализовано:**
- Multi-level circuit breakers (WARNING, CRITICAL, EMERGENCY)
- Automatic triggers (drawdown, loss rate, error rate)
- Manual emergency stop (operator-triggered)
- Position liquidation (market orders)
- Order cancellation (all pending)
- Dual control (для EMERGENCY)
- Recovery conditions (auto + manual)
- Comprehensive audit trail

**❌ Что НЕ реализовано:**
- Partial liquidation (close only losing positions)
- Smart liquidation (minimize slippage)
- Cross-exchange hedging (при emergency)
- Predictive circuit breakers (ML-based)
- Gradual recovery (phased restart)

**⚠️ ВАЖНО:**
```markdown
Kill Switch использует MARKET orders для закрытия позиций.
Это гарантирует fill но может дать плохую цену (slippage).
Для smart liquidation требуется:
- Limit orders с aggressive pricing
- TWAP liquidation
- Фаза 20: Advanced Execution Algos

Dual control только для EMERGENCY manual triggers.
Auto-triggers (drawdown, etc) выполняются немедленно.

Recovery требует manual approval для EMERGENCY.
Auto-recovery работает только для WARNING/CRITICAL.
```

### Production Readiness Matrix:

| Компонент | После Фазы 12 | Production Ready |
|-----------|--------------|------------------|
| Circuit Breakers | ✅ Ready | ✅ Ready |
| Emergency Stop | ✅ Ready | ✅ Ready |
| Position Liquidation | ✅ Ready (market) | ⚠️ Smart для advanced |
| Dual Control | ✅ Ready | ✅ Ready |
| Recovery | ✅ Ready (manual) | ✅ Ready |
| Audit Trail | ✅ Ready | ✅ Ready |

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ

### Критические требования:

```
Операция                         Latency Target    Критичность
────────────────────────────────────────────────────────────────────
trigger_kill_switch()            <1s               CRITICAL (защита капитала)
close_all_positions()            <30s              CRITICAL
cancel_all_orders()              <5s               HIGH
check_recovery_conditions()      <1s               MEDIUM
────────────────────────────────────────────────────────────────────
```

---

## 📊 ОБЯЗАТЕЛЬНЫЕ BENCHMARK ТЕСТЫ

```python
@pytest.mark.benchmark
async def test_emergency_position_closure():
    """
    Acceptance: 10 positions closed <30s
    """
    kill_switch = KillSwitch(...)
    
    # Open 10 positions
    # ...
    
    start = time.time()
    action = await kill_switch._close_all_positions()
    duration = time.time() - start
    
    assert duration < 30, f"Closure {duration}s > 30s"
    assert action.success
    assert action.positions_closed == 10
```

**Acceptance Criteria:**
```
✅ trigger_latency: <1s
✅ position_closure: 10 positions <30s
✅ order_cancellation: all orders <5s
✅ recovery_check: <1s
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── src/
│   └── emergency/
│       ├── __init__.py
│       ├── kill_switch.py                # KillSwitch
│       ├── circuit_breakers.py           # CircuitBreaker configs
│       ├── dual_control.py               # Dual control logic
│       ├── recovery.py                   # Recovery conditions
│       └── models.py                     # EmergencySeverity, etc
│
└── tests/
    ├── unit/
    │   ├── test_kill_switch.py
    │   ├── test_circuit_breakers.py
    │   └── test_dual_control.py
    ├── integration/
    │   └── test_emergency_flow.py
    └── benchmarks/
        └── bench_emergency.py
```

---

## ACCEPTANCE CRITERIA

### Circuit Breakers
- [ ] Drawdown breaker
- [ ] Loss rate breaker
- [ ] Error rate breaker
- [ ] Data quality breaker

### Emergency Actions
- [ ] Cancel all orders
- [ ] Close all positions
- [ ] Freeze system

### Controls
- [ ] Dual control (EMERGENCY)
- [ ] Manual approval
- [ ] Recovery conditions

### Performance
- [ ] Trigger <1s
- [ ] Closure <30s
- [ ] Cancel <5s

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 12: Kill Switch & Emergency Controls** готова к реализации! 🚀

---

## 🆕 ДОПОЛНЕНИЯ v4.4 (VELOCITY KILLSWITCH ЦЕНТРАЛИЗАЦИЯ)

### VELOCITY KILLSWITCH — Централизованное управление из Фазы 5

**Проблема в текущей версии:**
Velocity KillSwitch реализован в Risk Engine (Фаза 5), но Фаза 12 — это
центральное место для ВСЕХ circuit breakers и emergency controls.
Velocity KillSwitch должен быть частью единой системы.

**Концепция из плана v4.4:**
Velocity KillSwitch (из Фазы 5) — автостоп при потере ≥2R за rolling window 10 сделок.
Cooldown: 24 часа после срабатывания.

**Централизация в Фазу 12:**

#### 1. Velocity KillSwitch переносится в Kill Switch Manager

**Файл:** `src/emergency/velocity_killswitch.py` ★ НОВЫЙ

```python
class VelocityKillSwitch:
    """
    Velocity-based circuit breaker — автостоп при высокой скорости потерь.
    
    Правило: Если за последние 10 сделок потеряно ≥2R → HALT на 24 часа.
    
    Логика:
        Rolling window из 10 последних сделок.
        На каждой новой сделке: рассчитать sum(r_multiple) за последние 10.
        Если sum(r_multiple) ≤ -2.0 → trigger.
    
    Cooldown:
        После срабатывания — 24 часа cooldown.
        Система не может торговать пока cooldown не истечёт.
        Сброс cooldown — только manual (operator UI).
    
    Integration:
        Risk Engine (Фаза 5) регистрирует каждую сделку с r_multiple.
        Velocity KillSwitch мониторит rolling window.
        При trigger → уведомляет Kill Switch Manager → HALT.
    """
    
    def __init__(self, config_manager, event_bus, state_machine):
        """
        Аргументы:
            config_manager: Параметры (max_loss_r, window_size, cooldown)
            event_bus: Для публикации VELOCITY_KILLSWITCH_TRIGGERED
            state_machine: Для перехода в HALT
        """
        self.config = config_manager
        self.event_bus = event_bus
        self.state_machine = state_machine
        
        # Параметры
        self.max_loss_r = Decimal(str(self.config.get(
            "risk.velocity_killswitch.max_loss_r", default=-2.0
        )))  # -2R
        self.window_size = int(self.config.get(
            "risk.velocity_killswitch.window_size", default=10
        ))  # 10 сделок
        self.cooldown_hours = int(self.config.get(
            "risk.velocity_killswitch.cooldown_hours", default=24
        ))  # 24 часа
        
        # State
        self.trade_history: Deque[Decimal] = deque(maxlen=self.window_size)
        self.is_triggered: bool = False
        self.triggered_at: Optional[datetime] = None
        self.cooldown_reset_by: Optional[str] = None
    
    async def register_trade(self, r_multiple: Decimal) -> None:
        """
        Зарегистрировать закрытие сделки.
        
        Вызывается Risk Engine при каждом POSITION_CLOSED.
        
        Аргументы:
            r_multiple: R-multiple сделки (profit / initial_risk)
                       Positive = прибыль, Negative = убыток
        """
        # Добавить в rolling window
        self.trade_history.append(r_multiple)
        
        logger.debug(
            "Сделка зарегистрирована в Velocity KillSwitch",
            r_multiple=float(r_multiple),
            window_size=len(self.trade_history),
            window_sum_r=float(sum(self.trade_history)),
        )
        
        # Проверить условие trigger только если window полный
        if len(self.trade_history) >= self.window_size:
            await self._check_trigger()
    
    async def _check_trigger(self) -> None:
        """
        Проверить условие срабатывания.
        
        Условие: sum(r_multiple за последние 10 сделок) ≤ -2.0
        """
        if self.is_triggered:
            return  # Уже сработал, в cooldown
        
        window_sum = sum(self.trade_history)
        
        if window_sum <= self.max_loss_r:
            # TRIGGER!
            await self._trigger(window_sum)
    
    async def _trigger(self, window_sum: Decimal) -> None:
        """
        Активировать Velocity KillSwitch.
        
        Действия:
        1. Установить triggered state
        2. Публиковать VELOCITY_KILLSWITCH_TRIGGERED event
        3. Уведомить State Machine → HALT
        4. Уведомить операторов (PagerDuty + Telegram)
        5. Записать в audit log
        """
        self.is_triggered = True
        self.triggered_at = datetime.utcnow()
        
        logger.critical(
            "🔴 VELOCITY KILLSWITCH СРАБОТАЛ",
            window_sum_r=float(window_sum),
            threshold_r=float(self.max_loss_r),
            window_size=self.window_size,
            cooldown_hours=self.cooldown_hours,
            last_10_trades=[float(r) for r in self.trade_history],
        )
        
        # Публиковать event
        await self.event_bus.publish({
            "type": "VELOCITY_KILLSWITCH_TRIGGERED",
            "priority": "CRITICAL",
            "payload": {
                "window_sum_r": float(window_sum),
                "threshold_r": float(self.max_loss_r),
                "window_size": self.window_size,
                "last_trades_r": [float(r) for r in self.trade_history],
                "triggered_at": self.triggered_at.isoformat(),
                "cooldown_until": (
                    self.triggered_at + timedelta(hours=self.cooldown_hours)
                ).isoformat(),
            }
        })
        
        # Уведомить State Machine
        await self.state_machine.transition("VELOCITY_KILLSWITCH_HALT", {
            "window_sum_r": float(window_sum),
            "cooldown_hours": self.cooldown_hours,
        })
        
        # Записать в БД
        await self._record_trigger_event(window_sum)
    
    def can_trade(self) -> tuple[bool, Optional[str]]:
        """
        Проверить можно ли торговать (не в cooldown).
        
        Вызывается Strategy Manager перед каждым сигналом.
        
        Возвращает:
            (allowed, rejection_reason)
        """
        if not self.is_triggered:
            return True, None
        
        # В cooldown
        cooldown_until = self.triggered_at + timedelta(hours=self.cooldown_hours)
        remaining = cooldown_until - datetime.utcnow()
        
        if remaining.total_seconds() > 0:
            return False, (
                f"velocity_killswitch_cooldown_"
                f"{int(remaining.total_seconds() / 3600)}h_remaining"
            )
        
        # Cooldown истёк → автоматическое восстановление
        logger.info(
            "Velocity KillSwitch cooldown истёк — автоматическое восстановление",
            triggered_at=self.triggered_at.isoformat(),
            cooldown_hours=self.cooldown_hours,
        )
        self._reset()
        return True, None
    
    async def reset_cooldown(self, operator: str) -> None:
        """
        Сбросить cooldown вручную (operator action).
        
        Только через UI. Требует подтверждения оператора.
        
        Аргументы:
            operator: Имя оператора (для audit trail)
        """
        if not self.is_triggered:
            logger.warning(
                "Попытка сброса cooldown когда KillSwitch не сработал",
                operator=operator,
            )
            return
        
        logger.warning(
            "Velocity KillSwitch cooldown сброшен вручную",
            operator=operator,
            triggered_at=self.triggered_at.isoformat(),
            cooldown_remaining_hours=(
                (self.triggered_at + timedelta(hours=self.cooldown_hours) - datetime.utcnow()).total_seconds() / 3600
            ),
        )
        
        self.cooldown_reset_by = operator
        self._reset()
        
        # Публиковать event
        await self.event_bus.publish({
            "type": "VELOCITY_KILLSWITCH_COOLDOWN_RESET",
            "priority": "HIGH",
            "payload": {
                "operator": operator,
                "triggered_at": self.triggered_at.isoformat(),
            }
        })
    
    def _reset(self) -> None:
        """Сбросить state (private)."""
        self.is_triggered = False
        self.triggered_at = None
        self.cooldown_reset_by = None
        # НЕ очищаем trade_history — rolling window продолжает работать
    
    def get_status(self) -> dict:
        """
        Получить текущий статус для UI / monitoring.
        
        Возвращает:
            {
              "is_triggered": False,
              "window_sum_r": -0.8,
              "threshold_r": -2.0,
              "last_10_trades_r": [-0.5, 0.3, -0.6, ...],
              "cooldown_until": None,
              "cooldown_remaining_hours": None
            }
        """
        cooldown_until = None
        cooldown_remaining = None
        
        if self.is_triggered and self.triggered_at:
            cooldown_until = self.triggered_at + timedelta(hours=self.cooldown_hours)
            remaining = cooldown_until - datetime.utcnow()
            if remaining.total_seconds() > 0:
                cooldown_remaining = remaining.total_seconds() / 3600
        
        return {
            "is_triggered": self.is_triggered,
            "window_sum_r": float(sum(self.trade_history)) if self.trade_history else 0.0,
            "threshold_r": float(self.max_loss_r),
            "window_size": self.window_size,
            "last_trades_r": [float(r) for r in self.trade_history],
            "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
            "cooldown_remaining_hours": cooldown_remaining,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "cooldown_reset_by": self.cooldown_reset_by,
        }
    
    async def _record_trigger_event(self, window_sum: Decimal) -> None:
        """Записать событие в audit log (PostgreSQL)."""
        # Делегируется KillSwitch manager
        pass
```

---

#### 2. Kill Switch Manager интеграция

**Обновлённый `src/emergency/kill_switch.py`:**

```python
class KillSwitch:
    """
    Центральный управляющий всеми circuit breakers и emergency controls.
    
    Новое v4.4: Включает Velocity KillSwitch из Фазы 5.
    """
    
    def __init__(
        self,
        config_manager,
        event_bus,
        state_machine,
        portfolio_governor,
        execution_layer,
        order_management,
    ):
        # Existing circuit breakers
        self.circuit_breakers = self._init_circuit_breakers()
        
        # ★ НОВОЕ v4.4: Velocity KillSwitch
        self.velocity_killswitch = VelocityKillSwitch(
            config_manager, event_bus, state_machine
        )
        
        # Подписка на события
        asyncio.create_task(self._subscribe_to_events())
    
    async def _subscribe_to_events(self):
        """
        Подписаться на события для мониторинга triggers.
        """
        # Подписка на POSITION_CLOSED для Velocity KillSwitch
        await self.event_bus.subscribe(
            "POSITION_CLOSED",
            self._on_position_closed,
        )
        
        # Подписка на VELOCITY_KILLSWITCH_TRIGGERED
        await self.event_bus.subscribe(
            "VELOCITY_KILLSWITCH_TRIGGERED",
            self._on_velocity_killswitch_triggered,
        )
    
    async def _on_position_closed(self, event: dict):
        """
        Обработчик POSITION_CLOSED — передать в Velocity KillSwitch.
        """
        payload = event.get("payload", {})
        r_multiple = payload.get("r_multiple")
        
        if r_multiple is not None:
            await self.velocity_killswitch.register_trade(Decimal(str(r_multiple)))
    
    async def _on_velocity_killswitch_triggered(self, event: dict):
        """
        Обработчик срабатывания Velocity KillSwitch.
        
        Действия:
        1. Записать в kill_switch_events (audit trail)
        2. Уведомить PagerDuty + Telegram
        3. Обновить UI dashboard
        """
        payload = event.get("payload", {})
        
        logger.critical(
            "Velocity KillSwitch сработал — централизованная обработка",
            window_sum_r=payload.get("window_sum_r"),
            threshold_r=payload.get("threshold_r"),
            cooldown_until=payload.get("cooldown_until"),
        )
        
        # Записать в audit log
        await self._record_killswitch_event(
            reason="velocity_killswitch_2r_10_trades",
            severity="CRITICAL",
            triggered_by="auto_velocity",
            system_state=payload,
            actions_taken=["halt_trading"],
        )
        
        # Уведомить операторов
        await self._alert_pagerduty(
            title="🔴 Velocity KillSwitch сработал",
            message=(
                f"Потеряно {payload['window_sum_r']:.2f}R за последние "
                f"{payload['window_size']} сделок (threshold: {payload['threshold_r']:.1f}R). "
                f"Торговля остановлена на {self.velocity_killswitch.cooldown_hours}h."
            ),
            severity="critical",
        )
    
    def get_all_circuit_breakers_status(self) -> dict:
        """
        Получить статус всех circuit breakers для UI dashboard.
        
        Возвращает:
            {
              "drawdown": {...},
              "loss_rate": {...},
              "error_rate": {...},
              "velocity_killswitch": {...}  ★ НОВОЕ
            }
        """
        status = {}
        
        # Existing circuit breakers
        for cb_name, cb_state in self.circuit_breakers.items():
            status[cb_name] = {
                "is_triggered": cb_state.is_triggered,
                "triggered_at": cb_state.triggered_at,
                "trigger_count": cb_state.trigger_count,
            }
        
        # ★ НОВОЕ: Velocity KillSwitch
        status["velocity_killswitch"] = self.velocity_killswitch.get_status()
        
        return status
```

---

#### 3. Database schema для Velocity KillSwitch

```sql
-- Velocity KillSwitch events (audit trail)
CREATE TABLE velocity_killswitch_events (
    id SERIAL PRIMARY KEY,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    window_sum_r NUMERIC(10, 4) NOT NULL,
    threshold_r NUMERIC(10, 4) NOT NULL,
    window_size INTEGER NOT NULL,
    last_trades_r JSONB NOT NULL,
    
    cooldown_until TIMESTAMPTZ NOT NULL,
    cooldown_reset_at TIMESTAMPTZ,
    cooldown_reset_by VARCHAR(100),
    
    recovered_at TIMESTAMPTZ
);

CREATE INDEX idx_velocity_ks_triggered ON velocity_killswitch_events(triggered_at DESC);
```

---

#### 4. UI Dashboard для Velocity KillSwitch

**Элементы UI (для Фазы 18 — Dashboard):**

```python
# Velocity KillSwitch Widget
{
  "widget_type": "velocity_killswitch_status",
  "data": {
    "is_triggered": False,
    "window_sum_r": -0.85,
    "threshold_r": -2.0,
    "progress": 42.5,  # (0.85 / 2.0) * 100 = 42.5%
    "last_10_trades": [
      {"r": -0.5, "symbol": "BTC/USDT"},
      {"r": 0.3, "symbol": "ETH/USDT"},
      {"r": -0.6, "symbol": "SOL/USDT"},
      ...
    ],
    "cooldown_remaining_hours": None,
    "reset_available": False
  },
  "actions": [
    {
      "type": "button",
      "label": "Reset Cooldown",
      "enabled": False,  # Только если triggered
      "requires_confirmation": True
    }
  ]
}
```

---

#### 5. Config параметры

**`config/risk.yaml`:**

```yaml
risk:
  velocity_killswitch:
    enabled: true
    max_loss_r: -2.0           # Trigger при ≤-2R
    window_size: 10            # За последние 10 сделок
    cooldown_hours: 24         # Cooldown 24 часа
    
    # Alerts
    warning_threshold_r: -1.5  # Warning при ≤-1.5R (75%)
    alert_channels:
      - pagerduty
      - telegram
      - email
```

---

## ACCEPTANCE CRITERIA v4.4

### Velocity KillSwitch Централизация ★ НОВОЕ
- [ ] VelocityKillSwitch класс в `src/emergency/velocity_killswitch.py`
- [ ] register_trade() вызывается на каждое POSITION_CLOSED
- [ ] Trigger при window_sum_r ≤ -2.0 за последние 10 сделок
- [ ] Cooldown 24 часа после срабатывания
- [ ] can_trade() проверка перед каждым сигналом
- [ ] reset_cooldown() — manual через UI (operator)
- [ ] Event: VELOCITY_KILLSWITCH_TRIGGERED
- [ ] Integration с Kill Switch Manager
- [ ] Database: velocity_killswitch_events таблица
- [ ] UI dashboard status widget

### Existing Circuit Breakers (как было)
- [ ] Drawdown breaker
- [ ] Loss rate breaker
- [ ] Error rate breaker
- [ ] Data quality breaker
- [ ] Manual emergency stop
- [ ] Dual control для EMERGENCY

---

**Version:** CRYPTOTEHNOLOG v4.4 (Фаза 12 — полная редакция)
**Dependencies:** Phases 0-11 (включая Фазу 5 Risk Engine с r_multiple tracking)
**Next:** Phase 13 - Notifications & Alerting (включает Velocity KillSwitch alerts)
