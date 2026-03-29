# AI ПРОМТ: ФАЗА 14 - STRATEGY MANAGER

## КОНТЕКСТ

Вы — Senior Trading System Architect, специализирующийся на trading strategy orchestration, workflow automation, и system integration.

**Фазы 0-13 завершены.** Доступны:
- Event Bus, Control Plane, Config Manager
- Risk Engine, Market Data, Technical Indicators
- Signal Generator, Portfolio Governor
- Execution Layer, Order Management System
- Kill Switch, Notifications
- Database, Logging, Metrics

**Текущая задача:** Реализовать production-ready Strategy Manager — центральный orchestrator, который координирует весь торговый workflow от получения данных до исполнения, интегрирует все компоненты, и управляет жизненным циклом стратегий.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class StrategyManager:
    """
    Центральный orchestrator торгового workflow.
    
    Особенности:
    - Strategy lifecycle management (load, start, stop, reload)
    - Workflow orchestration (data → signals → risk → execution)
    - Multi-strategy coordination (parallel execution)
    - Performance tracking (per-strategy metrics)
    - Dynamic strategy activation/deactivation
    - Strategy parameter optimization (A/B testing)
    - Error isolation (один сбой не роняет других)
    - Event-driven architecture (reactive trading)
    """
    
    async def run_trading_cycle(self):
        """
        Основной торговый цикл (вызывается при новом баре).
        
        Workflow:
        1. Получить новый OHLCV bar
        2. Обновить индикаторы
        3. Для каждой активной стратегии:
           a. Сгенерировать сигнал
           b. Проверить risk (Risk Engine)
           c. Рассчитать position size
           d. Проверить portfolio limits
           e. Исполнить (Execution Layer)
        4. Обновить метрики
        5. Отправить уведомления
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.info("🔄 Торговый цикл начат", symbol="BTC/USDT", timeframe="5m")
logger.warning("⚠️  Стратегия пропущена", strategy="momentum", reason="indicator_not_ready")
logger.error("❌ Ошибка выполнения стратегии", strategy="breakout", error="execution_timeout")
logger.debug("✅ Сигнал успешно обработан", strategy="mean_reversion", signal="BUY", confidence=85)
```

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Strategy Manager — это "мозг" системы, который координирует ВСЕ компоненты. Получает market data, запрашивает indicators, генерирует signals, проверяет risks, рассчитывает position sizes, исполняет orders, отслеживает positions, и уведомляет операторов. Обеспечивает smooth workflow и error isolation.

### Входящие зависимости (что использует Strategy Manager):

#### 1. **Market Data Layer (Фаза 6)** → BAR_COMPLETED trigger
   - Event: Подписка на `BAR_COMPLETED`
   - Частота: зависит от timeframe (5m → 12/час)
   - Действие: Trigger нового торгового цикла
   - Критичность: CRITICAL (без data нет trading)

#### 2. **Technical Indicators (Фаза 7)** → запрос индикаторов
   - Запрос: `get_indicator(symbol, timeframe, indicator, params)`
   - Частота: при каждом bar (для каждой стратегии)
   - Действие: Получить RSI, MACD, Bollinger для стратегии
   - Критичность: HIGH

#### 3. **Signal Generator (Фаза 8)** → генерация сигналов
   - Запрос: `generate_signal(symbol, timeframe, strategy)`
   - Частота: при каждом bar
   - Действие: Получить торговый сигнал (BUY/SELL/NONE)
   - Критичность: HIGH

#### 4. **Risk Engine (Фаза 5)** → risk checks
   - Запрос: `check_trade(signal, position_size)`
   - Частота: при каждом сигнале
   - Действие: Проверить можно ли открыть позицию
   - Критичность: CRITICAL (защита капитала)

#### 5. **Portfolio Governor (Фаза 9)** → portfolio checks
   - Запрос: `check_can_open_position(symbol, size_usd, strategy)`
   - Частота: после risk check
   - Действие: Проверить portfolio limits
   - Критичность: HIGH

#### 6. **Execution Layer (Фаза 10)** → исполнение ордеров
   - Запрос: `execute_order(signal, position_size)`
   - Частота: после всех checks
   - Действие: Отправить ордер на биржу
   - Критичность: CRITICAL

#### 7. **Config Manager (Фаза 4)** → strategy configs
   - Запрос: `get_strategy_config(strategy_name)`
   - Частота: при load/reload стратегии
   - Действие: Получить параметры стратегии
   - Критичность: MEDIUM

#### 8. **State Machine (Фаза 2)** → system state checks
   - Запрос: `get_current_state()`
   - Частота: перед каждым циклом
   - Действие: Проверить можно ли торговать
   - Критичность: CRITICAL

### Исходящие зависимости (что публикует Strategy Manager):

#### 1. → Event Bus (Фаза 3)
   - **Event: `TRADING_CYCLE_STARTED`** (приоритет: NORMAL)
     - Payload: `{"symbol": "BTC/USDT", "timeframe": "5m", "active_strategies": 3}`
     - Подписчики: Observability

   - **Event: `TRADING_CYCLE_COMPLETED`** (приоритет: NORMAL)
     - Payload: `{"duration_ms": 150, "signals_generated": 1, "orders_placed": 1}`
     - Подписчики: Performance Analytics

   - **Event: `STRATEGY_SIGNAL_PROCESSED`** (приоритет: HIGH)
     - Payload:
       ```json
       {
         "strategy": "momentum",
         "signal": "BUY",
         "confidence": 85,
         "outcome": "executed",
         "order_id": "ord_123"
       }
       ```
     - Подписчики: Notifications, Analytics

   - **Event: `STRATEGY_ERROR`** (приоритет: HIGH)
     - Payload: `{"strategy": "breakout", "error": "indicator_timeout", "action": "skipped"}`
     - Подписчики: Notifications, Kill Switch (если too many errors)

#### 2. → Notifications (Фаза 13)
   - Уведомления о сигналах, ордерах, ошибках

#### 3. → PostgreSQL (performance tracking)
   - **Table: `strategy_performance`**
     ```sql
     CREATE TABLE strategy_performance (
         id SERIAL PRIMARY KEY,
         timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
         
         strategy_name VARCHAR(50) NOT NULL,
         
         signals_generated INTEGER DEFAULT 0,
         signals_executed INTEGER DEFAULT 0,
         signals_rejected INTEGER DEFAULT 0,
         
         total_pnl_usd NUMERIC(20, 2),
         win_rate NUMERIC(5, 2),
         
         avg_holding_time_seconds INTEGER,
         sharpe_ratio NUMERIC(10, 4),
         
         metadata JSONB
     );
     
     CREATE INDEX idx_strategy_perf_time ON strategy_performance(timestamp DESC);
     CREATE INDEX idx_strategy_perf_name ON strategy_performance(strategy_name, timestamp DESC);
     ```

#### 4. → Metrics (Prometheus)
   - Метрики: `trading_cycles_total`, `strategy_signals_total`, `strategy_errors_total`

### Контракты данных:

#### Strategy:

```python
from dataclasses import dataclass
from typing import Dict, Any, Callable, List
from enum import Enum

class StrategyStatus(str, Enum):
    """Статус стратегии."""
    INACTIVE = "INACTIVE"     # Не запущена
    ACTIVE = "ACTIVE"         # Активна
    PAUSED = "PAUSED"         # Приостановлена
    ERROR = "ERROR"           # Ошибка

@dataclass
class Strategy:
    """Торговая стратегия."""
    
    name: str  # "momentum", "mean_reversion"
    description: str
    
    # Configuration
    symbols: List[str]  # ["BTC/USDT", "ETH/USDT"]
    timeframes: List[str]  # ["5m", "15m"]
    
    # Parameters
    parameters: Dict[str, Any]  # {"rsi_period": 14, "rsi_oversold": 30}
    
    # Status
    status: StrategyStatus = StrategyStatus.INACTIVE
    
    # Performance tracking
    signals_generated: int = 0
    signals_executed: int = 0
    signals_rejected: int = 0
    
    total_pnl_usd: Decimal = Decimal("0")
    win_rate: Optional[Decimal] = None
    
    # Error tracking
    error_count: int = 0
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
```

#### TradingCycle:

```python
@dataclass
class TradingCycle:
    """Один торговый цикл."""
    
    cycle_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # Trigger
    symbol: str
    timeframe: str
    bar: OHLCVBar
    
    # Executed strategies
    strategies_executed: List[str] = None
    
    # Results
    signals_generated: int = 0
    orders_placed: int = 0
    errors_count: int = 0
    
    # Performance
    duration_ms: Optional[float] = None
    
    def __post_init__(self):
        if self.strategies_executed is None:
            self.strategies_executed = []
```

### Sequence Diagram (Trading Cycle Flow):

```
[Market Data] ──BAR_COMPLETED──> [Strategy Manager]
                                        |
                            [Check System State]
                            OPERATIONAL? → YES
                                        |
                            [Start Trading Cycle]
                                        |
                            ┌───────────┼───────────┐
                            v           v           v
                    [Strategy 1]  [Strategy 2]  [Strategy 3]
                    momentum      mean_reversion breakout
                            |           |           |
                    [Get Indicators]────┴───────────┘
                    RSI, MACD, Bollinger
                            |
                            v
                    [Generate Signal]
                    BUY, confidence: 85%
                            |
                            v
                    [Risk Engine Check]
                    allowed: True, position_size: $10,000
                            |
                            v
                    [Portfolio Check]
                    can_open: True
                            |
                            v
                    [Execute Order]
                    order_id: ord_123, status: SUBMITTED
                            |
                            v
                    [Track Result]
                    signal executed
                            |
                ┌───────────┴───────────┐
                v                       v
        [Notifications]         [Metrics]
        "✅ BUY executed"       signals_executed_total++
                            
[Any Component] ──ERROR──> [Strategy Manager]
                                |
                    [Error Isolation]
                    log + metrics + continue
                                |
                    [Check Error Rate]
                    >50% errors? → pause strategy
```

### Обработка ошибок интеграции:

#### 1. Strategy isolation (один сбой не роняет других):

```python
class StrategyManager:
    async def run_trading_cycle(self, bar: OHLCVBar):
        """
        Торговый цикл с error isolation.
        """
        cycle = TradingCycle(
            cycle_id=str(uuid.uuid4()),
            started_at=datetime.now(timezone.utc),
            symbol=bar.symbol,
            timeframe=bar.timeframe,
            bar=bar,
        )
        
        logger.info(
            "🔄 Торговый цикл начат",
            cycle_id=cycle.cycle_id,
            symbol=bar.symbol,
            timeframe=bar.timeframe,
        )
        
        # Получить активные стратегии для этого symbol+timeframe
        active_strategies = self._get_active_strategies(bar.symbol, bar.timeframe)
        
        # Execute каждую стратегию ИЗОЛИРОВАННО
        for strategy in active_strategies:
            try:
                # Execute стратегию
                result = await self._execute_strategy(strategy, bar)
                
                # Track result
                cycle.strategies_executed.append(strategy.name)
                
                if result.signal_generated:
                    cycle.signals_generated += 1
                
                if result.order_placed:
                    cycle.orders_placed += 1
                
            except Exception as e:
                # ИЗОЛИРОВАТЬ ошибку
                logger.error(
                    "❌ Ошибка выполнения стратегии",
                    strategy=strategy.name,
                    error=str(e),
                    traceback=traceback.format_exc(),
                )
                
                cycle.errors_count += 1
                
                # Update strategy error tracking
                strategy.error_count += 1
                strategy.last_error = str(e)
                strategy.last_error_at = datetime.now(timezone.utc)
                
                # Check error rate
                if strategy.error_count > 10:
                    logger.critical(
                        "🔴 Стратегия остановлена из-за частых ошибок",
                        strategy=strategy.name,
                        error_count=strategy.error_count,
                    )
                    
                    # Auto-pause strategy
                    strategy.status = StrategyStatus.PAUSED
                    
                    # Notify
                    await self.notifications.send_notification(
                        message=f"🔴 Стратегия {strategy.name} остановлена (>10 ошибок)",
                        severity=NotificationSeverity.CRITICAL,
                        channels=[NotificationChannel.TELEGRAM, NotificationChannel.EMAIL],
                    )
                
                # CONTINUE с другими стратегиями (не break!)
                continue
        
        # Complete cycle
        cycle.completed_at = datetime.now(timezone.utc)
        cycle.duration_ms = (cycle.completed_at - cycle.started_at).total_seconds() * 1000
        
        logger.info(
            "✅ Торговый цикл завершен",
            cycle_id=cycle.cycle_id,
            duration_ms=cycle.duration_ms,
            signals=cycle.signals_generated,
            orders=cycle.orders_placed,
            errors=cycle.errors_count,
        )
        
        # Publish event
        await self.event_bus.publish(Event(
            event_type="TRADING_CYCLE_COMPLETED",
            priority=Priority.Normal,
            source="strategy_manager",
            payload={
                "cycle_id": cycle.cycle_id,
                "duration_ms": cycle.duration_ms,
                "signals_generated": cycle.signals_generated,
                "orders_placed": cycle.orders_placed,
                "errors_count": cycle.errors_count,
            },
        ))
```

**Error isolation:**
- Each strategy в try-except
- Error → log + track + continue
- >10 errors → auto-pause strategy
- NEVER break цикл для других стратегий

#### 2. Timeout для каждого шага:

```python
class StrategyManager:
    async def _execute_strategy(
        self,
        strategy: Strategy,
        bar: OHLCVBar,
    ) -> StrategyExecutionResult:
        """
        Execute стратегию с timeout на каждый шаг.
        """
        result = StrategyExecutionResult(strategy_name=strategy.name)
        
        # Step 1: Get indicators (timeout 500ms)
        try:
            indicators = await asyncio.wait_for(
                self._get_strategy_indicators(strategy, bar.symbol, bar.timeframe),
                timeout=0.5,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "⚠️  Timeout получения индикаторов",
                strategy=strategy.name,
            )
            return result  # Skip strategy
        
        # Step 2: Generate signal (timeout 1s)
        try:
            signal = await asyncio.wait_for(
                self.signal_generator.generate_signal(
                    symbol=bar.symbol,
                    timeframe=bar.timeframe,
                    strategy_name=strategy.name,
                ),
                timeout=1.0,
            )
            
            if signal:
                result.signal_generated = True
            else:
                return result  # No signal
                
        except asyncio.TimeoutError:
            logger.warning(
                "⚠️  Timeout генерации сигнала",
                strategy=strategy.name,
            )
            return result
        
        # Step 3: Risk check (timeout 500ms)
        try:
            risk_check = await asyncio.wait_for(
                self.risk_engine.check_trade(signal, position_size),
                timeout=0.5,
            )
            
            if not risk_check.allowed:
                logger.info(
                    "⛔ Сигнал отклонен Risk Engine",
                    strategy=strategy.name,
                    reason=risk_check.reason,
                )
                result.signal_rejected = True
                return result
                
        except asyncio.TimeoutError:
            logger.warning(
                "⚠️  Timeout risk check",
                strategy=strategy.name,
            )
            return result
        
        # Step 4: Execute order (timeout 30s)
        try:
            order = await asyncio.wait_for(
                self.execution.execute_order(signal, position_size),
                timeout=30.0,
            )
            
            result.order_placed = True
            result.order_id = order.order_id
            
        except asyncio.TimeoutError:
            logger.error(
                "❌ Timeout исполнения ордера",
                strategy=strategy.name,
            )
            # Critical: order may be partially filled
            await self._handle_execution_timeout(signal)
        
        return result
```

**Timeout policy:**
- Get indicators: 500ms
- Generate signal: 1s
- Risk check: 500ms
- Execute order: 30s
- При timeout → skip step + continue

#### 3. Graceful degradation при component failures:

```python
class StrategyManager:
    async def _get_strategy_indicators(
        self,
        strategy: Strategy,
        symbol: str,
        timeframe: str,
    ) -> Dict[str, IndicatorValue]:
        """
        Получить индикаторы с fallback.
        """
        required_indicators = strategy.parameters.get("indicators", {})
        
        indicators = {}
        failed_indicators = []
        
        for indicator_name, params in required_indicators.items():
            try:
                indicator = await self.indicator_engine.calculate(
                    symbol=symbol,
                    timeframe=timeframe,
                    indicator=indicator_name,
                    params=params,
                )
                
                # Check is_valid
                if indicator.is_valid:
                    indicators[indicator_name] = indicator
                else:
                    logger.debug(
                        "Индикатор не готов",
                        indicator=indicator_name,
                        warming_bars_left=indicator.warming_bars_left,
                    )
                    failed_indicators.append(indicator_name)
                    
            except Exception as e:
                logger.error(
                    "Ошибка получения индикатора",
                    indicator=indicator_name,
                    error=str(e),
                )
                failed_indicators.append(indicator_name)
        
        # Проверить есть ли минимум необходимых индикаторов
        min_required = strategy.parameters.get("min_required_indicators", len(required_indicators))
        
        if len(indicators) < min_required:
            raise InsufficientDataError(
                f"Только {len(indicators)}/{len(required_indicators)} индикаторов готовы"
            )
        
        return indicators
```

**Graceful degradation:**
- Если индикатор failed → continue с остальными
- Проверка min_required_indicators
- Если too many failed → skip strategy
- Never crash весь цикл

### Мониторинг интеграций:

#### Метрики Strategy Manager:

```python
# Trading cycles
trading_cycles_total{symbol, timeframe}
trading_cycle_duration_seconds{percentile}
trading_cycles_errors_total{error_type}

# Strategies
strategy_status{strategy_name}  # gauge: 0=inactive, 1=active, 2=paused, 3=error
strategies_active_count{}  # gauge

# Signals
strategy_signals_generated_total{strategy_name, outcome}  # outcome: executed, rejected, error
strategy_signals_executed_total{strategy_name}
strategy_signals_rejected_total{strategy_name, reason}

# Performance
strategy_pnl_usd{strategy_name}  # gauge
strategy_win_rate{strategy_name}  # gauge
strategy_sharpe_ratio{strategy_name}  # gauge

# Errors
strategy_errors_total{strategy_name, error_type}
strategy_timeouts_total{strategy_name, step}
```

#### Alerts:

**Critical:**
- `strategy_errors_total{strategy_name}` > 10 за час
- `strategies_active_count` == 0 (no active strategies)
- `trading_cycle_duration_seconds{p99}` > 10 секунд

**Warning:**
- `strategy_signals_rejected_total` rate > 80%
- `strategy_timeouts_total` > 5/час

---

## 📊 ОБЯЗАТЕЛЬНЫЕ BENCHMARK ТЕСТЫ

```python
@pytest.mark.benchmark
async def test_trading_cycle_latency():
    """
    Acceptance: <1s для 3 strategies
    """
    manager = StrategyManager(...)
    
    # 3 active strategies
    # ...
    
    start = time.time()
    await manager.run_trading_cycle(bar)
    duration = time.time() - start
    
    assert duration < 1.0, f"Cycle {duration}s > 1s"

@pytest.mark.benchmark
async def test_error_isolation():
    """
    Проверить что ошибка в одной стратегии не роняет другие.
    """
    # Strategy 1: normal
    # Strategy 2: raise exception
    # Strategy 3: normal
    
    # После цикла: strategies 1 и 3 должны выполниться
    # ...
```

**Acceptance Criteria:**
```
✅ trading_cycle: <1s для 3 strategies
✅ error_isolation: 1 failed → 2 others OK
✅ timeout_handling: step timeout → skip + continue
✅ graceful_degradation: component down → reduced functionality
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── src/
│   └── strategy_manager/
│       ├── __init__.py
│       ├── manager.py                    # StrategyManager
│       ├── orchestrator.py               # Trading cycle orchestration
│       ├── strategy_loader.py            # Load/reload strategies
│       ├── performance_tracker.py        # Per-strategy metrics
│       └── models.py                     # Strategy, TradingCycle
│
└── tests/
    ├── unit/
    │   ├── test_orchestrator.py
    │   ├── test_error_isolation.py
    │   └── test_performance_tracker.py
    ├── integration/
    │   └── test_strategy_manager.py
    └── benchmarks/
        └── bench_strategy_manager.py
```

---

## ACCEPTANCE CRITERIA

### Orchestration
- [ ] Trading cycle на каждый BAR_COMPLETED
- [ ] Multi-strategy coordination
- [ ] Error isolation
- [ ] Timeout handling

### Integration
- [ ] All components integrated
- [ ] Event-driven workflow
- [ ] Graceful degradation

### Performance
- [ ] Cycle <1s (3 strategies)
- [ ] Parallel strategy execution
- [ ] <500ms per strategy

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 14: Strategy Manager** готова к реализации! 🚀

**ЦЕНТРАЛЬНЫЙ ORCHESTRATOR — ВСЕХ КОМПОНЕНТОВ СОБРАНЫ ВМЕСТЕ!**

---

## 🆕 ДОПОЛНЕНИЯ v4.4 (METACLASSIFIER + OPPORTUNITYENGINE + CAPITALMANAGER INTEGRATION)

### 1. METACLASSIFIER INTEGRATION — Разрешение конфликтов стратегий

**Проблема из плана v4.4:**
Несколько стратегий могут генерировать противоречивые сигналы одновременно:
- DonchianBreakout → BUY (confidence: 78)
- MomentumStrategy → SELL (confidence: 65)

**Решение:** MetaClassifier из Фазы 8

**Обновлённый _execute_strategy_cycle():**

```python
class StrategyManager:
    async def _execute_strategy_cycle(self, bar: OHLCVBar):
        """
        Выполнить торговый цикл с MetaClassifier conflict resolution.
        
        Новый workflow v4.4:
        1. Генерировать сигналы от ВСЕХ активных стратегий (параллельно)
        2. Передать все сигналы в MetaClassifier
        3. MetaClassifier разрешает конфликты → возвращает winning signal или ABSTAIN
        4. Если winning signal → проверить risk, portfolio, execute
        5. Если ABSTAIN → логировать конфликт, не торговать
        """
        # Шаг 1: Генерировать сигналы от всех стратегий параллельно
        signals_by_strategy = {}
        
        tasks = []
        for strategy in self.active_strategies:
            task = self.signal_generator.generate_signal(
                symbol=bar.symbol,
                timeframe=bar.timeframe,
                strategy_name=strategy.name,
            )
            tasks.append((strategy.name, task))
        
        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
        
        for (strategy_name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error("Ошибка генерации сигнала", strategy=strategy_name, error=str(result))
                signals_by_strategy[strategy_name] = None
            else:
                signals_by_strategy[strategy_name] = result
        
        # Шаг 2: Разрешение конфликтов через MetaClassifier
        resolution, winning_signal, reason = await self.meta_classifier.resolve(
            symbol=bar.symbol,
            signals=signals_by_strategy,
        )
        
        if resolution == "ABSTAIN":
            logger.warning(
                "Конфликт стратегий — ABSTAIN",
                symbol=bar.symbol,
                strategies=list(signals_by_strategy.keys()),
                reason=reason,
            )
            # Публиковать event для аудита
            await self.event_bus.publish({
                "type": "CONFLICT_RESOLVED",
                "priority": "NORMAL",
                "payload": {
                    "symbol": bar.symbol,
                    "resolution": "ABSTAIN",
                    "reason": reason,
                    "signals": {s: sig.direction.value if sig else None 
                               for s, sig in signals_by_strategy.items()},
                }
            })
            return  # Не торговать
        
        # Шаг 3: Winning signal → execute
        logger.info(
            "Конфликт разрешён — winning signal",
            symbol=bar.symbol,
            winning_strategy=winning_signal.strategy,
            direction=winning_signal.direction.value,
            confidence=winning_signal.confidence,
            reason=reason,
        )
        
        # Продолжить с risk check, portfolio check, execution
        await self._execute_signal(winning_signal)
```

**Новый компонент:** `src/strategy_manager/conflict_resolver.py`

```python
class ConflictResolver:
    """Обёртка над MetaClassifier из Фазы 8 для Strategy Manager."""
    
    def __init__(self, meta_classifier, event_bus):
        self.meta_classifier = meta_classifier
        self.event_bus = event_bus
    
    async def resolve_and_execute(self, signals_by_strategy, bar):
        """
        Разрешить конфликт и вернуть winning signal или None.
        """
        resolution, winning_signal, reason = await self.meta_classifier.resolve(
            symbol=bar.symbol,
            signals=signals_by_strategy,
        )
        
        if resolution == "WINNER":
            return winning_signal
        else:
            # ABSTAIN — логировать и вернуть None
            await self._log_conflict(signals_by_strategy, reason)
            return None
```

**Database:** Уже есть `conflict_log` таблица из Фазы 8.

---

### 2. OPPORTUNITYENGINE INTEGRATION — Ранжирование символов для торговли

**Концепция из плана v4.4:**
OpportunityEngine (Фаза 8) ранжирует символы по opportunity score.
Strategy Manager торгует только топ-N символов (configurable, default 5).

**Обновлённый торговый цикл:**

```python
class StrategyManager:
    async def run_trading_cycle_multi_symbol(self, bar_events: List[OHLCVBar]):
        """
        Торговый цикл для ВСЕХ символов вселенной.
        
        Workflow v4.4:
        1. Получить current admissible universe (из UniverseEngine Фазы 6)
        2. Для каждого символа: сгенерировать сигналы от всех стратегий
        3. Передать все сигналы в OpportunityEngine для скоринга
        4. OpportunityEngine возвращает топ-N символов (отранжированных)
        5. Торговать только топ-N символов
        """
        # Шаг 1: Получить admissible universe
        universe, version, confidence, _ = self.universe_engine.get_universe(
            min_confidence=0.6
        )
        
        if not universe:
            logger.warning("Вселенная пуста — торговля невозможна", version=version)
            return
        
        logger.info(
            "Торговый цикл начат для вселенной",
            symbols_count=len(universe),
            confidence=confidence,
            version=version,
        )
        
        # Шаг 2: Генерировать сигналы для ВСЕХ символов
        signals_by_symbol = {}
        
        for symbol_obj in universe:
            symbol = symbol_obj.name
            
            # Генерировать сигналы от всех стратегий для этого символа
            signals_by_strategy = await self._generate_signals_for_symbol(symbol, bar_events)
            
            # MetaClassifier разрешает конфликты
            winning_signal = await self.conflict_resolver.resolve_and_execute(
                signals_by_strategy, symbol
            )
            
            signals_by_symbol[symbol] = winning_signal
        
        # Шаг 3: OpportunityEngine ранжирует символы
        top_opportunities = await self.opportunity_engine.score_all(signals_by_symbol)
        
        top_n = int(self.config.get("strategy.max_concurrent_symbols", default=5))
        
        logger.info(
            "Возможности отранжированы",
            total_symbols=len(signals_by_symbol),
            top_n=top_n,
            top_symbol=top_opportunities[0].symbol if top_opportunities else "нет",
            top_score=top_opportunities[0].total_score if top_opportunities else 0,
        )
        
        # Шаг 4: Торговать только топ-N
        for opp in top_opportunities[:top_n]:
            signal = opp.best_signal
            if signal:
                await self._execute_signal(signal)
```

**Новый компонент:** `src/strategy_manager/opportunity_selector.py`

```python
class OpportunitySelector:
    """Обёртка над OpportunityEngine из Фазы 8 для Strategy Manager."""
    
    def __init__(self, opportunity_engine, config):
        self.opportunity_engine = opportunity_engine
        self.config = config
    
    async def select_top_symbols(self, signals_by_symbol):
        """
        Отранжировать символы и вернуть топ-N для торговли.
        
        Возвращает: List[OpportunityScore] (топ-N)
        """
        top_n = int(self.config.get("strategy.max_concurrent_symbols", default=5))
        
        ranked = await self.opportunity_engine.score_all(signals_by_symbol)
        
        return ranked[:top_n]
```

---

### 3. CAPITALMANAGER INTEGRATION — Проверка capital allocation

**Концепция из плана v4.4:**
No trade without capital allocation check (CapitalManager из Фазы 9).

**Обновлённый _execute_signal():**

```python
class StrategyManager:
    async def _execute_signal(self, signal: TradingSignal):
        """
        Исполнить сигнал с проверками: risk, portfolio, capital.
        
        Новый workflow v4.4:
        1. Risk Engine check
        2. Portfolio Governor check
        3. CapitalManager check (★ НОВОЕ)
        4. Execute order
        """
        # Existing: Risk Engine check
        risk_check = await self.risk_engine.check_trade(signal, position_size)
        if not risk_check.allowed:
            logger.info("Сигнал отклонён Risk Engine", reason=risk_check.reason)
            return
        
        # Existing: Portfolio Governor check
        can_open, reason = await self.portfolio.check_can_open_position(
            signal.symbol, signal.size_usd, signal.strategy
        )
        if not can_open:
            logger.info("Сигнал отклонён Portfolio", reason=reason)
            return
        
        # ★ НОВОЕ v4.4: CapitalManager check
        can_allocate, reason = await self.capital_manager.check_can_allocate(
            signal.strategy, signal.size_usd
        )
        if not can_allocate:
            logger.warning(
                "Сигнал отклонён CapitalManager",
                strategy=signal.strategy,
                size_usd=float(signal.size_usd),
                reason=reason,
            )
            # Метрика
            self.metrics.signals_rejected_total.labels(
                strategy=signal.strategy,
                reason="capital_exceeded",
            ).inc()
            return
        
        # Execute order
        order = await self.execution.execute_order(signal, position_size)
        
        # ★ НОВОЕ v4.4: Register capital usage
        await self.capital_manager.allocate_to_position(
            signal.strategy, signal.size_usd
        )
        
        logger.info(
            "Сигнал исполнен",
            strategy=signal.strategy,
            symbol=signal.symbol,
            order_id=order.order_id,
        )
```

---

### 4. PYRAMIDING INTEGRATION — Автоматическое масштабирование позиций

**Концепция из плана v4.4:**
PyramidingManager из Фазы 8 автоматически добавляет к прибыльным позициям.

**Новый обработчик:**

```python
class StrategyManager:
    async def _on_bar_completed(self, bar: OHLCVBar):
        """
        Обработчик BAR_COMPLETED с pyramiding check.
        
        Workflow v4.4:
        1. Run normal trading cycle (signals, execution)
        2. Check pyramiding opportunities для ВСЕХ открытых позиций (★ НОВОЕ)
        """
        # Обычный торговый цикл
        await self.run_trading_cycle(bar)
        
        # ★ НОВОЕ: Pyramiding check
        open_positions = await self.portfolio.get_open_positions()
        
        for position in open_positions:
            # Получить market data для символа
            market_data = {
                "close": bar.close,
                "high": bar.high,
                "low": bar.low,
                "atr": await self._get_atr(position.symbol),
                "adx": await self._get_adx(position.symbol),
            }
            
            # Проверить pyramiding opportunity
            pyramid_tier = await self.pyramiding_manager.check_pyramid_opportunity(
                position, market_data
            )
            
            if pyramid_tier:
                logger.info(
                    "Pyramiding добавлен к позиции",
                    position_id=position.position_id,
                    tier=pyramid_tier.tier_number,
                    additional_size_r=float(pyramid_tier.additional_size_r),
                )
```

---

### 5. STRATEGY MANAGER — Полностью обновлённый main class

**Новый __init__ с v4.4 компонентами:**

```python
class StrategyManager:
    """
    Strategy Manager v4.4 — центральный orchestrator.
    
    Новые компоненты v4.4:
    - MetaClassifier (conflict resolution)
    - OpportunityEngine (symbol ranking)
    - CapitalManager (allocation check)
    - PyramidingManager (position scaling)
    - UniverseEngine (admissible symbols)
    """
    
    def __init__(
        self,
        config_manager,
        event_bus,
        state_machine,
        # Existing
        signal_generator,
        risk_engine,
        portfolio_governor,
        execution_layer,
        indicator_engine,
        # ★ НОВЫЕ v4.4
        meta_classifier,         # Из Фазы 8
        opportunity_engine,      # Из Фазы 8
        pyramiding_manager,      # Из Фазы 8
        capital_manager,         # Из Фазы 9
        universe_engine,         # Из Фазы 6
    ):
        self.config = config_manager
        self.event_bus = event_bus
        self.state_machine = state_machine
        
        # Existing components
        self.signal_generator = signal_generator
        self.risk_engine = risk_engine
        self.portfolio = portfolio_governor
        self.execution = execution_layer
        self.indicators = indicator_engine
        
        # ★ НОВЫЕ компоненты v4.4
        self.meta_classifier = meta_classifier
        self.opportunity_engine = opportunity_engine
        self.pyramiding_manager = pyramiding_manager
        self.capital_manager = capital_manager
        self.universe_engine = universe_engine
        
        # Обёртки
        self.conflict_resolver = ConflictResolver(meta_classifier, event_bus)
        self.opportunity_selector = OpportunitySelector(opportunity_engine, config)
        
        # Existing: active strategies
        self.active_strategies = {}
        
        # Подписка на события
        asyncio.create_task(self._subscribe_to_events())
```

---

## ACCEPTANCE CRITERIA v4.4

### MetaClassifier Integration ★ НОВОЕ
- [ ] Генерация сигналов от всех стратегий параллельно
- [ ] MetaClassifier разрешает конфликты (WINNER / ABSTAIN)
- [ ] ABSTAIN → логирование + no trade
- [ ] Event: CONFLICT_RESOLVED

### OpportunityEngine Integration ★ НОВОЕ
- [ ] Скоринг всех символов из admissible universe
- [ ] Топ-N символов для торговли (configurable, default 5)
- [ ] Event: OPPORTUNITY_SCORED

### CapitalManager Integration ★ НОВОЕ
- [ ] check_can_allocate() перед каждой сделкой
- [ ] allocate_to_position() после execution
- [ ] Reject signal если capital exceeded

### Pyramiding Integration ★ НОВОЕ
- [ ] check_pyramid_opportunity() для всех open positions
- [ ] Автоматическое добавление tier 2/3
- [ ] Event: PYRAMID_SIGNAL

### Orchestration (существующее + расширения)
- [ ] Trading cycle на BAR_COMPLETED
- [ ] Multi-strategy coordination
- [ ] Error isolation
- [ ] Timeout handling на каждом шаге

---

**Version:** CRYPTOTEHNOLOG v4.4 (Фаза 14 — полная редакция)
**Dependencies:** Phases 0-13 (включая Фазу 8 с MetaClassifier/OpportunityEngine/Pyramiding, Фазу 9 с CapitalManager, Фазу 6 с UniverseEngine)
**Next:** Phase 15 - Performance Analytics (SimulationEngine + MAE/MFE analytics)
