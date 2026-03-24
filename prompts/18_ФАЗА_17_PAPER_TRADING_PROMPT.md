# AI ПРОМТ: ФАЗА 17 - PAPER TRADING

## КОНТЕКСТ

Вы — Senior Trading Systems Engineer, специализирующийся на simulation environments, real-time testing, и production validation.

**Фазы 0-16 завершены.** Доступны:
- Infrastructure, Risk, Data, Logic, Execution, Operations
- Safety, Notifications, Orchestration, Analytics
- Backtesting Engine
- Database, Logging, Metrics

**Текущая задача:** Реализовать production-ready Paper Trading System — real-time торговля с виртуальным капиталом для final validation перед live deployment.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class PaperTradingEngine:
    """
    Движок paper trading для тестирования стратегий в real-time.
    
    Особенности:
    - Real-time market data (live WebSocket)
    - Virtual portfolio (без реальных денег)
    - Simulated execution (realistic fills)
    - Full system integration (использует все компоненты)
    - Performance tracking (vs live market)
    - Risk-free validation (перед live trading)
    - Side-by-side comparison (paper vs live)
    - Automatic transition (paper → live)
    """
    
    async def start_paper_trading(
        self,
        strategy: str,
        symbols: List[str],
        initial_capital: Decimal = Decimal("100000"),
    ):
        """
        Запустить paper trading session.
        
        Аргументы:
            strategy: Имя стратегии
            symbols: Список символов
            initial_capital: Виртуальный капитал
        
        Процесс:
        1. Инициализировать virtual portfolio
        2. Subscribe на real-time market data
        3. Run trading loop (как в live):
           - Получить новый bar
           - Обновить индикаторы
           - Сгенерировать сигнал
           - Проверить risk
           - Симулировать execution
           - Обновить virtual portfolio
        4. Track performance
        5. Compare vs live market (if live running)
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.info("📝 Paper trading запущен", strategy="momentum", capital=100000, mode="PAPER")
logger.info("✅ Virtual позиция открыта", symbol="BTC/USDT", side="LONG", size=0.5, mode="PAPER")
logger.debug("Simulated fill", expected_price=50000, filled_price=50025, slippage=0.05, mode="PAPER")
logger.warning("⚠️  Paper performance отстает от live", paper_return=2.5, live_return=3.2)
```

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Paper Trading — финальная validation перед live deployment. Использует реальные market data, реальную торговую логику, но виртуальный капитал. Позволяет test систему в production conditions без риска потери денег. Выявляет проблемы execution, timing, slippage в real-time.

### Входящие зависимости:

#### 1. **Market Data Layer (Фаза 6)** → real-time bars (SAME as live)
   - Event: Подписка на `BAR_COMPLETED`
   - Data: Real-time OHLCV bars
   - Критичность: HIGH (должен быть IDENTICAL to live)

#### 2. **Strategy Manager (Фаза 14)** → strategy logic (REUSE)
   - Uses SAME strategies as live
   - Ensures consistency
   - Критичность: HIGH

#### 3. **All components** → full integration test
   - Signal Generator, Risk Engine, Portfolio Governor
   - Все компоненты работают как в live
   - Только execution симулируется
   - Критичность: HIGH

### Исходящие зависимости:

#### 1. → Virtual Portfolio (isolated)
   - **Table: `paper_trading_portfolio`**
     ```sql
     CREATE TABLE paper_trading_portfolio (
         session_id VARCHAR(50) NOT NULL,
         timestamp TIMESTAMPTZ NOT NULL,
         
         cash_balance_usd NUMERIC(20, 2),
         equity_usd NUMERIC(20, 2),
         
         open_positions JSONB,
         
         PRIMARY KEY (session_id, timestamp)
     );
     ```

   - **Table: `paper_trading_trades`**
     ```sql
     CREATE TABLE paper_trading_trades (
         trade_id SERIAL PRIMARY KEY,
         session_id VARCHAR(50) NOT NULL,
         
         opened_at TIMESTAMPTZ,
         closed_at TIMESTAMPTZ,
         
         symbol VARCHAR(20),
         direction VARCHAR(5),
         
         entry_price NUMERIC(20, 8),
         exit_price NUMERIC(20, 8),
         quantity NUMERIC(20, 8),
         
         pnl_usd NUMERIC(20, 2),
         pnl_percent NUMERIC(10, 4),
         
         simulated_slippage_percent NUMERIC(5, 4),
         simulated_commission_usd NUMERIC(20, 2)
     );
     ```

#### 2. → Notifications (Фаза 13)
   - Alert: Paper trading session started/stopped
   - Daily: Paper trading performance report
   - Channel: Telegram (summary)

#### 3. → Performance Analytics (Фаза 15)
   - Compare: Paper vs Backtest vs Live
   - Metrics: Sharpe, Win Rate, etc
   - Report: Validation report

### Контракты данных:

#### PaperTradingSession:

```python
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional

@dataclass
class PaperTradingSession:
    """Paper trading session."""
    
    session_id: str
    started_at: datetime
    stopped_at: Optional[datetime] = None
    
    strategy: str
    symbols: List[str]
    timeframe: str
    
    initial_capital: Decimal
    current_capital: Decimal
    
    # Performance
    total_return_percent: Decimal
    sharpe_ratio: Optional[Decimal] = None
    max_drawdown_percent: Decimal
    
    # Trade stats
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    
    # Status
    status: str  # "RUNNING", "STOPPED", "PAUSED"
```

#### Virtual Execution:

```python
class VirtualExecutionEngine:
    """
    Virtual execution для paper trading.
    
    Симулирует fills используя real-time market prices.
    """
    
    async def execute_virtual_order(
        self,
        signal: TradingSignal,
        current_market_price: Decimal,
        current_orderbook: Orderbook,
    ) -> VirtualFill:
        """
        Симулировать execution order в real-time.
        
        Отличие от Backtesting:
        - Используется CURRENT market price (real-time)
        - Учитывается CURRENT orderbook liquidity
        - Более реалистичный slippage (основан на реальных условиях)
        
        Slippage model:
        - Проверить orderbook depth
        - Если наш size > best bid/ask size → slippage
        - Realistic slippage 0.02-0.2% (зависит от liquidity)
        """
        # Check orderbook liquidity
        if signal.direction == SignalDirection.BUY:
            best_ask = current_orderbook.get_best_ask()
            available_liquidity = best_ask.quantity
        else:
            best_bid = current_orderbook.get_best_bid()
            available_liquidity = best_bid.quantity
        
        # Calculate quantity
        position_size_btc = signal.position_size_usd / current_market_price
        
        # Slippage based на liquidity
        if position_size_btc > available_liquidity:
            # Large order → walk the book
            slippage_percent = Decimal("0.002")  # 0.2%
        else:
            # Normal order → best price
            slippage_percent = Decimal("0.0002")  # 0.02%
        
        # Fill price
        if signal.direction == SignalDirection.BUY:
            fill_price = current_market_price * (1 + slippage_percent)
        else:
            fill_price = current_market_price * (1 - slippage_percent)
        
        # Commission
        commission = signal.position_size_usd * Decimal("0.00075")  # 0.075%
        
        return VirtualFill(
            fill_price=fill_price,
            fill_quantity=position_size_btc,
            fill_time=datetime.now(timezone.utc),
            slippage_percent=slippage_percent * 100,
            commission_usd=commission,
        )
```

### Sequence Diagram:

```
[Real-time Market] ──BAR_COMPLETED──> [Paper Trading Engine]
                                              |
                                    [SAME workflow as live]
                                              |
                            ┌─────────────────┼─────────────────┐
                            │                 │                 │
                    [Indicators]      [Signal Gen]      [Risk Engine]
                    REAL-TIME         REAL-TIME         REAL-TIME
                            │                 │                 │
                            └─────────────────┼─────────────────┘
                                              │
                                    [✅ Risk passed]
                                              │
                                    [Virtual Execution]
                                    simulate fill
                                    (NOT sent to exchange)
                                              │
                                    [Virtual Portfolio]
                                    update positions
                                    calculate P&L
                                              │
                            ┌─────────────────┼─────────────────┐
                            │                 │                 │
                    [PostgreSQL]      [Notifications]  [Analytics]
                    save trades       Telegram alert   track metrics
```

### Обработка ошибок:

#### 1. Paper vs Live comparison:

```python
class PaperTradingEngine:
    async def compare_with_live(
        self,
        paper_session_id: str,
    ) -> ComparisonReport:
        """
        Сравнить paper trading performance с live (если live running).
        
        Полезно для:
        - Detect если paper отличается от live (execution quality?)
        - Validate что система работает одинаково
        """
        # Get paper performance
        paper_metrics = await self._get_session_metrics(paper_session_id)
        
        # Get live performance (same period)
        live_metrics = await self.performance_analytics.calculate_metrics(
            period_start=paper_metrics.started_at.date(),
            period_end=datetime.now(timezone.utc).date(),
            strategy=paper_metrics.strategy,
        )
        
        if not live_metrics:
            logger.info("Live trading не запущен, пропускаем сравнение")
            return None
        
        # Compare
        return_diff = paper_metrics.total_return_percent - live_metrics.total_return_percent
        sharpe_diff = paper_metrics.sharpe_ratio - live_metrics.sharpe_ratio
        
        if abs(return_diff) > 5:  # > 5% difference
            logger.warning(
                "⚠️  Значительное расхождение paper vs live",
                paper_return=paper_metrics.total_return_percent,
                live_return=live_metrics.total_return_percent,
                diff=return_diff,
            )
        
        return ComparisonReport(
            paper_metrics=paper_metrics,
            live_metrics=live_metrics,
            return_diff=return_diff,
            sharpe_diff=sharpe_diff,
        )
```

#### 2. Automatic graduation (paper → live):

```python
class PaperTradingEngine:
    async def check_graduation_criteria(
        self,
        session_id: str,
    ) -> bool:
        """
        Проверить готов ли strategy для live trading.
        
        Graduation criteria:
        - Paper trading duration >= 30 days
        - Sharpe ratio >= 1.5
        - Win rate >= 50%
        - Max drawdown <= 15%
        - Consistency (no large losses)
        """
        metrics = await self._get_session_metrics(session_id)
        
        # Duration check
        duration_days = (datetime.now(timezone.utc) - metrics.started_at).days
        if duration_days < 30:
            logger.info(
                "📝 Paper trading еще не готов (duration)",
                current_days=duration_days,
                required_days=30,
            )
            return False
        
        # Performance checks
        criteria = {
            "sharpe_ratio": metrics.sharpe_ratio >= Decimal("1.5"),
            "win_rate": metrics.win_rate >= Decimal("0.5"),
            "max_drawdown": metrics.max_drawdown_percent <= Decimal("15"),
        }
        
        passed = all(criteria.values())
        
        if passed:
            logger.info(
                "✅ Paper trading ГОТОВ к live deployment!",
                duration_days=duration_days,
                sharpe=metrics.sharpe_ratio,
                win_rate=metrics.win_rate,
                max_dd=metrics.max_drawdown_percent,
            )
            
            # Уведомить операторов
            await self.notifications.send_notification(
                message=f"🎉 Strategy '{metrics.strategy}' готов к live trading!\n\n"
                        f"Duration: {duration_days} days\n"
                        f"Sharpe: {metrics.sharpe_ratio}\n"
                        f"Win rate: {metrics.win_rate * 100}%\n"
                        f"Max DD: {metrics.max_drawdown_percent}%",
                severity=NotificationSeverity.INFO,
                channels=[NotificationChannel.TELEGRAM, NotificationChannel.EMAIL],
            )
        else:
            failed_criteria = [k for k, v in criteria.items() if not v]
            logger.info(
                "📝 Paper trading еще не готов (performance)",
                failed_criteria=failed_criteria,
                current_metrics=metrics,
            )
        
        return passed
```

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 17

**✅ Что реализовано:**
- Real-time market data integration
- Virtual portfolio management
- Simulated execution (realistic slippage)
- Full system integration test
- Performance tracking
- Paper vs Live comparison
- Automatic graduation criteria

**❌ Что НЕ реализовано:**
- Real exchange connectivity (only simulation)
- Real slippage (estimated, not actual)
- Real latency (может отличаться от live)
- Market impact (от наших ордеров в live)

**⚠️ ВАЖНО:**
```markdown
Paper Trading максимально близок к live, НО:
- Slippage simulated (не actual exchange fills)
- No real latency (WebSocket vs exchange API)
- No market impact (в live наши ордера влияют на цену)
- No psychological pressure (виртуальные деньги)

Paper Trading — отличный test, но NOT perfect predictor of live.
Всегда начинать live с малым капиталом.
```

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ

### Критические требования:

```
Операция                         Latency Target
────────────────────────────────────────────────────────
virtual_execution()              <100ms (same as live)
portfolio_update()               <50ms
performance_calculation()        <5s (daily)
comparison_report()              <10s
────────────────────────────────────────────────────────
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── src/
│   └── paper_trading/
│       ├── __init__.py
│       ├── engine.py                     # PaperTradingEngine
│       ├── virtual_execution.py          # VirtualExecutionEngine
│       ├── virtual_portfolio.py          # VirtualPortfolio
│       ├── comparison.py                 # Paper vs Live comparison
│       └── models.py                     # PaperTradingSession
│
└── tests/
    ├── unit/
    │   └── test_virtual_execution.py
    ├── integration/
    │   └── test_paper_trading.py
    └── benchmarks/
        └── bench_paper_trading.py
```

---

## ACCEPTANCE CRITERIA

### Core Features
- [ ] Real-time market data integration
- [ ] Virtual portfolio management
- [ ] Simulated execution (realistic)
- [ ] Performance tracking

### Validation
- [ ] Paper vs Live comparison
- [ ] Graduation criteria check
- [ ] Automatic alerts

### Integration
- [ ] SAME workflow as live
- [ ] SAME strategy logic
- [ ] SAME risk checks

### Reporting
- [ ] Daily performance reports
- [ ] Trade statistics
- [ ] Comparison with backtest/live

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 17: Paper Trading** готова к реализации! 🚀
