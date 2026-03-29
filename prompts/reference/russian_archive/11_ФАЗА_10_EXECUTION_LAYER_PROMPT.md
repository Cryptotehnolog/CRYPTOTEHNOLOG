# AI ПРОМТ: ФАЗА 10 - EXECUTION LAYER

## КОНТЕКСТ

Вы — Senior Trading Systems Engineer, специализирующийся на order execution, exchange APIs, и low-latency trading infrastructure.

**Фазы 0-9 завершены.** Доступны:
- Event Bus (Rust + Python) — работает с persistence
- Control Plane (State Machine, Watchdog) — работает
- Config Manager — hot reload, GPG signatures, Vault
- Risk Engine — R-unit sizing, correlation, drawdown
- Market Data Layer — WebSocket, ticks, OHLCV bars, orderbook
- Technical Indicators — 20+ индикаторов, NumPy vectorization
- Signal Generator — торговые стратегии, confidence scoring
- Portfolio Governor — position tracking, P&L, exposure
- Database Layer, Logging, Metrics — готовы

**Текущая задача:** Реализовать production-ready Execution Layer с multi-exchange support, smart order routing, slippage control, retry logic, и real-time order status tracking.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class ExecutionEngine:
    """
    Движок исполнения ордеров с multi-exchange support.
    
    Особенности:
    - Multi-exchange connectivity (Bybit, OKX, Binance)
    - Smart order placement (TWAP, VWAP, Iceberg)
    - Slippage control (limit orders с price tolerance)
    - Retry logic с exponential backoff
    - Order status tracking (PENDING → FILLED → SETTLED)
    - Fill notifications (partial fills, complete fills)
    - Rate limiting (соблюдение exchange limits)
    - Exchange failover (если одна биржа недоступна)
    """
    
    async def execute_order(
        self,
        signal: TradingSignal,
        position_size: Decimal,
    ) -> Order:
        """
        Исполнить торговый сигнал на бирже.
        
        Аргументы:
            signal: Торговый сигнал (BUY/SELL)
            position_size: Размер позиции в USD
        
        Возвращает:
            Order объект
        
        Процесс:
        1. Выбрать биржу (smart routing)
        2. Рассчитать quantity (size_usd / price)
        3. Проверить balance достаточен
        4. Создать limit order (entry_price ± slippage_tolerance)
        5. Отправить на биржу
        6. Отслеживать статус (polling или WebSocket)
        7. Обработать fills (partial/complete)
        8. Публиковать ORDER_FILLED event
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.info("Ордер отправлен на биржу", order_id="ord_123", exchange="bybit", symbol="BTC/USDT")
logger.warning("Частичное исполнение", order_id="ord_123", filled=0.3, total=0.5)
logger.error("Ордер отклонен биржей", reason="insufficient_balance", required=10000, available=5000)
logger.debug("Статус ордера обновлен", order_id="ord_123", status="PARTIALLY_FILLED")
```

### Примеры замены:

| ❌ Неправильно | ✅ Правильно |
|----------------|--------------|
| "Order placed" | "Ордер размещен" |
| "Partial fill" | "Частичное исполнение" |
| "Insufficient balance" | "Недостаточный баланс" |
| "Slippage exceeded" | "Превышен slippage" |
| "Exchange timeout" | "Таймаут биржи" |

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Execution Layer — мост между торговой логикой и биржами. Получает торговые сигналы от Strategy Manager, преобразует в ордера, отправляет на биржи через REST/WebSocket API, отслеживает исполнение, обрабатывает fills (частичные и полные), управляет retry при сбоях, контролирует slippage, и уведомляет Portfolio Governor о completed trades.

### Входящие зависимости (кто запрашивает execution):

#### 1. **Strategy Manager (Фаза 14)** → execution торговых сигналов
   - Запрос: `async def execute_signal(signal: TradingSignal, size_usd: Decimal) -> Order`
   - Частота: 5-20 раз/день
   - Действие: Strategy получил validated сигнал от Risk Engine → execute
   - Timeout: 30 секунд (exchange latency)
   - Критичность: HIGH (это основная функция)

#### 2. **Portfolio Governor (Фаза 9)** → закрытие позиций (SL/TP hit)
   - Запрос: `async def close_position(position: Position, reason: str) -> Order`
   - Частота: 5-20 раз/день
   - Действие: Portfolio обнаружил SL/TP hit → немедленно закрыть
   - Критичность: CRITICAL (защита капитала)

#### 3. **Risk Engine (Фаза 5)** → emergency close (kill switch)
   - Запрос: `async def emergency_close_all() -> List[Order]`
   - Частота: очень редко (emergency)
   - Действие: Закрыть ВСЕ позиции немедленно (market orders)
   - Критичность: CRITICAL

#### 4. **Market Data Layer (Фаза 6)** → orderbook для smart execution
   - Запрос: `async def get_orderbook(symbol: str, exchange: str) -> Orderbook`
   - Частота: перед каждым ордером
   - Действие: Execution проверяет liquidity перед размещением
   - Критичность: MEDIUM (optimization)

#### 5. **Config Manager (Фаза 4)** → hot reload execution params
   - Event: `CONFIG_UPDATED` (slippage_tolerance, retry_attempts)
   - Частота: редко
   - Действие: Execution обновляет parameters
   - Критичность: LOW

### Исходящие зависимости (что публикует Execution Layer):

#### 1. → Event Bus (Фаза 3)
   - **Event: `ORDER_SUBMITTED`** (приоритет: HIGH)
     - Payload:
       ```json
       {
         "order_id": "ord_uuid",
         "exchange_order_id": "exch_123",
         "exchange": "bybit",
         "symbol": "BTC/USDT",
         "side": "BUY",
         "order_type": "LIMIT",
         "quantity": 0.5,
         "price": 50000,
         "status": "PENDING",
         "timestamp": 1704067200000000
       }
       ```
     - Подписчики: Observability, Order Manager (Фаза 11)

   - **Event: `ORDER_FILLED`** (приоритет: CRITICAL)
     - Payload:
       ```json
       {
         "order_id": "ord_uuid",
         "exchange_order_id": "exch_123",
         "filled_quantity": 0.5,
         "filled_price": 50050,
         "fill_type": "COMPLETE",
         "commission": 5.0,
         "commission_asset": "USDT",
         "timestamp": 1704067210000000
       }
       ```
     - Подписчики: Portfolio Governor (для position tracking), Analytics

   - **Event: `ORDER_REJECTED`** (приоритет: HIGH)
     - Payload: `{"order_id": "...", "reason": "insufficient_balance", "exchange": "bybit"}`
     - Подписчики: Strategy Manager (для retry logic), Observability

   - **Event: `SLIPPAGE_EXCEEDED`** (приоритет: HIGH)
     - Payload: `{"order_id": "...", "expected_price": 50000, "market_price": 50500, "slippage_percent": 1.0}`
     - Подписчики: Risk Engine, Observability

#### 2. → PostgreSQL (для order history)
   - **Table: `orders`**
     ```sql
     CREATE TABLE orders (
         order_id VARCHAR(50) PRIMARY KEY,
         created_at TIMESTAMPTZ NOT NULL,
         updated_at TIMESTAMPTZ,
         
         exchange VARCHAR(20) NOT NULL,
         exchange_order_id VARCHAR(100),
         
         symbol VARCHAR(20) NOT NULL,
         side VARCHAR(4) NOT NULL,  -- BUY, SELL
         order_type VARCHAR(10) NOT NULL,  -- LIMIT, MARKET, STOP
         
         quantity NUMERIC(20, 8) NOT NULL,
         price NUMERIC(20, 8),
         
         filled_quantity NUMERIC(20, 8) DEFAULT 0,
         average_fill_price NUMERIC(20, 8),
         
         status VARCHAR(20) DEFAULT 'PENDING',
         -- PENDING, SUBMITTED, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED
         
         commission NUMERIC(20, 8),
         commission_asset VARCHAR(10),
         
         signal_id VARCHAR(50),
         position_id VARCHAR(50),
         
         metadata JSONB
     );
     
     CREATE INDEX idx_orders_created ON orders(created_at DESC);
     CREATE INDEX idx_orders_symbol ON orders(symbol, status);
     CREATE INDEX idx_orders_exchange ON orders(exchange, exchange_order_id);
     ```

#### 3. → Exchange APIs (REST + WebSocket)
   - **Bybit REST API:**
     - POST `/v5/order/create` — создать ордер
     - GET `/v5/order/realtime` — статус ордера
     - POST `/v5/order/cancel` — отменить ордер
   
   - **Bybit WebSocket:**
     - Subscribe `order` stream — real-time order updates
     - Subscribe `execution` stream — fills

#### 4. → Redis (для order state cache)
   - **Key: `order:{order_id}`** → JSON order data
   - **Key: `orders:pending`** → Set of pending order_ids
   - **TTL:** 24 часа (для completed orders)

#### 5. → Metrics (Prometheus)
   - Метрики: `orders_submitted_total`, `orders_filled_total`, `execution_latency_seconds`, `slippage_percent`

### Контракты данных:

#### Order:

```python
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class OrderSide(str, Enum):
    """Сторона ордера."""
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    """Тип ордера."""
    LIMIT = "LIMIT"      # Limit order (цена гарантирована)
    MARKET = "MARKET"    # Market order (исполнение гарантировано)
    STOP = "STOP"        # Stop order (trigger price)
    STOP_LIMIT = "STOP_LIMIT"

class OrderStatus(str, Enum):
    """Статус ордера."""
    PENDING = "PENDING"               # Создан, не отправлен
    SUBMITTED = "SUBMITTED"           # Отправлен на биржу
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Частично исполнен
    FILLED = "FILLED"                 # Полностью исполнен
    CANCELLED = "CANCELLED"           # Отменен
    REJECTED = "REJECTED"             # Отклонен биржей
    EXPIRED = "EXPIRED"               # Истек (timeout)

class FillType(str, Enum):
    """Тип исполнения."""
    PARTIAL = "PARTIAL"    # Частичное
    COMPLETE = "COMPLETE"  # Полное

@dataclass
class Order:
    """Торговый ордер."""
    
    order_id: str  # Наш UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Exchange
    exchange: str  # "bybit", "okx", "binance"
    exchange_order_id: Optional[str] = None  # ID от биржи
    
    # Instrument
    symbol: str  # "BTC/USDT"
    side: OrderSide
    order_type: OrderType
    
    # Quantity & Price
    quantity: Decimal  # Количество (в базовой валюте)
    price: Optional[Decimal] = None  # Цена (для LIMIT)
    
    # Execution
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Optional[Decimal] = None
    
    # Status
    status: OrderStatus = OrderStatus.PENDING
    
    # Fees
    commission: Optional[Decimal] = None
    commission_asset: Optional[str] = None  # "USDT"
    
    # References
    signal_id: Optional[str] = None
    position_id: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = None
    
    # Retry tracking
    retry_count: int = 0
    max_retries: int = 3
    
    def is_filled(self) -> bool:
        """Проверить полностью ли исполнен ордер."""
        return self.status == OrderStatus.FILLED
    
    def is_partially_filled(self) -> bool:
        """Проверить частично ли исполнен."""
        return self.filled_quantity > 0 and self.filled_quantity < self.quantity
    
    def get_remaining_quantity(self) -> Decimal:
        """Получить неисполненное количество."""
        return self.quantity - self.filled_quantity
    
    def update_fill(
        self,
        fill_quantity: Decimal,
        fill_price: Decimal,
        commission: Decimal,
        commission_asset: str,
    ):
        """
        Обновить ордер после fill.
        """
        self.filled_quantity += fill_quantity
        
        # Weighted average fill price
        if self.average_fill_price is None:
            self.average_fill_price = fill_price
        else:
            total_filled_value = (self.average_fill_price * (self.filled_quantity - fill_quantity)) + (fill_price * fill_quantity)
            self.average_fill_price = total_filled_value / self.filled_quantity
        
        # Commission
        if self.commission is None:
            self.commission = commission
        else:
            self.commission += commission
        
        self.commission_asset = commission_asset
        
        # Update status
        if self.filled_quantity >= self.quantity:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIALLY_FILLED
        
        self.updated_at = datetime.now(timezone.utc)

@dataclass
class ExecutionResult:
    """Результат исполнения ордера."""
    
    order: Order
    success: bool
    error_message: Optional[str] = None
    
    # Execution quality
    expected_price: Optional[Decimal] = None
    actual_price: Optional[Decimal] = None
    slippage_percent: Optional[Decimal] = None
    
    # Timing
    submission_latency_ms: Optional[float] = None
    fill_latency_ms: Optional[float] = None
```

#### Smart Order Routing:

```python
class SmartOrderRouter:
    """
    Умная маршрутизация ордеров между биржами.
    
    Критерии выбора биржи:
    1. Liquidity (orderbook depth)
    2. Fees (maker/taker)
    3. Latency (ping time)
    4. Availability (health status)
    """
    
    async def select_exchange(
        self,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
    ) -> str:
        """
        Выбрать оптимальную биржу для ордера.
        
        Процесс:
        1. Получить orderbook от всех бирж
        2. Рассчитать available liquidity на каждой
        3. Сравнить fees
        4. Проверить latency
        5. Выбрать лучшую
        """
        available_exchanges = self.config.get_enabled_exchanges()
        
        # Score для каждой биржи
        scores = {}
        
        for exchange in available_exchanges:
            try:
                # 1. Liquidity check
                orderbook = await self.market_data.get_orderbook(symbol, exchange)
                available_liquidity = self._calculate_liquidity(orderbook, side, quantity)
                
                if available_liquidity < quantity:
                    logger.debug(
                        "Недостаточная ликвидность",
                        exchange=exchange,
                        available=available_liquidity,
                        required=quantity,
                    )
                    continue  # Skip this exchange
                
                # 2. Fees
                fees = self.config.get_exchange_fees(exchange)
                
                # 3. Latency
                latency = await self._check_latency(exchange)
                
                # Calculate score (higher = better)
                score = (
                    (available_liquidity / quantity) * 0.4 +  # 40% weight
                    (1 / fees.taker) * 0.3 +                   # 30% weight
                    (1 / latency) * 0.3                         # 30% weight
                )
                
                scores[exchange] = score
                
            except Exception as e:
                logger.error(
                    "Ошибка проверки биржи",
                    exchange=exchange,
                    error=str(e),
                )
        
        if not scores:
            raise ExecutionError("Нет доступных бирж с достаточной ликвидностью")
        
        # Выбрать биржу с максимальным score
        best_exchange = max(scores.items(), key=lambda x: x[1])[0]
        
        logger.info(
            "Биржа выбрана",
            exchange=best_exchange,
            score=scores[best_exchange],
            alternatives=scores,
        )
        
        return best_exchange
```

### Sequence Diagram (Order Execution Flow):

```
[Strategy Manager] ──execute_signal──> [Execution Engine]
                                              |
                                  [Smart Order Router]
                                  select best exchange
                                              |
                                              v
                                  [Bybit/OKX/Binance]
                                              |
                            ┌─────────────────┼─────────────────┐
                            v                 v                 v
                    [Check Balance]  [Calculate Qty]  [Create Order]
                    sufficient?      size/price        limit order
                            |                 |                 |
                            v                 v                 v
                        ✅ OK           quantity=0.5      price=50000
                                              |
                                              v
                            [Submit to Exchange API]
                            POST /v5/order/create
                                              |
                            ┌─────────────────┼─────────────────┐
                            v                                   v
                        SUCCESS                             REJECTED
                            |                                   |
                            v                                   v
                [Order Status Tracking]              [ORDER_REJECTED event]
                WebSocket subscription               retry logic
                            |
                ┌───────────┼───────────┐
                v                       v
        [PARTIAL_FILL]          [COMPLETE_FILL]
                |                       |
                v                       v
        [ORDER_FILLED event]    [ORDER_FILLED event]
        fill_type=PARTIAL        fill_type=COMPLETE
                |                       |
                v                       v
        [Portfolio Governor]    [Portfolio Governor]
        update position         register position
```

### Обработка ошибок интеграции:

#### 1. Insufficient balance:

```python
class ExecutionEngine:
    async def execute_order(
        self,
        signal: TradingSignal,
        position_size_usd: Decimal,
    ) -> ExecutionResult:
        """Execute с проверкой balance."""
        # Select exchange
        exchange = await self.router.select_exchange(
            signal.symbol,
            signal.direction,
            quantity,
        )
        
        # Check balance
        balance = await self.exchange_clients[exchange].get_balance("USDT")
        
        if balance < position_size_usd:
            logger.error(
                "Недостаточный баланс для ордера",
                exchange=exchange,
                required=position_size_usd,
                available=balance,
            )
            
            # Публиковать event
            await self.event_bus.publish(Event(
                event_type="ORDER_REJECTED",
                priority=Priority.High,
                source="execution_engine",
                payload={
                    "order_id": order.order_id,
                    "reason": "insufficient_balance",
                    "required": str(position_size_usd),
                    "available": str(balance),
                },
            ))
            
            return ExecutionResult(
                order=order,
                success=False,
                error_message=f"Insufficient balance: need {position_size_usd}, have {balance}",
            )
        
        # Продолжить execution
        # ...
```

**Действия:**
- Проверить balance перед submission
- Публиковать ORDER_REJECTED event
- Return ExecutionResult с success=False
- Метрика: `orders_rejected_total{reason="insufficient_balance"}`

#### 2. Exchange API timeout:

```python
class ExecutionEngine:
    async def _submit_order_with_retry(
        self,
        order: Order,
        max_retries: int = 3,
    ) -> bool:
        """
        Submit order с retry logic.
        
        Retry policy:
        - Exponential backoff: 1s, 2s, 4s
        - Max retries: 3
        - Только для network errors (не для rejections)
        """
        for attempt in range(max_retries):
            try:
                # Submit to exchange
                response = await asyncio.wait_for(
                    self.exchange_clients[order.exchange].create_order(
                        symbol=order.symbol,
                        side=order.side.value,
                        type=order.order_type.value,
                        quantity=order.quantity,
                        price=order.price,
                    ),
                    timeout=10.0,  # 10 second timeout
                )
                
                # Success
                order.exchange_order_id = response["order_id"]
                order.status = OrderStatus.SUBMITTED
                
                logger.info(
                    "Ордер отправлен на биржу",
                    order_id=order.order_id,
                    exchange_order_id=order.exchange_order_id,
                    attempt=attempt + 1,
                )
                
                return True
                
            except asyncio.TimeoutError:
                logger.warning(
                    "Таймаут биржи, повтор",
                    order_id=order.order_id,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )
                
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)
                
            except ExchangeRejectionError as e:
                # Rejection → НЕ retry
                logger.error(
                    "Ордер отклонен биржей",
                    order_id=order.order_id,
                    reason=str(e),
                )
                
                order.status = OrderStatus.REJECTED
                return False
            
            except Exception as e:
                logger.error(
                    "Ошибка отправки ордера",
                    order_id=order.order_id,
                    error=str(e),
                )
                
                await asyncio.sleep(2 ** attempt)
        
        # Все попытки провалились
        logger.critical(
            "Не удалось отправить ордер после всех попыток",
            order_id=order.order_id,
            max_retries=max_retries,
        )
        
        order.status = OrderStatus.EXPIRED
        return False
```

**Retry policy:**
- Network errors: retry с exponential backoff
- Rejections: НЕ retry
- Max retries: 3
- Timeout: 10 секунд на попытку

#### 3. Slippage control:

```python
class ExecutionEngine:
    async def _check_slippage(
        self,
        signal: TradingSignal,
        current_market_price: Decimal,
    ) -> bool:
        """
        Проверить не превышен ли slippage.
        
        Slippage tolerance: default 0.5%
        """
        expected_price = signal.entry_price
        slippage_percent = abs(current_market_price - expected_price) / expected_price * 100
        
        if slippage_percent > self.config.max_slippage_percent:
            logger.warning(
                "Превышен допустимый slippage",
                expected_price=expected_price,
                market_price=current_market_price,
                slippage_percent=slippage_percent,
                max_allowed=self.config.max_slippage_percent,
            )
            
            # Публиковать event
            await self.event_bus.publish(Event(
                event_type="SLIPPAGE_EXCEEDED",
                priority=Priority.High,
                source="execution_engine",
                payload={
                    "signal_id": signal.signal_id,
                    "expected_price": str(expected_price),
                    "market_price": str(current_market_price),
                    "slippage_percent": str(slippage_percent),
                },
            ))
            
            # Метрика
            self.metrics.slippage_exceeded_total.inc()
            
            return False  # Reject order
        
        return True  # Slippage OK
```

**Slippage policy:**
- Max slippage: 0.5% (configurable)
- Проверка перед submission
- Если превышен → reject order
- Event: SLIPPAGE_EXCEEDED

### Мониторинг интеграций:

#### Метрики Execution Layer:

```python
# Order submission
orders_submitted_total{exchange, symbol, side}
orders_rejected_total{exchange, reason}
order_submission_latency_seconds{exchange, percentile}

# Fills
orders_filled_total{exchange, symbol, fill_type}  # fill_type: partial, complete
fill_latency_seconds{exchange, percentile}
average_fill_price{exchange, symbol}

# Quality
slippage_percent{exchange, symbol}  # histogram
slippage_exceeded_total{exchange}
commission_paid_usd{exchange}  # counter

# Retries
order_retries_total{exchange, reason}
order_retry_success_rate{exchange}  # gauge

# Exchange health
exchange_api_latency_seconds{exchange, endpoint}
exchange_api_errors_total{exchange, error_type}
exchange_websocket_status{exchange}  # gauge: 1=connected, 0=disconnected
```

#### Alerts:

**Critical (PagerDuty):**
- `orders_rejected_total{reason="insufficient_balance"}` > 0
- `exchange_websocket_status{exchange="bybit"}` == 0 для >60 секунд
- `slippage_exceeded_total` rate > 20% от orders_submitted

**Warning (Telegram):**
- `order_submission_latency_seconds{p99}` > 5 секунд
- `order_retries_total` rate > 10/час
- `slippage_percent{p95}` > 0.3%

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 10

### Execution Layer:

**✅ Что реализовано:**
- Multi-exchange support (Bybit, OKX, Binance)
- Smart order routing (liquidity, fees, latency)
- Slippage control (max 0.5%)
- Retry logic (exponential backoff, 3 attempts)
- Order status tracking (WebSocket)
- Fill handling (partial/complete)
- Rate limiting (соблюдение exchange limits)

**❌ Что НЕ реализовано:**
- Advanced execution algos (TWAP, VWAP, Iceberg)
- Pre-trade analysis (market impact estimation)
- Post-trade TCA (Transaction Cost Analysis)
- SOR aggregation (split orders across exchanges)
- Dark pool connectivity
- Direct market access (FIX protocol)

**⚠️ ВАЖНО:**
```markdown
Execution Layer использует простые limit orders.
Для advanced execution требуется:
- TWAP: Time-Weighted Average Price splitting
- VWAP: Volume-Weighted Average Price
- Iceberg: Hidden quantity orders
- Фаза 20: Advanced Execution Algos

Smart routing выбирает ОДНУ биржу.
Для SOR (Smart Order Routing) aggregation требуется:
- Split order между несколькими биржами
- Aggregate fills
- Minimize market impact

Fees учитываются post-execution.
Для pre-trade cost estimation требуется:
- Market impact models
- Slippage prediction
- TCA framework
```

### Production Readiness Matrix:

| Компонент | После Фазы 10 | Production Ready |
|-----------|--------------|------------------|
| Order Submission | ✅ Ready | ✅ Ready |
| Smart Routing | ✅ Ready (single exchange) | ⚠️ SOR для advanced |
| Retry Logic | ✅ Ready | ✅ Ready |
| Slippage Control | ✅ Ready | ✅ Ready |
| Fill Tracking | ✅ Ready | ✅ Ready |
| Multi-Exchange | ✅ Ready (3 exchanges) | ✅ Ready |

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ И МАСШТАБИРУЕМОСТЬ

### Критические требования:

```
Операция                         Latency Target    Частота
────────────────────────────────────────────────────────────────────
execute_order()                  <5s               5-20 раз/день
select_exchange()                <500ms            перед каждым ордером
submit_order()                   <2s               5-20 раз/день
track_order_status()             <100ms            каждую секунду
handle_fill()                    <100ms            при fill event
────────────────────────────────────────────────────────────────────
```

### Ожидаемая нагрузка:

```
Component                 Operations/sec    CPU Impact    Memory Impact
─────────────────────────────────────────────────────────────────────
Order execution           0.01-0.1/sec      Low           Low
Exchange API calls        0.1-1/sec         Low           Low
WebSocket processing      1-10/sec          Low           Low
Status tracking           1-5/sec           Low           Low
DB writes                 0.01-0.1/sec      Low           Low
─────────────────────────────────────────────────────────────────────
TOTAL                     ~10 ops/sec       Low           ~30 MB
```

### Критические узкие места:

#### 1. Exchange API latency

**Проблема:** Каждый API call к бирже занимает 500ms-2s → медленно.

**Решение: Connection pooling + keep-alive**

```python
import aiohttp

class ExchangeClient:
    """Client с connection pooling."""
    
    def __init__(self, exchange: str, api_key: str, api_secret: str):
        self.exchange = exchange
        
        # Connection pool (reuse connections)
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=10,  # Max 10 concurrent connections
                ttl_dns_cache=300,  # Cache DNS
            ),
            timeout=aiohttp.ClientTimeout(total=10),
        )
    
    async def create_order(self, **params) -> dict:
        """Create order с connection reuse."""
        # Connection уже открыто → faster
        async with self.session.post(
            f"{self.base_url}/v5/order/create",
            json=params,
            headers=self._get_headers(),
        ) as response:
            return await response.json()
```

**Результат:**
- Connection reuse: ~200ms вместо ~500ms
- Keep-alive избегает handshake overhead

#### 2. Sequential order tracking

**Проблема:** Polling статуса каждого ордера по отдельности → медленно.

**Решение: WebSocket для real-time updates**

```python
class OrderStatusTracker:
    """WebSocket tracker для real-time order updates."""
    
    async def subscribe_order_updates(self, exchange: str):
        """
        Subscribe к order stream через WebSocket.
        
        Получаем updates в real-time (no polling).
        """
        ws_url = self.config.get_websocket_url(exchange)
        
        async with websockets.connect(ws_url) as ws:
            # Subscribe к order stream
            await ws.send(json.dumps({
                "op": "subscribe",
                "args": ["order"],
            }))
            
            # Listen for updates
            async for message in ws:
                data = json.loads(message)
                
                if data.get("topic") == "order":
                    await self._handle_order_update(data)
    
    async def _handle_order_update(self, data: dict):
        """Handle order update от WebSocket."""
        order_id = data["order_id"]
        status = data["status"]
        
        # Update order в памяти
        order = self.active_orders.get(order_id)
        if order:
            order.status = OrderStatus(status)
            
            # If filled → process
            if status == "FILLED":
                await self._process_fill(order, data)
```

**Результат:**
- Real-time updates (no polling delay)
- Latency: <100ms вместо 1-5 секунд (polling)

#### 3. Rate limiting overhead

**Проблема:** Каждый request проверяет rate limit → overhead.

**Решение: Token bucket с async sem**

```python
import asyncio
from collections import deque
from datetime import datetime, timedelta

class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, requests_per_second: int):
        self.rate = requests_per_second
        self.tokens = requests_per_second
        self.last_refill = datetime.now()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """
        Acquire token (wait if needed).
        
        Non-blocking для доступных tokens.
        """
        async with self._lock:
            # Refill tokens
            now = datetime.now()
            elapsed = (now - self.last_refill).total_seconds()
            
            if elapsed > 0:
                refill = elapsed * self.rate
                self.tokens = min(self.rate, self.tokens + refill)
                self.last_refill = now
            
            # Wait for token if needed
            while self.tokens < 1:
                await asyncio.sleep(0.01)
                # Refill again
                now = datetime.now()
                elapsed = (now - self.last_refill).total_seconds()
                refill = elapsed * self.rate
                self.tokens = min(self.rate, self.tokens + refill)
                self.last_refill = now
            
            # Consume token
            self.tokens -= 1

class ExchangeClient:
    def __init__(self, ...):
        # Rate limiter для каждого endpoint
        self.rate_limiters = {
            "/order/create": RateLimiter(10),  # 10 req/sec
            "/order/query": RateLimiter(50),    # 50 req/sec
        }
    
    async def create_order(self, **params):
        """Create order с rate limiting."""
        # Acquire token (wait if needed)
        await self.rate_limiters["/order/create"].acquire()
        
        # Make request
        return await self._do_request("/order/create", params)
```

**Результат:**
- Token bucket: O(1) check
- Async wait только когда rate limit hit
- No requests rejected (automatically throttled)

#### 4. Database write bottleneck

**Решение: Async background persistence** (как в Фазе 9)

```python
class ExecutionEngine:
    def __init__(self, ...):
        # Queue для async DB writes
        self.db_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        asyncio.create_task(self._db_writer_worker())
    
    async def execute_order(self, ...) -> ExecutionResult:
        """Execute БЕЗ блокировки на DB write."""
        # ... execute logic
        
        # Enqueue для async write (non-blocking)
        await self.db_queue.put(order)
        
        return result
```

**Результат:**
- Non-blocking execution
- Background persistence

---

## 📊 ОБЯЗАТЕЛЬНЫЕ BENCHMARK ТЕСТЫ

```python
@pytest.mark.benchmark
async def test_order_submission_latency():
    """
    Acceptance: <2s p99
    """
    engine = ExecutionEngine(...)
    
    signal = TradingSignal(...)
    
    start = time.time()
    result = await engine.execute_order(signal, Decimal("10000"))
    latency = (time.time() - start)
    
    assert latency < 2.0, f"Submission {latency}s > 2s"

@pytest.mark.benchmark
async def test_smart_routing_latency():
    """
    Acceptance: <500ms
    """
    # ...

@pytest.mark.benchmark
async def test_websocket_fill_latency():
    """
    Acceptance: <100ms от fill до event
    """
    # ...

@pytest.mark.benchmark
async def test_concurrent_orders():
    """
    Acceptance: 10 concurrent orders <10s
    """
    # ...
```

**Acceptance Criteria:**
```
✅ order_submission: <2s p99
✅ smart_routing: <500ms
✅ fill_processing: <100ms
✅ concurrent_orders: 10 orders <10s
✅ retry_success_rate: >90%
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── src/
│   └── execution/
│       ├── __init__.py
│       ├── engine.py                     # ExecutionEngine
│       ├── router.py                     # SmartOrderRouter
│       ├── exchange_client.py            # ExchangeClient base
│       ├── exchanges/
│       │   ├── bybit.py                  # Bybit client
│       │   ├── okx.py                    # OKX client
│       │   └── binance.py                # Binance client
│       ├── order_tracker.py              # OrderStatusTracker
│       ├── rate_limiter.py               # RateLimiter
│       └── models.py                     # Order dataclass
│
└── tests/
    ├── unit/
    │   ├── test_order.py
    │   ├── test_router.py
    │   └── test_rate_limiter.py
    ├── integration/
    │   └── test_execution_engine.py
    └── benchmarks/
        └── bench_execution.py
```

---

## ACCEPTANCE CRITERIA

### Order Execution
- [ ] Multi-exchange (Bybit, OKX, Binance)
- [ ] Limit orders
- [ ] Market orders
- [ ] Retry logic (3 attempts)

### Smart Routing
- [ ] Liquidity check
- [ ] Fee comparison
- [ ] Latency check
- [ ] Best execution

### Quality
- [ ] Slippage control (<0.5%)
- [ ] Fill tracking (partial/complete)
- [ ] Commission tracking
- [ ] Order history

### Performance
- [ ] Submission <2s
- [ ] Routing <500ms
- [ ] Fill processing <100ms

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 10: Execution Layer** готова к реализации! 🚀
