# AI ПРОМТ: ФАЗА 16 - BACKTESTING ENGINE

## КОНТЕКСТ

Вы — Senior Quantitative Developer, специализирующийся на backtesting frameworks, historical data analysis, и strategy validation.

**Фазы 0-15 завершены.** Доступны:
- Infrastructure (Event Bus, State Machine, Config)
- Risk Engine, Market Data, Technical Indicators
- Signal Generator, Portfolio Governor
- Execution Layer, Order Management System
- Kill Switch, Notifications
- Strategy Manager, Performance Analytics
- Database, Logging, Metrics

**Текущая задача:** Реализовать production-ready Backtesting Engine с historical simulation, realistic execution modeling, comprehensive statistics, и strategy optimization capabilities.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class BacktestEngine:
    """
    Движок бэктестинга для валидации торговых стратегий.
    
    Особенности:
    - Historical data replay (bar-by-bar simulation)
    - Realistic execution modeling (slippage, commission, latency)
    - Portfolio simulation (позиции, P&L, drawdown)
    - Multiple timeframe support (1m, 5m, 15m, 1h, 4h, 1d)
    - Walk-forward optimization (избежать overfitting)
    - Monte Carlo simulation (stress testing)
    - Comprehensive statistics (Sharpe, Win Rate, Max DD)
    - Comparison reports (strategy vs benchmark)
    """
    
    async def run_backtest(
        self,
        strategy: str,
        symbols: List[str],
        start_date: date,
        end_date: date,
        initial_capital: Decimal = Decimal("100000"),
    ) -> BacktestResult:
        """
        Запустить бэктест стратегии на исторических данных.
        
        Аргументы:
            strategy: Имя стратегии (e.g. "momentum")
            symbols: Список символов (e.g. ["BTC/USDT", "ETH/USDT"])
            start_date: Дата начала
            end_date: Дата окончания
            initial_capital: Начальный капитал
        
        Процесс:
        1. Загрузить historical OHLCV данные
        2. Инициализировать симулированный портфель
        3. Для каждого бара (bar-by-bar):
           a. Обновить индикаторы
           b. Сгенерировать сигнал
           c. Симулировать execution (с slippage/commission)
           d. Обновить портфель
           e. Рассчитать P&L
        4. Рассчитать финальные метрики
        5. Сгенерировать отчет
        
        Возвращает:
            BacktestResult с метриками, trades, equity curve
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.info("🔄 Бэктест запущен", strategy="momentum", period="2023-01-01 to 2024-01-01")
logger.debug("Bar processed", date="2023-06-15", close=50000, signals_generated=1)
logger.info("✅ Бэктест завершен", total_trades=150, final_equity=125000, duration_sec=45)
logger.warning("⚠️  High slippage detected", avg_slippage_percent=1.5, threshold=1.0)
```

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Backtesting Engine — валидация стратегий перед live trading. Симулирует торговлю на исторических данных, реалистично моделирует execution (slippage, commission), рассчитывает performance metrics, помогает optimize parameters, и предотвращает overfitting через walk-forward analysis.

### Входящие зависимости:

#### 1. **Historical Data Storage** → OHLCV bars
   - Query: `get_historical_bars(symbol, timeframe, start, end)`
   - Source: TimescaleDB (из Фазы 6)
   - Data: OHLCV bars для replay
   - Критичность: HIGH

#### 2. **Signal Generator (Фаза 8)** → strategy logic (reuse)
   - Использует ту же logic что и live trading
   - Ensures consistency между backtest и live
   - Критичность: HIGH

#### 3. **Technical Indicators (Фаза 7)** → indicator calculations (reuse)
   - Reuse existing indicator library
   - Критичность: HIGH

#### 4. **Risk Engine (Фаза 5)** → position sizing (reuse)
   - Same R-unit sizing logic
   - Критичность: MEDIUM

### Исходящие зависимости:

#### 1. → PostgreSQL (backtest results)
   - **Table: `backtest_runs`**
     ```sql
     CREATE TABLE backtest_runs (
         run_id SERIAL PRIMARY KEY,
         started_at TIMESTAMPTZ NOT NULL,
         completed_at TIMESTAMPTZ,
         
         strategy VARCHAR(50) NOT NULL,
         symbols VARCHAR(20)[] NOT NULL,
         timeframe VARCHAR(5) NOT NULL,
         
         period_start DATE NOT NULL,
         period_end DATE NOT NULL,
         
         initial_capital NUMERIC(20, 2),
         final_capital NUMERIC(20, 2),
         
         -- Performance metrics
         total_return_percent NUMERIC(10, 4),
         sharpe_ratio NUMERIC(10, 4),
         max_drawdown_percent NUMERIC(10, 4),
         win_rate NUMERIC(5, 4),
         profit_factor NUMERIC(10, 4),
         
         total_trades INTEGER,
         winning_trades INTEGER,
         losing_trades INTEGER,
         
         -- Execution quality
         avg_slippage_percent NUMERIC(5, 4),
         total_commission_usd NUMERIC(20, 2),
         
         metadata JSONB
     );
     ```

   - **Table: `backtest_trades`**
     ```sql
     CREATE TABLE backtest_trades (
         trade_id SERIAL PRIMARY KEY,
         run_id INTEGER REFERENCES backtest_runs(run_id),
         
         opened_at TIMESTAMPTZ NOT NULL,
         closed_at TIMESTAMPTZ,
         
         symbol VARCHAR(20) NOT NULL,
         direction VARCHAR(5) NOT NULL,
         
         entry_price NUMERIC(20, 8),
         exit_price NUMERIC(20, 8),
         quantity NUMERIC(20, 8),
         
         pnl_usd NUMERIC(20, 2),
         pnl_percent NUMERIC(10, 4),
         
         holding_time_hours INTEGER,
         
         slippage_percent NUMERIC(5, 4),
         commission_usd NUMERIC(20, 2)
     );
     ```

#### 2. → Notifications (Фаза 13)
   - Report: Backtest completion notification
   - Channel: Email (detailed report), Telegram (summary)

#### 3. → Performance Analytics (Фаза 15)
   - Reuse metrics calculator
   - Compare backtest vs live performance

### Контракты данных:

#### BacktestResult:

```python
from dataclasses import dataclass
from decimal import Decimal
from datetime import date, datetime
from typing import List, Dict, Any

@dataclass
class BacktestResult:
    """Результат бэктеста."""
    
    run_id: int
    started_at: datetime
    completed_at: datetime
    
    # Configuration
    strategy: str
    symbols: List[str]
    timeframe: str
    period_start: date
    period_end: date
    
    # Capital
    initial_capital: Decimal
    final_capital: Decimal
    
    # Performance metrics
    total_return_percent: Decimal
    annualized_return_percent: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    max_drawdown_percent: Decimal
    
    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    profit_factor: Decimal
    average_win_usd: Decimal
    average_loss_usd: Decimal
    
    # Execution quality
    avg_slippage_percent: Decimal
    total_commission_usd: Decimal
    
    # Detailed data
    trades: List[Dict]  # List of trade details
    equity_curve: List[tuple[date, Decimal]]  # Daily equity
    
    # Metadata
    metadata: Dict[str, Any] = None
```

#### Execution Simulator:

```python
class ExecutionSimulator:
    """
    Симулятор реалистичного исполнения ордеров.
    
    Моделирует:
    - Slippage (зависит от volatility и orderbook liquidity)
    - Commission (maker/taker fees)
    - Latency (задержка между signal и execution)
    - Partial fills (для больших ордеров)
    """
    
    def simulate_market_order(
        self,
        signal: TradingSignal,
        current_bar: OHLCVBar,
        position_size_usd: Decimal,
    ) -> SimulatedExecution:
        """
        Симулировать market order execution.
        
        Slippage model:
        - Базовый slippage: 0.05% (normal conditions)
        - + Volatility adjustment: ATR/price * 0.5
        - + Size impact: если size > 1% of volume → дополнительный slippage
        
        Commission:
        - Taker fee: 0.075% (typical для Bybit/Binance)
        """
        # Base slippage
        base_slippage = Decimal("0.0005")  # 0.05%
        
        # Volatility adjustment (используем ATR)
        atr = self._calculate_atr(current_bar)
        volatility_slippage = (atr / current_bar.close) * Decimal("0.5")
        
        # Size impact
        size_impact = self._calculate_size_impact(
            position_size_usd,
            current_bar.volume * current_bar.close,
        )
        
        # Total slippage
        total_slippage = base_slippage + volatility_slippage + size_impact
        
        # Fill price (с учетом slippage)
        if signal.direction == SignalDirection.BUY:
            fill_price = signal.entry_price * (1 + total_slippage)
        else:
            fill_price = signal.entry_price * (1 - total_slippage)
        
        # Commission
        commission = position_size_usd * Decimal("0.00075")  # 0.075%
        
        return SimulatedExecution(
            fill_price=fill_price,
            slippage_percent=total_slippage * 100,
            commission_usd=commission,
            filled_at=current_bar.close_time,
        )
    
    def _calculate_size_impact(
        self,
        order_size_usd: Decimal,
        bar_volume_usd: Decimal,
    ) -> Decimal:
        """
        Рассчитать market impact от размера ордера.
        
        Если ордер > 1% от volume бара → дополнительный slippage.
        """
        if bar_volume_usd == 0:
            return Decimal("0.01")  # 1% slippage если нет volume data
        
        size_ratio = order_size_usd / bar_volume_usd
        
        if size_ratio > Decimal("0.01"):  # > 1% of volume
            # Square root impact model
            return (size_ratio ** Decimal("0.5")) * Decimal("0.1")
        
        return Decimal("0")
```

### Sequence Diagram:

```
[User] ──run_backtest()──> [Backtesting Engine]
                                    |
                        [Load Historical Data]
                        TimescaleDB query
                        2023-01-01 to 2024-01-01
                                    |
                        [Initialize Simulated Portfolio]
                        capital = $100,000
                                    |
                        [Bar-by-Bar Loop]
                                    |
                    ┌───────────────┴───────────────┐
                    │ For each bar:                 │
                    │                               │
                    │ 1. Update Indicators          │
                    │    RSI, MACD, Bollinger       │
                    │                               │
                    │ 2. Generate Signal            │
                    │    (reuse Signal Generator)   │
                    │                               │
                    │ 3. Check Risk                 │
                    │    (reuse Risk Engine)        │
                    │                               │
                    │ 4. Simulate Execution         │
                    │    slippage + commission      │
                    │                               │
                    │ 5. Update Portfolio           │
                    │    positions, equity, P&L     │
                    │                               │
                    └───────────────┬───────────────┘
                                    |
                        [Calculate Final Metrics]
                        Sharpe, Win Rate, Max DD
                                    |
                        [Generate Report]
                        HTML + charts
                                    |
                    ┌───────────────┴───────────────┐
                    │                               │
                    v                               v
            [Save to DB]                    [Send Notification]
            backtest_runs                   Email + Telegram
```

### Обработка ошибок:

#### 1. Missing historical data:

```python
class BacktestEngine:
    async def _load_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: date,
        end_date: date,
    ) -> List[OHLCVBar]:
        """Load с проверкой completeness."""
        
        bars = await self.database.query(
            """
            SELECT * FROM ohlcv_bars
            WHERE symbol = $1 AND timeframe = $2
              AND time >= $3 AND time <= $4
            ORDER BY time ASC
            """,
            symbol, timeframe, start_date, end_date,
        )
        
        if not bars:
            raise BacktestError(
                f"No historical data found for {symbol} {timeframe} "
                f"between {start_date} and {end_date}"
            )
        
        # Check для gaps
        expected_bars = self._calculate_expected_bars(
            start_date,
            end_date,
            timeframe,
        )
        
        gap_percent = (expected_bars - len(bars)) / expected_bars * 100
        
        if gap_percent > 10:  # > 10% missing
            logger.warning(
                "⚠️  Значительные пропуски в данных",
                symbol=symbol,
                timeframe=timeframe,
                expected=expected_bars,
                actual=len(bars),
                gap_percent=gap_percent,
            )
        
        return bars
```

#### 2. Walk-forward optimization:

```python
class BacktestEngine:
    async def walk_forward_optimization(
        self,
        strategy: str,
        symbol: str,
        full_period_start: date,
        full_period_end: date,
        in_sample_days: int = 90,
        out_sample_days: int = 30,
    ) -> WalkForwardResult:
        """
        Walk-forward optimization для избежания overfitting.
        
        Процесс:
        1. Разбить период на windows (in-sample + out-sample)
        2. Для каждого window:
           a. Optimize parameters на in-sample
           b. Test на out-sample
        3. Aggregate results
        
        Example:
        Full period: 2023-01-01 to 2023-12-31
        
        Window 1:
        - In-sample: 2023-01-01 to 2023-03-31 (90 days) → optimize
        - Out-sample: 2023-04-01 to 2023-04-30 (30 days) → test
        
        Window 2:
        - In-sample: 2023-02-01 to 2023-04-30 (90 days) → optimize
        - Out-sample: 2023-05-01 to 2023-05-30 (30 days) → test
        
        ...
        """
        windows = self._generate_walk_forward_windows(
            full_period_start,
            full_period_end,
            in_sample_days,
            out_sample_days,
        )
        
        results = []
        
        for window in windows:
            # Optimize на in-sample
            best_params = await self._optimize_parameters(
                strategy=strategy,
                symbol=symbol,
                start_date=window.in_sample_start,
                end_date=window.in_sample_end,
            )
            
            # Test на out-sample (с optimized params)
            out_sample_result = await self.run_backtest(
                strategy=strategy,
                symbols=[symbol],
                start_date=window.out_sample_start,
                end_date=window.out_sample_end,
                params=best_params,  # Используем optimized
            )
            
            results.append({
                "window": window,
                "best_params": best_params,
                "out_sample_sharpe": out_sample_result.sharpe_ratio,
                "out_sample_return": out_sample_result.total_return_percent,
            })
        
        # Aggregate
        avg_out_sample_sharpe = np.mean([r["out_sample_sharpe"] for r in results])
        
        logger.info(
            "✅ Walk-forward optimization завершена",
            windows=len(windows),
            avg_out_sample_sharpe=avg_out_sample_sharpe,
        )
        
        return WalkForwardResult(
            windows=results,
            avg_sharpe=avg_out_sample_sharpe,
        )
```

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 16

**✅ Что реализовано:**
- Bar-by-bar simulation
- Realistic execution modeling (slippage, commission)
- Portfolio simulation (позиции, P&L)
- Comprehensive metrics (Sharpe, Win Rate, Max DD)
- Walk-forward optimization
- Strategy comparison

**❌ Что НЕ реализовано:**
- Tick-by-tick simulation (только bar-level)
- Orderbook replay (для limit order simulation)
- Multiple asset correlation во время backtest
- Transaction cost analysis (TCA) детализация
- Monte Carlo path generation
- Market regime detection

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ

### Критические требования:

```
Операция                         Latency Target
────────────────────────────────────────────────────────
backtest_1_year_1_symbol()       <60s
backtest_5_years_multi_symbol()  <300s (5 min)
walk_forward_optimization()      <600s (10 min)
────────────────────────────────────────────────────────
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── src/
│   └── backtesting/
│       ├── __init__.py
│       ├── engine.py                     # BacktestEngine
│       ├── simulator.py                  # ExecutionSimulator
│       ├── portfolio.py                  # SimulatedPortfolio
│       ├── optimization.py               # Walk-forward, parameter optimization
│       └── models.py                     # BacktestResult
│
└── tests/
    ├── unit/
    │   ├── test_engine.py
    │   └── test_simulator.py
    ├── integration/
    │   └── test_backtest_full.py
    └── benchmarks/
        └── bench_backtest.py
```

---

## ACCEPTANCE CRITERIA

### Core Features
- [ ] Bar-by-bar simulation
- [ ] Realistic slippage modeling
- [ ] Commission calculation
- [ ] Portfolio tracking
- [ ] Metrics calculation

### Optimization
- [ ] Walk-forward optimization
- [ ] Parameter grid search
- [ ] Out-of-sample testing

### Reporting
- [ ] Comprehensive statistics
- [ ] Equity curve chart
- [ ] Trade list
- [ ] Comparison vs benchmark

### Performance
- [ ] 1 year backtest <60s
- [ ] Multi-symbol support
- [ ] Parallel execution

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 16: Backtesting Engine** готова к реализации! 🚀
