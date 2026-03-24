# AI ПРОМТ: ФАЗА 15 - PERFORMANCE ANALYTICS

## КОНТЕКСТ

Вы — Senior Quantitative Analyst, специализирующийся на trading performance analysis, risk-adjusted returns, и strategy optimization.

**Фазы 0-13 завершены.** Доступны:
- Event Bus, Control Plane, Config Manager
- Risk Engine, Market Data, Technical Indicators
- Signal Generator, Portfolio Governor
- Execution Layer, Order Management System
- Kill Switch, Notifications
- Database Layer, Logging, Metrics — готовы

**Текущая задача:** Реализовать production-ready Performance Analytics с comprehensive metrics (Sharpe, Sortino, Max DD, Win Rate), trade analysis, strategy comparison, и automated reporting.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class PerformanceAnalytics:
    """
    Аналитическая система для оценки торговой производительности.
    
    Особенности:
    - Risk-adjusted metrics (Sharpe ratio, Sortino ratio, Calmar ratio)
    - Trade analysis (win rate, profit factor, avg R-multiple)
    - Drawdown analysis (max DD, recovery time, underwater curve)
    - Strategy comparison (performance по стратегиям)
    - Time-series analysis (daily/weekly/monthly returns)
    - Rolling metrics (30-day Sharpe, rolling win rate)
    - Benchmark comparison (vs BTC buy-and-hold)
    - Automated reporting (daily/weekly/monthly reports)
    """
    
    def calculate_sharpe_ratio(
        self,
        returns: np.ndarray,
        risk_free_rate: Decimal = Decimal("0.02"),
        periods_per_year: int = 365,
    ) -> Decimal:
        """
        Рассчитать Sharpe Ratio (risk-adjusted return).
        
        Аргументы:
            returns: Массив daily returns
            risk_free_rate: Безрисковая ставка (годовая, default 2%)
            periods_per_year: Периодов в году (365 для daily)
        
        Формула:
            Sharpe = (Mean Return - Risk Free Rate) / Std Dev Returns
            Annualized: Sharpe * sqrt(periods_per_year)
        
        Интерпретация:
            > 3.0: Отлично
            2.0-3.0: Очень хорошо
            1.0-2.0: Хорошо
            < 1.0: Плохо
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.info("📊 Метрики рассчитаны", sharpe=2.35, sortino=3.12, max_dd=0.15)
logger.debug("Rolling Sharpe обновлен", window=30, current_sharpe=2.1)
logger.warning("⚠️  Производительность ухудшилась", win_rate=0.35, threshold=0.50)
```

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Performance Analytics — аналитический engine для оценки качества торговли. Собирает данные о позициях, сделках, P&L из Portfolio Governor и Order Management. Рассчитывает comprehensive metrics (Sharpe, Sortino, Win Rate, Max DD). Сравнивает стратегии. Генерирует automated reports. Помогает optimize trading strategies.

### Входящие зависимости:

#### 1. **Portfolio Governor (Фаза 9)** → closed positions
   - Query: `get_closed_positions(start_date, end_date)`
   - Частота: при расчете metrics (daily/weekly)
   - Data: Position с realized_pnl, holding_time, outcome
   - Критичность: HIGH (основные данные для анализа)

#### 2. **Portfolio Governor (Фаза 9)** → equity curve
   - Query: `get_equity_history(start_date, end_date)`
   - Частота: при расчете metrics
   - Data: Timeseries equity_usd
   - Критичность: HIGH (для returns, drawdown)

#### 3. **Order Management (Фаза 11)** → order statistics
   - Query: `get_order_statistics(strategy, period)`
   - Частота: weekly reports
   - Data: Fill quality, slippage, execution time
   - Критичность: MEDIUM

### Исходящие зависимости:

#### 1. → PostgreSQL (metrics storage)
   - **Table: `performance_metrics`**
     ```sql
     CREATE TABLE performance_metrics (
         metric_id SERIAL PRIMARY KEY,
         calculated_at TIMESTAMPTZ NOT NULL,
         period_start DATE NOT NULL,
         period_end DATE NOT NULL,
         
         -- Strategy filter
         strategy VARCHAR(50),  -- NULL = all strategies
         
         -- Returns
         total_return_percent NUMERIC(10, 4),
         annualized_return_percent NUMERIC(10, 4),
         
         -- Risk-adjusted
         sharpe_ratio NUMERIC(10, 4),
         sortino_ratio NUMERIC(10, 4),
         calmar_ratio NUMERIC(10, 4),
         
         -- Drawdown
         max_drawdown_percent NUMERIC(10, 4),
         max_drawdown_duration_days INTEGER,
         recovery_time_days INTEGER,
         
         -- Trade stats
         total_trades INTEGER,
         win_rate NUMERIC(5, 4),
         profit_factor NUMERIC(10, 4),
         average_win_usd NUMERIC(20, 2),
         average_loss_usd NUMERIC(20, 2),
         average_r_multiple NUMERIC(10, 4),
         
         -- Time-based
         best_day_return_percent NUMERIC(10, 4),
         worst_day_return_percent NUMERIC(10, 4),
         
         metadata JSONB
     );
     
     CREATE INDEX idx_metrics_period ON performance_metrics(period_start, period_end);
     CREATE INDEX idx_metrics_strategy ON performance_metrics(strategy, period_start);
     ```

#### 2. → Notifications (Фаза 13)
   - Report: Daily/Weekly/Monthly performance report
   - Channel: Email (HTML), Telegram (summary)
   - Частота: daily @ 00:00 UTC

#### 3. → Metrics (Prometheus)
   - Gauge: `current_sharpe_ratio`, `current_win_rate`

### Контракты данных:

#### PerformanceMetrics:

```python
from dataclasses import dataclass
from decimal import Decimal
from datetime import date
from typing import Optional

@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""
    
    calculated_at: datetime
    period_start: date
    period_end: date
    
    strategy: Optional[str] = None  # None = all strategies
    
    # Returns
    total_return_percent: Decimal
    annualized_return_percent: Decimal
    
    # Risk-adjusted
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    
    # Drawdown
    max_drawdown_percent: Decimal
    max_drawdown_duration_days: int
    recovery_time_days: Optional[int] = None
    
    # Trade stats
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    profit_factor: Decimal
    average_win_usd: Decimal
    average_loss_usd: Decimal
    average_r_multiple: Decimal
    
    # Time-based
    best_day_return_percent: Decimal
    worst_day_return_percent: Decimal
    
    # Additional
    metadata: Dict[str, Any] = None
```

#### Key Calculations:

```python
class MetricsCalculator:
    """Калькулятор performance metrics."""
    
    def calculate_sharpe_ratio(
        self,
        returns: np.ndarray,
        risk_free_rate: Decimal = Decimal("0.02"),
    ) -> Decimal:
        """
        Sharpe Ratio = (Mean Return - Risk Free Rate) / Std Dev
        """
        if len(returns) < 2:
            return Decimal("0")
        
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        
        if std_return == 0:
            return Decimal("0")
        
        # Annualized
        excess_return = mean_return - (float(risk_free_rate) / 365)
        sharpe = (excess_return / std_return) * np.sqrt(365)
        
        return Decimal(str(round(sharpe, 4)))
    
    def calculate_sortino_ratio(
        self,
        returns: np.ndarray,
        risk_free_rate: Decimal = Decimal("0.02"),
    ) -> Decimal:
        """
        Sortino Ratio = (Mean Return - Risk Free) / Downside Deviation
        
        Like Sharpe но использует только downside volatility.
        """
        if len(returns) < 2:
            return Decimal("0")
        
        mean_return = np.mean(returns)
        
        # Downside deviation (только negative returns)
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return Decimal("999")  # No downside = infinite Sortino
        
        downside_std = np.std(downside_returns, ddof=1)
        
        if downside_std == 0:
            return Decimal("0")
        
        # Annualized
        excess_return = mean_return - (float(risk_free_rate) / 365)
        sortino = (excess_return / downside_std) * np.sqrt(365)
        
        return Decimal(str(round(sortino, 4)))
    
    def calculate_max_drawdown(
        self,
        equity_curve: np.ndarray,
    ) -> tuple[Decimal, int, Optional[int]]:
        """
        Рассчитать maximum drawdown.
        
        Возвращает:
            (max_dd_percent, dd_duration_days, recovery_days)
        """
        if len(equity_curve) < 2:
            return Decimal("0"), 0, None
        
        # Running maximum
        running_max = np.maximum.accumulate(equity_curve)
        
        # Drawdown at each point
        drawdown = (equity_curve - running_max) / running_max
        
        # Max drawdown
        max_dd = abs(np.min(drawdown))
        max_dd_percent = Decimal(str(round(max_dd * 100, 4)))
        
        # Duration (от peak до trough)
        max_dd_idx = np.argmin(drawdown)
        peak_idx = np.argmax(equity_curve[:max_dd_idx + 1])
        dd_duration = max_dd_idx - peak_idx
        
        # Recovery time (от trough до recovery)
        peak_value = equity_curve[peak_idx]
        recovery_idx = None
        
        for i in range(max_dd_idx, len(equity_curve)):
            if equity_curve[i] >= peak_value:
                recovery_idx = i
                break
        
        if recovery_idx:
            recovery_days = recovery_idx - max_dd_idx
        else:
            recovery_days = None  # Still underwater
        
        return max_dd_percent, dd_duration, recovery_days
    
    def calculate_profit_factor(
        self,
        positions: List[Position],
    ) -> Decimal:
        """
        Profit Factor = Gross Profit / Gross Loss
        
        > 2.0: Excellent
        1.5-2.0: Good
        1.0-1.5: Marginal
        < 1.0: Losing
        """
        gross_profit = sum(
            p.realized_pnl_usd
            for p in positions
            if p.realized_pnl_usd > 0
        )
        
        gross_loss = abs(sum(
            p.realized_pnl_usd
            for p in positions
            if p.realized_pnl_usd < 0
        ))
        
        if gross_loss == 0:
            return Decimal("999") if gross_profit > 0 else Decimal("0")
        
        return gross_profit / gross_loss
    
    def calculate_r_multiple(
        self,
        position: Position,
    ) -> Decimal:
        """
        R-Multiple = Actual Profit / Initial Risk
        
        Initial Risk = entry_price - stop_loss
        
        Example:
        Entry: $50,000, Stop: $49,000, Exit: $51,000
        Risk: $1,000
        Profit: $1,000
        R = 1.0 (1R profit)
        """
        if not position.stop_loss:
            return Decimal("0")
        
        if position.direction == PositionDirection.LONG:
            initial_risk = position.entry_price - position.stop_loss
        else:
            initial_risk = position.stop_loss - position.entry_price
        
        if initial_risk <= 0:
            return Decimal("0")
        
        r_multiple = position.realized_pnl_usd / (initial_risk * position.quantity)
        
        return Decimal(str(round(r_multiple, 2)))
```

### Sequence Diagram:

```
[Scheduler] ──daily @ 00:00──> [Performance Analytics]
                                        |
                            [Fetch Closed Positions]
                            last 24 hours
                                        |
                            [Fetch Equity Curve]
                            last 30 days
                                        |
                            ┌───────────┼───────────┐
                            v           v           v
                    [Calculate]  [Calculate]  [Calculate]
                    Returns      Risk-Adj     Trade Stats
                    Sharpe       Sortino      Win Rate
                                        |
                                        v
                            [Store Metrics]
                            PostgreSQL
                                        |
                            ┌───────────┼───────────┐
                            v                       v
                    [Generate Report]       [Update Prometheus]
                    HTML email              current_sharpe_ratio
                    Telegram summary
                                        |
                                        v
                            [Send Notifications]
                            Email + Telegram
```

### Обработка ошибок:

#### 1. Insufficient data:

```python
class PerformanceAnalytics:
    async def calculate_metrics(
        self,
        period_start: date,
        period_end: date,
        strategy: Optional[str] = None,
    ) -> Optional[PerformanceMetrics]:
        """Calculate с проверкой достаточно ли данных."""
        
        # Fetch positions
        positions = await self.portfolio.get_closed_positions(
            start_date=period_start,
            end_date=period_end,
            strategy=strategy,
        )
        
        # Check minimum trades
        if len(positions) < 10:
            logger.warning(
                "⚠️  Недостаточно сделок для расчета метрик",
                trades=len(positions),
                min_required=10,
                period=f"{period_start} - {period_end}",
            )
            return None
        
        # Fetch equity curve
        equity = await self.portfolio.get_equity_history(
            start_date=period_start,
            end_date=period_end,
        )
        
        if len(equity) < 7:  # Минимум неделя
            logger.warning(
                "⚠️  Недостаточно данных equity curve",
                days=len(equity),
                min_required=7,
            )
            return None
        
        # Proceed с расчетом
        # ...
```

#### 2. Strategy comparison:

```python
class PerformanceAnalytics:
    async def compare_strategies(
        self,
        period_start: date,
        period_end: date,
    ) -> Dict[str, PerformanceMetrics]:
        """
        Сравнить производительность по стратегиям.
        """
        strategies = await self.portfolio.get_active_strategies()
        
        comparison = {}
        
        for strategy in strategies:
            metrics = await self.calculate_metrics(
                period_start=period_start,
                period_end=period_end,
                strategy=strategy,
            )
            
            if metrics:
                comparison[strategy] = metrics
        
        # Sort по Sharpe ratio
        sorted_strategies = sorted(
            comparison.items(),
            key=lambda x: x[1].sharpe_ratio,
            reverse=True,
        )
        
        logger.info(
            "📊 Strategy comparison",
            period=f"{period_start} - {period_end}",
            best_strategy=sorted_strategies[0][0] if sorted_strategies else None,
            best_sharpe=sorted_strategies[0][1].sharpe_ratio if sorted_strategies else None,
        )
        
        return dict(sorted_strategies)
```

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 15

**✅ Что реализовано:**
- Classic metrics (Sharpe, Sortino, Calmar)
- Trade statistics (win rate, profit factor, R-multiple)
- Drawdown analysis (max DD, recovery time)
- Strategy comparison
- Automated reporting (daily/weekly/monthly)
- Time-series analysis

**❌ Что НЕ реализовано:**
- Monte Carlo simulations
- Advanced attribution analysis
- Factor analysis (market beta, alpha)
- Transaction cost analysis (TCA)
- Slippage modeling
- Market regime detection

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ

### Критические требования:

```
Операция                         Latency Target
────────────────────────────────────────────────────────
calculate_daily_metrics()        <10s
calculate_monthly_metrics()      <30s
generate_report()                <5s
compare_strategies()             <15s
────────────────────────────────────────────────────────
```

---

## 📊 BENCHMARK ТЕСТЫ

```python
@pytest.mark.benchmark
async def test_metrics_calculation_performance():
    """
    Acceptance: 1000 trades <10s
    """
    # Generate 1000 closed positions
    # Calculate all metrics
    # Assert duration < 10s
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── src/
│   └── analytics/
│       ├── __init__.py
│       ├── performance.py                # PerformanceAnalytics
│       ├── calculator.py                 # MetricsCalculator
│       ├── reporting.py                  # Report generation
│       └── models.py                     # PerformanceMetrics
│
└── tests/
    ├── unit/
    │   ├── test_metrics.py
    │   └── test_calculator.py
    ├── integration/
    │   └── test_performance.py
    └── benchmarks/
        └── bench_analytics.py
```

---

## ACCEPTANCE CRITERIA

### Metrics
- [ ] Sharpe ratio
- [ ] Sortino ratio
- [ ] Calmar ratio
- [ ] Max drawdown
- [ ] Win rate
- [ ] Profit factor
- [ ] R-multiple

### Reporting
- [ ] Daily reports
- [ ] Weekly reports
- [ ] Monthly reports
- [ ] Strategy comparison

### Performance
- [ ] Daily calc <10s
- [ ] Monthly calc <30s
- [ ] Report gen <5s

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 15: Performance Analytics** готова к реализации! 🚀

---

## 🆕 ДОПОЛНЕНИЯ v4.4 (SIMULATIONENGINE + MAE/MFE + EXIT ATTRIBUTION)

### 1. SIMULATIONENGINE — Replay, Stress Testing, Monte Carlo VaR

**Концепция из плана v4.4:**
SimulationEngine — детерминированное воспроизведение и стресс-тестирование.
Три функции:
1. **Replay** — точное воспроизведение исторического дня (frozen snapshots)
2. **Stress Testing** — экстремальные сценарии (FLASH_CRASH, EXCHANGE_OUTAGE, FUNDING_SPIKE, LIQUIDITY_CRISIS)
3. **Monte Carlo VaR** — оценка хвостовых рисков (10,000 iterations)

**Файл:** `src/analytics/simulation_engine.py`

```python
class SimulationEngine:
    """
    Детерминированное воспроизведение и стресс-тестирование.
    
    Replay ≠ Simulation — оба необходимы.
    """
    
    def __init__(self, config_manager, portfolio, market_data):
        self.config = config_manager
        self.portfolio = portfolio
        self.market_data = market_data
        self.snapshot_store = SnapshotStore("/var/lib/trading/snapshots")
    
    async def replay_day(
        self,
        date: str,
        config_hash: str,
        strategy_version: str,
    ) -> dict:
        """
        Точное воспроизведение исторического дня.
        
        Workflow:
        1. Загрузить frozen config (по config_hash)
        2. Загрузить frozen market snapshot (начало дня)
        3. Загрузить strategy code (по version)
        4. Replay: тик за тиком с симулированным исполнением
        5. Сравнить результаты с actual (deviation < 1%)
        
        Возвращает:
            {
              "date": "2025-01-15",
              "simulated_pnl": 1250.00,
              "actual_pnl": 1240.50,
              "deviation_pct": 0.0076,  # <1% = acceptable
              "trades_count": 5,
              "max_drawdown": 0.05,
              "sharpe": 2.35
            }
        """
        # Загрузка исторических данных
        historical_config = await self._load_historical_config(config_hash)
        market_snapshot = await self.snapshot_store.load(date, "000000")
        strategy = await self._load_strategy_version(strategy_version)
        
        # Создать изолированное окружение
        sim_state = SimulationState(
            initial_equity=market_snapshot.equity,
            universe=market_snapshot.universe,
            market_data=await self._load_intraday_data(date),
        )
        
        # Replay тик за тиком
        for tick in sim_state.market_data:
            sim_state.update(tick)
            
            signals = await strategy.generate_signals(sim_state)
            
            for signal in signals:
                approval = await sim_state.risk_engine.check(signal)
                if approval["allowed"]:
                    fill = await sim_state.simulate_execution(signal, approval)
                    sim_state.apply_fill(fill)
        
        # Сравнить с actual
        actual_results = await self._load_actual_results(date, strategy_version)
        deviation = self._calculate_deviation(sim_state.results, actual_results)
        
        return {
            "date": date,
            "simulated_pnl": sim_state.results.pnl,
            "actual_pnl": actual_results.pnl,
            "deviation_pct": deviation,
            "deviation_acceptable": deviation < 0.01,  # 1%
            "trades_count": len(sim_state.results.trades),
            "max_drawdown": sim_state.results.max_dd,
            "sharpe": sim_state.results.sharpe,
        }
    
    async def stress_test(
        self,
        strategy_code: str,
        scenarios: List[str],
    ) -> dict:
        """
        Тестирование стратегии в экстремальных сценариях.
        
        Scenarios:
        - FLASH_CRASH_2020: 50% drop за 1 час
        - EXCHANGE_COLLAPSE_FTX: потеря биржи + correlation spike
        - FUNDING_SPIKE_2021: 2% funding за 8 часов
        - LIQUIDITY_CRISIS_DEFI: spread ×10, depth -90%
        
        Возвращает:
            {
              "scenarios_tested": 4,
              "results": {
                "FLASH_CRASH_2020": {
                  "final_equity": 750000,
                  "total_return": -0.25,
                  "max_drawdown": 0.30,
                  "recovery_time": None  # still underwater
                }
              },
              "worst_scenario": ("FLASH_CRASH_2020", {...}),
              "passed_all": False  # max_dd > 0.25
            }
        """
        results = {}
        
        for scenario_name in scenarios:
            scenario = self._load_scenario(scenario_name)
            
            # Применить стресс к рыночным данным
            stressed_data = await self._apply_stress(scenario)
            
            # Симуляция
            sim_state = SimulationState(
                initial_equity=Decimal("1000000"),  # $1M
                universe=stressed_data.universe,
                market_data=stressed_data,
            )
            
            strategy = self._instantiate_strategy(strategy_code)
            
            for tick in sim_state.market_data:
                sim_state.update(tick)
                signals = await strategy.generate_signals(sim_state)
                
                for signal in signals:
                    approval = await sim_state.risk_engine.check(signal)
                    if approval["allowed"]:
                        fill = await sim_state.simulate_execution(signal, approval)
                        sim_state.apply_fill(fill)
            
            results[scenario_name] = {
                "final_equity": sim_state.results.equity,
                "total_return": (sim_state.results.equity - 1000000) / 1000000,
                "max_drawdown": sim_state.results.max_dd,
                "recovery_time": sim_state.results.recovery_time,
                "trades_count": len(sim_state.results.trades),
            }
        
        return {
            "scenarios_tested": len(scenarios),
            "results": results,
            "worst_scenario": min(results.items(), key=lambda x: x[1]["total_return"]),
            "passed_all": all(r["max_drawdown"] < 0.25 for r in results.values()),
        }
    
    async def monte_carlo_var(
        self,
        portfolio: dict,
        days: int = 30,
        iterations: int = 10000,
    ) -> dict:
        """
        Monte Carlo симуляция для оценки хвостовых рисков.
        
        Workflow:
        1. Для каждой итерации (10,000): случайные вариации параметров
        2. Симулировать forward 30 дней с этими параметрами
        3. Рассчитать VaR 95%, VaR 99%, Expected Shortfall
        4. Probability of ruin (return < -50%)
        
        Возвращает:
            {
              "iterations": 10000,
              "horizon_days": 30,
              "var_95": -0.12,  # 5-й процентиль = -12%
              "var_99": -0.25,  # 1-й процентиль = -25%
              "expected_shortfall": -0.18,  # среднее в хвосте
              "worst_10_scenarios": [-0.45, -0.42, ...],
              "probability_of_ruin": 0.0015  # 0.15% шанс ruin
            }
        """
        returns = []
        
        for i in range(iterations):
            # Случайные вариации параметров
            params = {
                "volatility_shift": random.gauss(1.0, 0.3),
                "correlation_shift": random.gauss(0.0, 0.2),
                "funding_regime": random.choice(["normal", "inverted", "spiked"]),
                "liquidity_factor": max(0.1, random.gauss(1.0, 0.4)),
            }
            
            # Симуляция с этими параметрами
            result = await self._simulate_forward(portfolio, days, params)
            returns.append(result["total_return"])
        
        # Рассчитать VaR и ES
        returns_sorted = sorted(returns)
        
        var_95 = returns_sorted[int(iterations * 0.05)]
        var_99 = returns_sorted[int(iterations * 0.01)]
        
        tail_returns = [r for r in returns if r <= var_95]
        expected_shortfall = mean(tail_returns) if tail_returns else var_95
        
        worst_10 = returns_sorted[:10]
        
        return {
            "iterations": iterations,
            "horizon_days": days,
            "var_95": var_95,
            "var_99": var_99,
            "expected_shortfall": expected_shortfall,
            "worst_10_scenarios": worst_10,
            "probability_of_ruin": sum(1 for r in returns if r < -0.5) / iterations,
        }
```

**Новые dataclasses:**

```python
@dataclass
class SimulationState:
    """Изолированное состояние симуляции."""
    initial_equity: Decimal
    universe: Set[Symbol]
    market_data: List[Tick]
    risk_engine: SimulatedRiskEngine
    results: SimulationResults
```

**Database:**

```sql
CREATE TABLE simulation_results (
    id SERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL,
    simulation_type VARCHAR(50) NOT NULL,  -- replay, stress_test, monte_carlo
    config JSONB,
    results JSONB
);
```

---

### 2. EXIT ATTRIBUTION — Анализ причин закрытия позиций

**Концепция из плана v4.4:**
Exit Attribution — почему позиция закрылась? Trailing stop? Hard stop? Take profit? Emergency?

**Обновлённый Position model:**

```python
@dataclass
class Position:
    # ... existing fields ...
    
    # ★ НОВОЕ v4.4: Exit Attribution
    exit_reason: Optional[str] = None  # "trailing_stop", "hard_stop", "take_profit", "emergency", "manual"
    mae_r: Optional[Decimal] = None    # Maximum Adverse Excursion (в R)
    mfe_r: Optional[Decimal] = None    # Maximum Favorable Excursion (в R)
```

**Exit reasons:**

- `trailing_stop` — закрылся по trailing stop (TrailingPolicy из Фазы 5)
- `hard_stop` — закрылся по hard stop-loss (начальный SL)
- `take_profit` — достиг take-profit уровня
- `emergency` — emergency close (KillSwitch / DrawdownProtection)
- `manual` — ручное закрытие оператором
- `pyramiding_stop` — закрытие всей пирамиды по trailing

**Компонент:** `src/analytics/exit_analyzer.py`

```python
class ExitAnalyzer:
    """
    Анализ причин закрытия позиций для оптимизации.
    
    Вопросы, на которые отвечает:
    - Какой % позиций закрывается trailing vs hard stop?
    - Сколько прибыли оставляем на столе (MFE - actual exit)?
    - Какой средний MAE у winning trades (normal retracement)?
    - Optimal trailing distance (чтобы не выбивало рано)?
    """
    
    async def analyze_exits(
        self,
        positions: List[Position],
    ) -> dict:
        """
        Анализ закрытий по причинам.
        
        Возвращает:
            {
              "by_reason": {
                "trailing_stop": {"count": 45, "avg_r": 2.1},
                "hard_stop": {"count": 15, "avg_r": -1.0},
                "take_profit": {"count": 20, "avg_r": 3.0}
              },
              "mae_analysis": {
                "winning_trades_avg_mae_r": -0.3,  # Нормальный retracement
                "losing_trades_avg_mae_r": -1.2
              },
              "mfe_analysis": {
                "avg_mfe_r": 2.8,
                "avg_exit_r": 2.1,
                "profit_left_on_table_r": 0.7  # MFE - exit
              },
              "trailing_optimization": {
                "current_distance": "1.5×ATR",
                "recommended_distance": "2.0×ATR",
                "reason": "29% позиций выбивает рано (MFE > exit + 1R)"
              }
            }
        """
        by_reason = defaultdict(lambda: {"count": 0, "total_r": 0})
        
        for pos in positions:
            if not pos.exit_reason:
                continue
            
            by_reason[pos.exit_reason]["count"] += 1
            
            # R-multiple от entry до exit
            r_multiple = self._calculate_r_multiple(pos)
            by_reason[pos.exit_reason]["total_r"] += r_multiple
        
        # Рассчитать averages
        for reason, stats in by_reason.items():
            if stats["count"] > 0:
                stats["avg_r"] = stats["total_r"] / stats["count"]
        
        # MAE/MFE analysis
        mae_mfe = await self._analyze_mae_mfe(positions)
        
        # Trailing optimization
        trailing_opt = await self._optimize_trailing_distance(positions)
        
        return {
            "by_reason": dict(by_reason),
            "mae_analysis": mae_mfe["mae"],
            "mfe_analysis": mae_mfe["mfe"],
            "trailing_optimization": trailing_opt,
        }
```

**Database updates:**

```sql
ALTER TABLE positions
ADD COLUMN exit_reason VARCHAR(50),
ADD COLUMN mae_r NUMERIC(10, 4),
ADD COLUMN mfe_r NUMERIC(10, 4);

CREATE INDEX idx_positions_exit_reason ON positions(exit_reason, outcome);
```

---

### 3. MAE/MFE INTEGRATION — Данные из Фазы 7

**Концепция:**
MAEMFETracker из Фазы 7 регистрирует MAE/MFE при каждом ORDER_FILLED и POSITION_CLOSED.
Performance Analytics читает эти данные и анализирует.

**Integration:**

```python
class PerformanceAnalytics:
    async def get_mae_mfe_quality_metrics(self, strategy: str, period_days: int = 30):
        """
        Получить MAE/MFE метрики качества от MAEMFETracker (Фаза 7).
        
        Возвращает:
            {
              "strategy": "donchian_breakout",
              "period_days": 30,
              "mae_avg_r": -0.35,  # Средний MAE
              "mfe_avg_r": 2.15,   # Средний MFE
              "mae_mfe_ratio": 6.1,  # MFE / |MAE| (чем больше, тем лучше)
              "exit_efficiency": 0.75,  # Actual exit / MFE (75% захватили)
            }
        """
        # Получить данные от MAEMFETracker
        mae_mfe_data = await self.indicators.mae_mfe_tracker.get_quality_metrics(
            strategy=strategy,
            period_days=period_days,
        )
        
        return mae_mfe_data
```

---

## ACCEPTANCE CRITERIA v4.4

### SimulationEngine ★ НОВОЕ
- [ ] replay_day() с deviation < 1% от actual
- [ ] stress_test() для 4 сценариев (FLASH_CRASH, EXCHANGE_OUTAGE, FUNDING_SPIKE, LIQUIDITY_CRISIS)
- [ ] monte_carlo_var() 10,000 iterations, VaR 95/99, Expected Shortfall
- [ ] Frozen snapshots (config_hash, market snapshot, strategy version)

### Exit Attribution ★ НОВОЕ
- [ ] exit_reason для каждой закрытой позиции
- [ ] MAE_r и MFE_r из MAEMFETracker (Фаза 7)
- [ ] Exit analysis по причинам (trailing, hard_stop, TP, emergency)
- [ ] Trailing optimization (recommend distance)

### MAE/MFE Integration ★ НОВОЕ
- [ ] Получить данные от MAEMFETracker (Фаза 7)
- [ ] MAE/MFE ratio analysis
- [ ] Exit efficiency (actual exit / MFE)

### Classic Metrics (существующее)
- [ ] Sharpe, Sortino, Calmar ratios
- [ ] Max drawdown, recovery time
- [ ] Win rate, profit factor, R-multiple
- [ ] Strategy comparison

---

**Version:** CRYPTOTEHNOLOG v4.4 (Фаза 15 — полная редакция)
**Dependencies:** Phases 0-14 (включая Фазу 7 MAEMFETracker)
**Next:** Phase 16 - Backtesting Engine (использует SimulationEngine для исторических тестов)
