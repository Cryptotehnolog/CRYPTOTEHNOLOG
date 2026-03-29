
---

## 🆕 ДОПОЛНЕНИЯ v4.4 (CAPITAL MANAGER + VELOCITY + EXPOSURE LIMITS)

### 1. CAPITAL MANAGER — Управление капиталом как ресурсом

**Концепция из плана v4.4:**
Капитал — ограниченный ресурс. Выделяется стратегиям на основе performance. No trade without capital allocation check.

**Файл:** `src/portfolio/capital_manager.py`

```python
class CapitalManager:
    """
    Менеджер капитала — allocation и rebalancing между стратегиями.
    
    Allocation formula:
        Базовая — равномерная между стратегиями.
        Adjustment — на основе Sharpe ratio (30 дней).
        Лучшие стратегии → больше капитала, худшие → минимум 10%.
    
    Rebalancing triggers:
        - Equity change > 10%
        - Раз в неделю (периодически)
        - Добавление/удаление стратегий
    """
    
    def __init__(self, config, event_bus, analytics):
        self.allocations = {}  # {strategy: CapitalAllocation}
        
    async def check_can_allocate(self, strategy: str, size_usd: Decimal) -> tuple[bool, str]:
        """Проверить что стратегия может использовать size_usd капитала."""
        alloc = self.allocations.get(strategy)
        if not alloc:
            return False, "strategy_not_allocated"
        if alloc.used + size_usd > alloc.allocated:
            return False, "capital_exceeded"
        return True, None
    
    async def rebalance(self, total_equity: Decimal):
        """Пересчитать allocation между стратегиями."""
        # Performance-based allocation (Sharpe ratio)
        # Минимум 10% для худших
        # Event: CAPITAL_REBALANCED
```

**Новые dataclasses:**

```python
@dataclass
class CapitalAllocation:
    strategy_name: str
    allocated_usd: Decimal
    percentage: Decimal
    used_usd: Decimal
    free_usd: Decimal
    performance_score: float  # 0.0-1.0 (Sharpe ratio)
    last_rebalanced: datetime
```

**Database:**

```sql
CREATE TABLE capital_allocations (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    strategy VARCHAR(50),
    allocated_usd NUMERIC(20, 2),
    percentage NUMERIC(6, 4),
    performance_score NUMERIC(6, 4)
);
```

---

### 2. VELOCITY MONITOR — Time-based velocity monitoring

**Из плана v4.4:**
Time-based (не bar-based). Интерполяция для точного расчёта. 3 окна:
- Fast (15 мин): -1% → TRADING → DEGRADED
- Slow (4 часа): -3% → risk reduction 50%
- Stable (2 из 3): положительные → DEGRADED → TRADING

**Файл:** `src/portfolio/velocity_monitor.py`

```python
class VelocityMonitor:
    """Time-based velocity мониторинг equity."""
    
    FAST_WINDOW = 15 * 60      # 15 минут
    SLOW_WINDOW = 4 * 60 * 60  # 4 часа
    
    def __init__(self, config, event_bus, state_machine):
        self.equity_history = deque(maxlen=10000)  # ~3 месяца
        
    async def check_velocity(self):
        """Проверить velocity и триггерить State Machine."""
        fast = self._calculate_velocity(self.FAST_WINDOW)
        slow = self._calculate_velocity(self.SLOW_WINDOW)
        
        if fast < -0.01:
            # TRADING → DEGRADED
            await self.state_machine.transition("FAST_VELOCITY_ALERT")
        elif slow < -0.03:
            # Risk reduction 50%
            await self.state_machine.transition("SLOW_VELOCITY_ALERT")
    
    def _calculate_velocity(self, window_seconds: int) -> float:
        """Velocity с интерполяцией."""
        cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
        historical = self._find_or_interpolate(cutoff)
        return (current - historical) / historical
```

**Events:**

```json
{"type": "FAST_VELOCITY_ALERT", "velocity": -0.015, "threshold": -0.01}
{"type": "SLOW_VELOCITY_LIMIT", "velocity": -0.035, "action": "risk_reduction_50%"}
{"type": "STABLE_RECOVERED", "readings": [0.002, 0.005, 0.001]}
```

---

### 3. EXPOSURE LIMITS — Портфельные лимиты

**Из плана v4.4:**
3 типа лимитов:
1. Net Beta к BTC < 1.5
2. Long/Short Imbalance < 70%
3. Cluster Concentration < 40%

**Файл:** `src/portfolio/exposure_limits.py`

```python
class ExposureLimits:
    """Проверка портфельных exposure limits."""
    
    def __init__(self, config, portfolio):
        self.max_beta = 1.5
        self.max_imbalance = 0.70
        self.max_cluster_concentration = 0.40
    
    async def check_all(self):
        """Проверить все exposure limits."""
        snapshot = self._build_snapshot()
        
        # 1. Beta
        if abs(snapshot.net_beta_btc) > self.max_beta:
            await self._reduce_all(0.30)
        
        # 2. Imbalance
        if snapshot.imbalance_ratio > self.max_imbalance:
            await self._hedge_or_reduce(snapshot)
        
        # 3. Cluster
        for cluster, concentration in snapshot.cluster_concentrations.items():
            if concentration > self.max_cluster_concentration:
                await self._reduce_cluster(cluster, 0.20)
```

**Новые dataclasses:**

```python
@dataclass
class ExposureSnapshot:
    net_beta_btc: float
    imbalance_ratio: float  # abs(net) / gross
    cluster_concentrations: Dict[str, float]
    long_value: Decimal
    short_value: Decimal
```

---

### 4. DRAWDOWN PROTECTION — Защита от просадки

**Из плана v4.4:**
HWM tracking. Drawdown > 10% → emergency close all → CRITICAL.

**Файл:** `src/portfolio/drawdown_protection.py`

```python
class DrawdownProtection:
    """Защита от drawdown от HWM."""
    
    def __init__(self, config, portfolio, state_machine):
        self.hwm = Decimal(0)
        self.max_drawdown = Decimal("0.10")  # 10%
    
    async def check_drawdown(self, current_equity: Decimal):
        """Проверить drawdown от HWM."""
        if current_equity > self.hwm:
            self.hwm = current_equity
        
        drawdown = (self.hwm - current_equity) / self.hwm
        
        if drawdown > self.max_drawdown:
            logger.critical("MAX DRAWDOWN EXCEEDED",
                          drawdown=float(drawdown), hwm=float(self.hwm))
            await self._emergency_close_all()
            await self.state_machine.transition("CRITICAL")
```

---

### 5. POSITION MODEL — Расширенный с cluster, beta

**Обновлённый Position dataclass:**

```python
@dataclass
class Position:
    # ... existing fields ...
    
    # ★ НОВЫЕ ПОЛЯ v4.4
    cluster: Optional[str] = None  # "DeFi", "Layer1", "Meme"
    beta_btc: float = 0.0           # Бета к BTC
    capital_allocated_from: Optional[str] = None  # Стратегия-источник
```

**Database updates:**

```sql
ALTER TABLE positions
ADD COLUMN cluster VARCHAR(50),
ADD COLUMN beta_btc NUMERIC(6, 3),
ADD COLUMN capital_allocated_from VARCHAR(50);

CREATE INDEX idx_positions_cluster ON positions(cluster, status);
```

---

### 6. PORTFOLIO GOVERNOR — Интеграция всех компонентов

**Обновлённый PortfolioGovernor:**

```python
class PortfolioGovernor:
    """Портфельный управляющий с CapitalManager + VelocityMonitor."""
    
    def __init__(self, config, event_bus, state_machine):
        # Новые компоненты v4.4
        self.capital_manager = CapitalManager(config, event_bus, analytics)
        self.velocity_monitor = VelocityMonitor(config, event_bus, state_machine)
        self.exposure_limits = ExposureLimits(config, self)
        self.drawdown_protection = DrawdownProtection(config, self, state_machine)
        
        # Периодические проверки (раз в минуту)
        asyncio.create_task(self._monitoring_loop())
    
    async def _monitoring_loop(self):
        """Фоновый мониторинг equity, velocity, exposure, drawdown."""
        while True:
            await asyncio.sleep(60)
            
            # 1. Update equity
            current_equity = self._calculate_equity()
            self.velocity_monitor.record_equity(current_equity)
            
            # 2. Check velocity
            await self.velocity_monitor.check_velocity()
            
            # 3. Check exposure limits
            await self.exposure_limits.check_all()
            
            # 4. Check drawdown
            await self.drawdown_protection.check_drawdown(current_equity)
            
            # 5. Rebalance capital if needed
            equity_change = abs(current_equity - self.last_equity) / self.last_equity
            if equity_change > 0.10:  # >10% change
                await self.capital_manager.rebalance(current_equity)
                self.last_equity = current_equity
    
    async def open_position(self, signal, exec_price, quantity):
        """Открыть позицию с проверкой capital allocation."""
        # 1. Check capital allocation
        can_allocate, reason = await self.capital_manager.check_can_allocate(
            signal.strategy, signal.size_usd
        )
        if not can_allocate:
            logger.warning("Позиция отклонена capital check",
                         strategy=signal.strategy, reason=reason)
            return None
        
        # 2. Create position
        position = Position(...)
        position.cluster = await self._get_cluster(signal.symbol)
        position.beta_btc = await self._get_beta(signal.symbol)
        position.capital_allocated_from = signal.strategy
        
        # 3. Register capital usage
        await self.capital_manager.allocate_to_position(
            signal.strategy, position.size_usd
        )
        
        # 4. Add to active positions
        # ... rest of existing logic
        
        return position
```

---

## ACCEPTANCE CRITERIA v4.4

### CapitalManager ★ НОВОЕ
- [ ] Allocation капитала между стратегиями (performance-based)
- [ ] Rebalancing при equity change > 10%
- [ ] check_can_allocate() < 1μs (sync read)
- [ ] Минимум 10% allocation для худших
- [ ] Event: CAPITAL_ALLOCATED, CAPITAL_REBALANCED

### VelocityMonitor ★ НОВОЕ
- [ ] Time-based (не bar-based)
- [ ] Fast 15m: -1% → FAST_VELOCITY_ALERT → DEGRADED
- [ ] Slow 4h: -3% → SLOW_VELOCITY_LIMIT → risk reduction 50%
- [ ] Stable (2 из 3) → STABLE_RECOVERED → TRADING
- [ ] Интерполяция для точного расчёта

### ExposureLimits ★ НОВОЕ
- [ ] Max beta BTC < 1.5
- [ ] Long/short imbalance < 70%
- [ ] Cluster concentration < 40%
- [ ] Автоматические actions (reduce, hedge)

### DrawdownProtection ★ НОВОЕ
- [ ] HWM tracking
- [ ] Drawdown > 10% → emergency close all → CRITICAL
- [ ] Event: MAX_DRAWDOWN_EXCEEDED

### Position Management (существующее + расширения)
- [ ] Position с полями cluster, beta_btc, capital_allocated_from
- [ ] Open/close с capital allocation check
- [ ] Real-time P&L updates
- [ ] Automated SL/TP

---

**Version:** CRYPTOTEHNOLOG v4.4 (Фаза 9 — полная редакция)
**Dependencies:** Phases 0-8
**Next:** Phase 10 - Execution Layer
