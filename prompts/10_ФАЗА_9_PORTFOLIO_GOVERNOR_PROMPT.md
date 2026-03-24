# AI ПРОМТ: ФАЗА 9 - PORTFOLIO GOVERNOR

## КОНТЕКСТ

Вы — Senior Portfolio Manager, специализирующийся на position management, portfolio optimization, и real-time P&L tracking.

**Фазы 0-8 завершены.** Доступны:
- Event Bus (Rust + Python) — работает с persistence
- Control Plane (State Machine, Watchdog) — работает
- Config Manager — hot reload, GPG signatures, Vault
- Risk Engine — R-unit sizing, correlation, drawdown
- Market Data Layer — WebSocket, ticks, OHLCV bars, orderbook
- Technical Indicators — 20+ индикаторов, NumPy vectorization
- Signal Generator — торговые стратегии, confidence scoring
- Database Layer, Logging, Metrics — готовы

**Текущая задача:** Реализовать production-ready Portfolio Governor с position tracking, real-time P&L calculation, exposure monitoring, correlation checks, и portfolio optimization.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class PortfolioGovernor:
    """
    Управляющий портфелем с real-time отслеживанием позиций.
    
    Особенности:
    - Real-time position tracking (открытие, изменение, закрытие)
    - Mark-to-market P&L calculation (обновление при каждом тике)
    - Exposure monitoring (total, per-symbol, per-strategy)
    - Correlation checks (избежать overconcentration)
    - Portfolio limits enforcement (max positions, max exposure)
    - Position lifecycle management (entry → active → closed)
    - Performance analytics (win rate, average R, Sharpe ratio)
    """
    
    async def open_position(
        self,
        signal: TradingSignal,
        executed_price: Decimal,
        quantity: Decimal,
    ) -> Position:
        """
        Открыть новую позицию.
        
        Аргументы:
            signal: Торговый сигнал (откуда взялась позиция)
            executed_price: Фактическая цена исполнения
            quantity: Количество (в базовой валюте)
        
        Возвращает:
            Position объект
        
        Действия:
        1. Создать Position объект
        2. Добавить в active positions
        3. Обновить portfolio exposure
        4. Проверить portfolio limits
        5. Сохранить в БД
        6. Публиковать POSITION_OPENED event
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.info("Позиция открыта", position_id="pos_123", symbol="BTC/USDT", size_usd=10000)
logger.warning("Превышен лимит exposure", current=0.85, max=0.80)
logger.error("Не удалось открыть позицию", reason="max_positions_reached", max=10, current=10)
logger.debug("P&L обновлен", position_id="pos_123", unrealized_pnl=150.50)
```

### Примеры замены:

| ❌ Неправильно | ✅ Правильно |
|----------------|--------------|
| "Position opened" | "Позиция открыта" |
| "Exposure limit exceeded" | "Превышен лимит exposure" |
| "P&L updated" | "P&L обновлен" |
| "Correlation too high" | "Корреляция слишком высокая" |
| "Portfolio rebalanced" | "Портфель ребалансирован" |

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Portfolio Governor — центральный регистр всех открытых позиций. Отслеживает что, сколько, и когда куплено/продано. Рассчитывает P&L в real-time. Проверяет лимиты (max positions, max exposure, correlation). Предоставляет analytics (win rate, avg profit, Sharpe ratio). Все execution проходят через Portfolio Governor для validation и tracking.

### Входящие зависимости (кто взаимодействует):

#### 1. **Strategy Manager (Фаза 14)** → открытие/закрытие позиций
   - Запрос: `async def open_position(signal, exec_price, quantity) -> Position`
   - Частота: 5-20 раз/день (зависит от стратегий)
   - Действие: Strategy Manager получил filled order → регистрирует позицию
   - Timeout: 100ms
   - Критичность: HIGH (без tracking позиций система слепа)

#### 2. **Risk Engine (Фаза 5)** → проверка exposure перед сделкой
   - Запрос: `async def check_can_open(symbol, size_usd) -> bool`
   - Частота: при каждом сигнале (10-50 раз/час)
   - Действие: Risk Engine проверяет можно ли открыть еще одну позицию
   - Критичность: HIGH (предотвращение overexposure)

#### 3. **Market Data Layer (Фаза 6)** → подписка на TICK_RECEIVED
   - Event: Подписка на `TICK_RECEIVED` для mark-to-market
   - Частота: 10-100 ticks/сек
   - Payload: `{"symbol": "BTC/USDT", "price": 50050}`
   - Действие: Portfolio обновляет unrealized P&L для открытых позиций
   - Критичность: HIGH (real-time P&L tracking)

#### 4. **Execution Layer (Фаза 10)** → уведомления об исполнении
   - Event: Подписка на `ORDER_FILLED`
   - Частота: при каждом fill (5-20 раз/день)
   - Payload: `{"order_id": "...", "filled_price": 50000, "filled_qty": 0.5}`
   - Действие: Portfolio регистрирует открытие/закрытие позиции
   - Критичность: HIGH

#### 5. **Config Manager (Фаза 4)** → hot reload limits
   - Event: `CONFIG_UPDATED` (изменение portfolio limits)
   - Частота: редко
   - Payload: `{"portfolio.max_positions": {"old": 10, "new": 15}}`
   - Действие: Portfolio обновляет лимиты
   - Критичность: MEDIUM

### Исходящие зависимости (что публикует Portfolio Governor):

#### 1. → Event Bus (Фаза 3)
   - **Event: `POSITION_OPENED`** (приоритет: HIGH)
     - Payload:
       ```json
       {
         "position_id": "pos_uuid",
         "symbol": "BTC/USDT",
         "direction": "LONG",
         "entry_price": 50000,
         "quantity": 0.5,
         "size_usd": 25000,
         "stop_loss": 49500,
         "take_profit": 51000,
         "strategy": "momentum",
         "signal_id": "sig_uuid",
         "timestamp": 1704067200000000
       }
       ```
     - Подписчики: Observability, Telegram alerts

   - **Event: `POSITION_CLOSED`** (приоритет: HIGH)
     - Payload: `{"position_id": "...", "exit_price": 50500, "pnl_usd": 250, "pnl_percent": 1.0, "outcome": "WIN"}`
     - Подписчики: Analytics, Telegram

   - **Event: `EXPOSURE_LIMIT_EXCEEDED`** (приоритет: CRITICAL)
     - Payload: `{"current_exposure": 0.85, "max_exposure": 0.80, "action": "reject_new_positions"}`
     - Подписчики: Risk Engine, State Machine

   - **Event: `PORTFOLIO_REBALANCED`** (приоритет: NORMAL)
     - Payload: `{"action": "reduce_correlation", "closed_positions": [...], "reason": "correlation_too_high"}`

#### 2. → PostgreSQL (для position history)
   - **Table: `positions`**
     ```sql
     CREATE TABLE positions (
         position_id VARCHAR(50) PRIMARY KEY,
         opened_at TIMESTAMPTZ NOT NULL,
         closed_at TIMESTAMPTZ,
         
         symbol VARCHAR(20) NOT NULL,
         direction VARCHAR(5) NOT NULL,  -- LONG, SHORT
         
         entry_price NUMERIC(20, 8) NOT NULL,
         exit_price NUMERIC(20, 8),
         quantity NUMERIC(20, 8) NOT NULL,
         size_usd NUMERIC(20, 2) NOT NULL,
         
         stop_loss NUMERIC(20, 8),
         take_profit NUMERIC(20, 8),
         
         strategy VARCHAR(50),
         signal_id VARCHAR(50),
         
         status VARCHAR(20) DEFAULT 'OPEN',  -- OPEN, CLOSED
         
         realized_pnl_usd NUMERIC(20, 2),
         realized_pnl_percent NUMERIC(10, 4),
         
         outcome VARCHAR(20),  -- WIN, LOSS, BREAKEVEN
         holding_time_seconds INTEGER,
         
         metadata JSONB
     );
     
     CREATE INDEX idx_positions_opened ON positions(opened_at DESC);
     CREATE INDEX idx_positions_symbol ON positions(symbol, status);
     CREATE INDEX idx_positions_strategy ON positions(strategy, outcome);
     ```

   - **Table: `portfolio_snapshots`** (для historical tracking)
     ```sql
     CREATE TABLE portfolio_snapshots (
         snapshot_id SERIAL PRIMARY KEY,
         timestamp TIMESTAMPTZ NOT NULL,
         
         total_equity_usd NUMERIC(20, 2),
         open_positions_count INTEGER,
         total_exposure_percent NUMERIC(10, 4),
         
         unrealized_pnl_usd NUMERIC(20, 2),
         realized_pnl_usd NUMERIC(20, 2),
         
         daily_return_percent NUMERIC(10, 4),
         sharpe_ratio NUMERIC(10, 4),
         
         positions_snapshot JSONB  -- Snapshot всех позиций
     );
     
     CREATE INDEX idx_snapshots_time ON portfolio_snapshots(timestamp DESC);
     ```

#### 3. → Redis (для real-time state)
   - **Key: `portfolio:positions:active`** → Set of position_ids
   - **Key: `portfolio:position:{position_id}`** → JSON position data
   - **Key: `portfolio:exposure:{symbol}`** → Decimal (current exposure)
   - **TTL:** Permanent (удаляется только при закрытии позиции)

#### 4. → Metrics (Prometheus)
   - Метрики: `open_positions_count`, `total_exposure_percent`, `unrealized_pnl_usd`, `position_win_rate`

### Контракты данных:

#### Position:

```python
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class PositionDirection(str, Enum):
    """Направление позиции."""
    LONG = "LONG"   # Купили (ожидаем рост)
    SHORT = "SHORT"  # Продали (ожидаем падение)

class PositionStatus(str, Enum):
    """Статус позиции."""
    OPEN = "OPEN"       # Активная позиция
    CLOSED = "CLOSED"   # Закрыта

class PositionOutcome(str, Enum):
    """Результат позиции."""
    WIN = "WIN"             # Прибыль
    LOSS = "LOSS"           # Убыток
    BREAKEVEN = "BREAKEVEN"  # Безубыток

@dataclass
class Position:
    """Торговая позиция."""
    
    position_id: str  # UUID
    opened_at: datetime
    closed_at: Optional[datetime] = None
    
    # Инструмент
    symbol: str  # "BTC/USDT"
    direction: PositionDirection
    
    # Цены
    entry_price: Decimal  # Цена входа
    exit_price: Optional[Decimal] = None  # Цена выхода
    
    # Размер
    quantity: Decimal  # Количество в базовой валюте (BTC)
    size_usd: Decimal  # Размер в USD
    
    # Уровни
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    
    # Происхождение
    strategy: Optional[str] = None  # "momentum"
    signal_id: Optional[str] = None
    
    # Статус
    status: PositionStatus = PositionStatus.OPEN
    
    # P&L (заполняется при закрытии)
    realized_pnl_usd: Optional[Decimal] = None
    realized_pnl_percent: Optional[Decimal] = None
    
    # Результат
    outcome: Optional[PositionOutcome] = None
    holding_time_seconds: Optional[int] = None
    
    # Метаданные
    metadata: Dict[str, Any] = None
    
    # Real-time (не в БД, только в памяти)
    current_price: Optional[Decimal] = None
    unrealized_pnl_usd: Optional[Decimal] = None
    unrealized_pnl_percent: Optional[Decimal] = None
    
    def calculate_unrealized_pnl(self, current_price: Decimal):
        """
        Рассчитать unrealized P&L при текущей цене.
        
        Formula:
        - LONG: (current_price - entry_price) * quantity
        - SHORT: (entry_price - current_price) * quantity
        """
        self.current_price = current_price
        
        if self.direction == PositionDirection.LONG:
            pnl_per_unit = current_price - self.entry_price
        else:  # SHORT
            pnl_per_unit = self.entry_price - current_price
        
        self.unrealized_pnl_usd = pnl_per_unit * self.quantity
        self.unrealized_pnl_percent = (pnl_per_unit / self.entry_price) * 100
    
    def close(
        self,
        exit_price: Decimal,
        closed_at: datetime,
    ):
        """
        Закрыть позицию и рассчитать realized P&L.
        """
        self.exit_price = exit_price
        self.closed_at = closed_at
        self.status = PositionStatus.CLOSED
        
        # Рассчитать realized P&L
        if self.direction == PositionDirection.LONG:
            pnl_per_unit = exit_price - self.entry_price
        else:  # SHORT
            pnl_per_unit = self.entry_price - exit_price
        
        self.realized_pnl_usd = pnl_per_unit * self.quantity
        self.realized_pnl_percent = (pnl_per_unit / self.entry_price) * 100
        
        # Определить outcome
        if self.realized_pnl_usd > Decimal("1"):  # $1+ = WIN
            self.outcome = PositionOutcome.WIN
        elif self.realized_pnl_usd < Decimal("-1"):  # -$1+ = LOSS
            self.outcome = PositionOutcome.LOSS
        else:
            self.outcome = PositionOutcome.BREAKEVEN
        
        # Holding time
        self.holding_time_seconds = int((closed_at - self.opened_at).total_seconds())
    
    def is_stop_loss_hit(self, current_price: Decimal) -> bool:
        """Проверить достигнут ли stop-loss."""
        if not self.stop_loss:
            return False
        
        if self.direction == PositionDirection.LONG:
            return current_price <= self.stop_loss
        else:  # SHORT
            return current_price >= self.stop_loss
    
    def is_take_profit_hit(self, current_price: Decimal) -> bool:
        """Проверить достигнут ли take-profit."""
        if not self.take_profit:
            return False
        
        if self.direction == PositionDirection.LONG:
            return current_price >= self.take_profit
        else:  # SHORT
            return current_price <= self.take_profit
```

#### Portfolio State:

```python
@dataclass
class PortfolioState:
    """Состояние портфеля в момент времени."""
    
    timestamp: datetime
    
    # Equity
    total_equity_usd: Decimal  # Общий капитал (cash + unrealized P&L)
    cash_balance_usd: Decimal  # Свободные средства
    
    # Positions
    open_positions_count: int
    positions: List[Position]
    
    # Exposure
    total_exposure_usd: Decimal  # Сумма всех size_usd
    total_exposure_percent: Decimal  # % от equity
    
    # P&L
    unrealized_pnl_usd: Decimal  # Сумма unrealized по всем позициям
    realized_pnl_usd: Decimal  # Сумма realized за период
    total_pnl_usd: Decimal  # unrealized + realized
    
    # Performance
    daily_return_percent: Decimal
    win_rate: Decimal  # % выигрышных сделок
    average_win_usd: Decimal
    average_loss_usd: Decimal
    profit_factor: Decimal  # Gross profit / Gross loss
    sharpe_ratio: Optional[Decimal] = None
    
    def get_exposure_by_symbol(self) -> Dict[str, Decimal]:
        """Получить exposure по символам."""
        exposure = {}
        for pos in self.positions:
            if pos.status == PositionStatus.OPEN:
                current = exposure.get(pos.symbol, Decimal("0"))
                exposure[pos.symbol] = current + pos.size_usd
        return exposure
    
    def get_exposure_by_strategy(self) -> Dict[str, Decimal]:
        """Получить exposure по стратегиям."""
        exposure = {}
        for pos in self.positions:
            if pos.status == PositionStatus.OPEN and pos.strategy:
                current = exposure.get(pos.strategy, Decimal("0"))
                exposure[pos.strategy] = current + pos.size_usd
        return exposure
```

### Sequence Diagram (Position Lifecycle):

```
[Strategy Manager] ──ORDER_FILLED──> [Portfolio Governor]
                                            |
                                [Create Position object]
                                            |
                            ┌───────────────┼───────────────┐
                            v               v               v
                    [Check Limits]  [Add to Active]  [Calculate Exposure]
                    max positions   positions list   total exposure %
                    correlation                      per-symbol
                            |               |               |
                            v               v               v
                        ✅ OK          update state     update metrics
                            |               |               |
                            └───────────────┼───────────────┘
                                            v
                            ┌───────────────┼───────────────┐
                            v               v               v
                    [PostgreSQL]    [Redis]         [Event Bus]
                    INSERT          cache           POSITION_OPENED
                    positions       active set
                                            
[Market Data] ──TICK_RECEIVED──> [Portfolio Governor]
                                            |
                                [Update Unrealized P&L]
                                for all open positions
                                            |
                            ┌───────────────┼───────────────┐
                            v               v               v
                    [Check SL/TP]   [Update Metrics]  [Redis Cache]
                    hit?            unrealized_pnl    update position
                            |               
                            v
                    [Trigger Close]
                    if SL/TP hit
                                            
[Strategy Manager] ──CLOSE_POSITION──> [Portfolio Governor]
                                            |
                                [Close Position]
                                calculate realized P&L
                                            |
                            ┌───────────────┼───────────────┐
                            v               v               v
                    [PostgreSQL]    [Redis]         [Event Bus]
                    UPDATE          remove from     POSITION_CLOSED
                    set closed      active set
```

### Обработка ошибок интеграции:

#### 1. Превышение лимита позиций:

```python
class PortfolioGovernor:
    async def check_can_open_position(
        self,
        symbol: str,
        size_usd: Decimal,
        strategy: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Проверить можно ли открыть позицию.
        
        Возвращает:
            (allowed, rejection_reason)
        """
        # Проверка 1: Max positions
        if len(self.active_positions) >= self.config.max_positions:
            logger.warning(
                "Достигнут лимит максимальных позиций",
                current=len(self.active_positions),
                max=self.config.max_positions,
            )
            return False, f"max_positions_reached_{self.config.max_positions}"
        
        # Проверка 2: Max exposure
        current_exposure = self.get_total_exposure_percent()
        new_exposure = current_exposure + (size_usd / self.total_equity) * 100
        
        if new_exposure > self.config.max_exposure_percent:
            logger.warning(
                "Превышен лимит exposure",
                current=current_exposure,
                new=new_exposure,
                max=self.config.max_exposure_percent,
            )
            return False, f"max_exposure_{new_exposure}_limit_{self.config.max_exposure_percent}"
        
        # Проверка 3: Max per-symbol exposure
        symbol_exposure = self.get_symbol_exposure(symbol)
        new_symbol_exposure = (symbol_exposure + size_usd) / self.total_equity * 100
        
        if new_symbol_exposure > self.config.max_per_symbol_percent:
            logger.warning(
                "Превышен лимит per-symbol exposure",
                symbol=symbol,
                current=symbol_exposure,
                new=new_symbol_exposure,
                max=self.config.max_per_symbol_percent,
            )
            return False, f"max_symbol_exposure_{symbol}"
        
        # Проверка 4: Correlation check
        if await self._check_correlation_violation(symbol, size_usd):
            return False, "correlation_too_high"
        
        # Все проверки passed
        return True, None
```

**Действия при rejection:**
- Return (False, reason)
- WARNING log
- Метрика: `positions_rejected_total{reason}`
- Event: `POSITION_REJECTED`

#### 2. Mark-to-market при missing tick:

```python
class PortfolioGovernor:
    async def update_position_pnl(
        self,
        position_id: str,
        current_price: Decimal,
    ):
        """
        Обновить unrealized P&L позиции.
        """
        position = self.active_positions.get(position_id)
        
        if not position:
            logger.error(
                "Позиция не найдена для update P&L",
                position_id=position_id,
            )
            return
        
        try:
            # Рассчитать unrealized P&L
            position.calculate_unrealized_pnl(current_price)
            
            # Обновить в Redis cache
            await self._update_position_cache(position)
            
            # Проверить SL/TP
            if position.is_stop_loss_hit(current_price):
                logger.info(
                    "Stop-loss достигнут",
                    position_id=position_id,
                    stop_loss=position.stop_loss,
                    current_price=current_price,
                )
                
                # Trigger close
                await self._trigger_close_position(
                    position_id=position_id,
                    reason="stop_loss_hit",
                )
            
            elif position.is_take_profit_hit(current_price):
                logger.info(
                    "Take-profit достигнут",
                    position_id=position_id,
                    take_profit=position.take_profit,
                    current_price=current_price,
                )
                
                await self._trigger_close_position(
                    position_id=position_id,
                    reason="take_profit_hit",
                )
            
        except Exception as e:
            logger.error(
                "Ошибка обновления P&L",
                position_id=position_id,
                error=str(e),
            )
```

**Fallback при missing ticks:**
- Использовать last known price
- TTL для stale prices (60 секунд)
- Alert если ticks не приходят >60 сек

#### 3. Correlation violation detection:

```python
class PortfolioGovernor:
    async def _check_correlation_violation(
        self,
        new_symbol: str,
        new_size_usd: Decimal,
    ) -> bool:
        """
        Проверить не создаст ли новая позиция высокую корреляцию.
        
        Логика:
        - Если уже есть позиция в BTC/USDT
        - И пытаемся открыть ETH/USDT
        - Проверить correlation(BTC, ETH)
        - Если correlation > 0.7 и total exposure > 50% → reject
        """
        # Получить все символы открытых позиций
        open_symbols = [pos.symbol for pos in self.active_positions.values()]
        
        if not open_symbols:
            return False  # Нет корреляции с пустым портфелем
        
        # Для каждого открытого символа проверить корреляцию
        for symbol in open_symbols:
            # Получить correlation из Indicator Engine
            correlation = await self.indicator_engine.get_correlation(
                symbol1=symbol,
                symbol2=new_symbol,
            )
            
            if correlation > self.config.max_correlation:
                # Высокая корреляция → проверить total exposure
                total_exposure_percent = self.get_total_exposure_percent()
                
                if total_exposure_percent > 50:
                    logger.warning(
                        "Отклонена позиция из-за высокой корреляции",
                        existing_symbol=symbol,
                        new_symbol=new_symbol,
                        correlation=correlation,
                        total_exposure=total_exposure_percent,
                    )
                    
                    # Публиковать event
                    await self.event_bus.publish(Event(
                        event_type="CORRELATION_VIOLATION",
                        priority=Priority.High,
                        source="portfolio_governor",
                        payload={
                            "existing_symbol": symbol,
                            "new_symbol": new_symbol,
                            "correlation": str(correlation),
                            "total_exposure": str(total_exposure_percent),
                        },
                    ))
                    
                    return True  # Violation detected
        
        return False  # No violation
```

**Correlation policy:**
- Max correlation: 0.7
- Только если total exposure > 50%
- Warning event публикуется

### Мониторинг интеграций:

#### Метрики Portfolio Governor:

```python
# Positions
open_positions_count{strategy}  # gauge
positions_opened_total{symbol, strategy}
positions_closed_total{symbol, strategy, outcome}
positions_rejected_total{reason}

# Exposure
total_exposure_percent{}  # gauge
exposure_by_symbol{symbol}  # gauge
exposure_by_strategy{strategy}  # gauge

# P&L
unrealized_pnl_usd{}  # gauge
realized_pnl_usd{}  # counter
total_pnl_usd{}  # gauge

# Performance
position_win_rate{strategy}  # gauge
average_win_usd{strategy}  # gauge
average_loss_usd{strategy}  # gauge
profit_factor{strategy}  # gauge

# Quality
position_holding_time_seconds{strategy, outcome}  # histogram
position_pnl_percent{strategy, outcome}  # histogram
```

#### Alerts:

**Critical:**
- `total_exposure_percent` > 80%
- `open_positions_count` > max_positions
- `unrealized_pnl_usd` < -20% of equity

**Warning:**
- `total_exposure_percent` > 60%
- `position_win_rate{strategy}` < 40%
- `positions_rejected_total` rate > 5/час

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 9

### Portfolio Governor:

**✅ Что реализовано:**
- Real-time position tracking
- Mark-to-market P&L calculation
- Exposure monitoring (total, per-symbol, per-strategy)
- Correlation checks
- Portfolio limits enforcement (max positions, max exposure)
- Automated SL/TP execution
- Performance analytics (win rate, profit factor)
- Position history persistence

**❌ Что НЕ реализовано:**
- Portfolio optimization (Markowitz, Black-Litterman)
- Dynamic hedging
- Multi-currency accounting
- Tax lot accounting
- Margin calculation
- Leverage management
- Cross-margining

**⚠️ ВАЖНО:**
```markdown
Portfolio Governor отслеживает positions, НЕ orders.
Order management в Фазе 11.

Correlation checks — basic Pearson correlation.
Для advanced portfolio optimization требуется:
- Фаза 21: ML Models
- Covariance matrix forecasting
- Risk parity allocation

P&L calculation — simple price difference.
НЕ учитывает:
- Funding fees (для perpetual futures)
- Borrowing costs (для margin)
- Transaction fees (учитываются в Execution)
```

### Production Readiness Matrix:

| Компонент | После Фазы 9 | Production Ready |
|-----------|--------------|------------------|
| Position Tracking | ✅ Ready | ✅ Ready |
| P&L Calculation | ✅ Ready (simple) | ⚠️ Funding/fees для futures |
| Exposure Monitoring | ✅ Ready | ✅ Ready |
| Correlation Checks | ✅ Ready (basic) | ⚠️ ML для advanced |
| Limits Enforcement | ✅ Ready | ✅ Ready |
| SL/TP Automation | ✅ Ready | ✅ Ready |

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ И МАСШТАБИРУЕМОСТЬ

### Критические требования:

```
Операция                         Latency Target    Частота
────────────────────────────────────────────────────────────────────
open_position()                  <100ms            5-20 раз/день
close_position()                 <100ms            5-20 раз/день
update_pnl()                     <10ms             10-100 раз/сек
check_can_open()                 <50ms             10-50 раз/час
get_portfolio_state()            <50ms             по запросу
calculate_analytics()            <200ms            раз в минуту
────────────────────────────────────────────────────────────────────
```

### Ожидаемая нагрузка:

```
Component                 Operations/sec    CPU Impact    Memory Impact
─────────────────────────────────────────────────────────────────────
Position updates          0.1-1/sec         Low           Low
P&L updates               10-100/sec        Low           Low (in-place)
Limit checks              0.5-5/sec         Low           Low
State queries             0.1-1/sec         Low           Low
Analytics calc            0.01-0.1/sec      Medium        Medium
─────────────────────────────────────────────────────────────────────
TOTAL                     ~50 ops/sec       Low           ~50 MB
```

### Критические узкие места:

#### 1. P&L update на каждый tick

**Проблема:** 100 ticks/сек * 10 позиций = 1000 P&L calculations/сек.

**Решение: Incremental in-place updates**

```python
class Position:
    def calculate_unrealized_pnl(self, current_price: Decimal):
        """
        In-place P&L update (НЕ создает новые объекты).
        """
        # Простая арифметика, no allocations
        self.current_price = current_price
        
        if self.direction == PositionDirection.LONG:
            pnl_per_unit = current_price - self.entry_price
        else:
            pnl_per_unit = self.entry_price - current_price
        
        # In-place update
        self.unrealized_pnl_usd = pnl_per_unit * self.quantity
        self.unrealized_pnl_percent = (pnl_per_unit / self.entry_price) * 100
```

**Результат:**
- No object creation → no GC pressure
- Simple arithmetic → <1ms
- Scales to 100+ positions

#### 2. Database write на каждую позицию

**Решение: Batch writes + async worker**

```python
class PortfolioGovernor:
    def __init__(self, ...):
        # Queue для async DB writes
        self.db_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        asyncio.create_task(self._db_writer_worker())
    
    async def open_position(self, ...) -> Position:
        """Open position БЕЗ блокировки на DB write."""
        # ... create position
        
        # Enqueue для async write (non-blocking)
        await self.db_queue.put(("INSERT", position))
        
        return position
    
    async def _db_writer_worker(self):
        """Background worker для batch DB writes."""
        batch = []
        
        while True:
            try:
                # Собрать batch
                while len(batch) < 10:
                    op, data = await asyncio.wait_for(
                        self.db_queue.get(),
                        timeout=1.0,
                    )
                    batch.append((op, data))
                
                # Batch INSERT
                await self._batch_write(batch)
                batch.clear()
                
            except asyncio.TimeoutError:
                # Flush partial batch
                if batch:
                    await self._batch_write(batch)
                    batch.clear()
```

**Результат:**
- Non-blocking position operations
- Batch writes (10x faster)

#### 3. Correlation checks на каждый сигнал

**Решение: Cache correlation matrix**

```python
class PortfolioGovernor:
    def __init__(self, ...):
        # Correlation cache
        self._correlation_cache: Dict[Tuple[str, str], Tuple[Decimal, datetime]] = {}
        self._correlation_ttl = timedelta(minutes=30)
    
    async def _get_correlation_cached(
        self,
        symbol1: str,
        symbol2: str,
    ) -> Decimal:
        """Get correlation с кэшированием."""
        cache_key = tuple(sorted([symbol1, symbol2]))
        
        # Check cache
        if cache_key in self._correlation_cache:
            corr, cached_at = self._correlation_cache[cache_key]
            
            if datetime.now(timezone.utc) - cached_at < self._correlation_ttl:
                return corr  # Cache hit
        
        # Cache miss → fetch
        corr = await self.indicator_engine.get_correlation(symbol1, symbol2)
        
        # Update cache
        self._correlation_cache[cache_key] = (corr, datetime.now(timezone.utc))
        
        return corr
```

**Результат:**
- Cache hit: instant
- TTL 30 минут (correlation stable)

#### 4. Analytics calculation overhead

**Решение: Lazy calculation + caching**

```python
class PortfolioGovernor:
    def __init__(self, ...):
        self._analytics_cache: Optional[Tuple[PortfolioAnalytics, datetime]] = None
        self._analytics_ttl = timedelta(seconds=60)
    
    def get_analytics(self) -> PortfolioAnalytics:
        """Get analytics с ленивым вычислением."""
        # Check cache
        if self._analytics_cache:
            analytics, cached_at = self._analytics_cache
            
            if datetime.now(timezone.utc) - cached_at < self._analytics_ttl:
                return analytics
        
        # Recalculate
        analytics = self._calculate_analytics()
        self._analytics_cache = (analytics, datetime.now(timezone.utc))
        
        return analytics
```

**Результат:**
- Analytics computed раз в минуту
- Cache hit: instant

---

## 📊 ОБЯЗАТЕЛЬНЫЕ BENCHMARK ТЕСТЫ

```python
@pytest.mark.benchmark
async def test_position_pnl_update_latency():
    """
    Acceptance: <10ms per position
    """
    portfolio = PortfolioGovernor(...)
    
    # Open 100 positions
    for i in range(100):
        pos = Position(...)
        portfolio.active_positions[pos.position_id] = pos
    
    # Benchmark P&L update for all
    start = time.time()
    for pos in portfolio.active_positions.values():
        pos.calculate_unrealized_pnl(Decimal("50000"))
    duration = (time.time() - start) * 1000
    
    assert duration < 100, f"100 positions: {duration}ms > 100ms"

@pytest.mark.benchmark
async def test_open_position_throughput():
    """
    Acceptance: >10 positions/sec
    """
    # ...

@pytest.mark.benchmark
async def test_correlation_check_latency():
    """
    Acceptance: cache hit <1ms, miss <100ms
    """
    # ...
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── src/
│   └── portfolio/
│       ├── __init__.py
│       ├── governor.py                   # Main PortfolioGovernor
│       ├── position.py                   # Position dataclass
│       ├── analytics.py                  # Performance analytics
│       ├── limits.py                     # Limit checks
│       └── models.py                     # PortfolioState
│
└── tests/
    ├── unit/
    │   ├── test_position.py
    │   ├── test_analytics.py
    │   └── test_limits.py
    ├── integration/
    │   └── test_portfolio_governor.py
    └── benchmarks/
        └── bench_portfolio.py
```

---

## ACCEPTANCE CRITERIA

### Position Management
- [ ] Open/close positions
- [ ] Track active positions
- [ ] Calculate realized/unrealized P&L
- [ ] Automated SL/TP execution

### Limits Enforcement
- [ ] Max positions
- [ ] Max total exposure
- [ ] Max per-symbol exposure
- [ ] Correlation checks

### Performance
- [ ] P&L update <10ms
- [ ] Position open <100ms
- [ ] >10 positions/sec throughput

### Analytics
- [ ] Win rate
- [ ] Profit factor
- [ ] Average win/loss
- [ ] Sharpe ratio

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 9: Portfolio Governor** готова к реализации! 🚀
