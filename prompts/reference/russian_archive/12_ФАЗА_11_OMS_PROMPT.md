# AI ПРОМТ: ФАЗА 11 - ORDER MANAGEMENT SYSTEM

## КОНТЕКСТ

Вы — Senior Order Management Engineer, специализирующийся на order lifecycle management, order book management, и trading operations.

**Фазы 0-10 завершены.** Доступны:
- Event Bus (Rust + Python) — работает с persistence
- Control Plane (State Machine, Watchdog) — работает
- Config Manager — hot reload, GPG signatures, Vault
- Risk Engine — R-unit sizing, correlation, drawdown
- Market Data Layer — WebSocket, ticks, OHLCV bars, orderbook
- Technical Indicators — 20+ индикаторов, NumPy vectorization
- Signal Generator — торговые стратегии, confidence scoring
- Portfolio Governor — position tracking, P&L, exposure
- Execution Layer — multi-exchange, smart routing, order execution
- Database Layer, Logging, Metrics — готовы

**Текущая задача:** Реализовать production-ready Order Management System с order lifecycle tracking, order cancellation, order modification, reconciliation, и centralized order book.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class OrderManagementSystem:
    """
    Система управления ордерами с полным lifecycle tracking.
    
    Особенности:
    - Centralized order book (все ордера в одном месте)
    - Order lifecycle tracking (PENDING → SUBMITTED → FILLED → SETTLED)
    - Order cancellation (manual + automatic)
    - Order modification (change price/quantity)
    - Orphaned order detection (ордера без parent signal)
    - Order reconciliation (синхронизация с биржами)
    - Audit trail (полная история всех изменений)
    - Order expiration (time-based TTL)
    """
    
    async def submit_order(
        self,
        order: Order,
    ) -> bool:
        """
        Зарегистрировать ордер в OMS перед отправкой на биржу.
        
        Аргументы:
            order: Order объект
        
        Возвращает:
            True если успешно зарегистрирован
        
        Действия:
        1. Validate order (price, quantity, symbol)
        2. Assign internal order_id
        3. Add to order book
        4. Persist to database
        5. Publish ORDER_REGISTERED event
        """
        pass
    
    async def cancel_order(
        self,
        order_id: str,
        reason: str,
    ) -> bool:
        """
        Отменить ордер.
        
        Процесс:
        1. Find order in order book
        2. Check can cancel (not FILLED yet)
        3. Send cancel request to exchange
        4. Update status to CANCELLING
        5. Wait for confirmation
        6. Update status to CANCELLED
        7. Publish ORDER_CANCELLED event
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.info("Ордер зарегистрирован в OMS", order_id="ord_123", symbol="BTC/USDT")
logger.warning("Обнаружен orphaned ордер", order_id="ord_456", age_hours=24)
logger.error("Не удалось отменить ордер", order_id="ord_789", reason="already_filled")
logger.debug("Reconciliation завершена", matched=150, orphaned=2, missing=0)
```

### Примеры замены:

| ❌ Неправильно | ✅ Правильно |
|----------------|--------------|
| "Order registered" | "Ордер зарегистрирован" |
| "Order cancelled" | "Ордер отменен" |
| "Orphaned order" | "Orphaned ордер" |
| "Reconciliation complete" | "Reconciliation завершена" |
| "Order expired" | "Ордер истек" |

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Order Management System (OMS) — центральный регистр ВСЕХ ордеров системы. Отслеживает полный lifecycle от создания до settlement. Управляет cancellation, modification, expiration. Reconciles с биржами для выявления orphaned/missing orders. Предоставляет unified view всех active/historical orders. Ensures audit trail для compliance.

### Входящие зависимости (кто взаимодействует с OMS):

#### 1. **Execution Layer (Фаза 10)** → регистрация ордеров
   - Запрос: `async def register_order(order: Order) -> bool`
   - Частота: перед каждым submission (5-20 раз/день)
   - Действие: Execution регистрирует ордер в OMS перед отправкой на биржу
   - Критичность: HIGH (без регистрации нет tracking)

#### 2. **Execution Layer (Фаза 10)** → обновление статусов
   - Event: Подписка на `ORDER_FILLED`, `ORDER_REJECTED`
   - Частота: при каждом fill/reject
   - Действие: OMS обновляет статус ордера
   - Критичность: HIGH

#### 3. **Strategy Manager (Фаза 14)** → cancellation ордеров
   - Запрос: `async def cancel_order(order_id: str, reason: str) -> bool`
   - Частота: редко (при изменении сигналов или market conditions)
   - Действие: Strategy решает отменить pending ордер
   - Критичность: MEDIUM

#### 4. **Portfolio Governor (Фаза 9)** → query active orders
   - Запрос: `async def get_active_orders(symbol: Optional[str]) -> List[Order]`
   - Частота: по запросу (для exposure calculation)
   - Действие: Portfolio проверяет pending orders при расчете exposure
   - Критичность: MEDIUM

#### 5. **Risk Engine (Фаза 5)** → emergency cancel all
   - Запрос: `async def cancel_all_orders(reason: str) -> int`
   - Частота: очень редко (kill switch)
   - Действие: Cancel ALL pending orders немедленно
   - Критичность: CRITICAL

#### 6. **Config Manager (Фаза 4)** → hot reload OMS settings
   - Event: `CONFIG_UPDATED` (order_ttl, reconciliation_interval)
   - Частота: редко
   - Действие: OMS обновляет параметры
   - Критичность: LOW

### Исходящие зависимости (что публикует OMS):

#### 1. → Event Bus (Фаза 3)
   - **Event: `ORDER_REGISTERED`** (приоритет: NORMAL)
     - Payload:
       ```json
       {
         "order_id": "ord_uuid",
         "symbol": "BTC/USDT",
         "side": "BUY",
         "quantity": 0.5,
         "price": 50000,
         "registered_at": 1704067200000000
       }
       ```
     - Подписчики: Observability, Audit

   - **Event: `ORDER_CANCELLED`** (приоритет: HIGH)
     - Payload: `{"order_id": "...", "reason": "manual_cancel", "cancelled_at": ...}`
     - Подписчики: Execution Layer (для cleanup), Portfolio Governor

   - **Event: `ORPHANED_ORDER_DETECTED`** (приоритет: CRITICAL)
     - Payload: `{"order_id": "...", "exchange": "bybit", "age_hours": 24, "action": "auto_cancel"}`
     - Подписчики: Observability, Operations team

   - **Event: `RECONCILIATION_COMPLETED`** (приоритет: NORMAL)
     - Payload: `{"matched": 150, "orphaned": 2, "missing": 0, "duration_ms": 1500}`
     - Подписчики: Observability

#### 2. → PostgreSQL (для order history + audit trail)
   - **Table: `orders`** (уже создана в Фазе 10, используется OMS)
   
   - **Table: `order_events`** (audit trail)
     ```sql
     CREATE TABLE order_events (
         event_id SERIAL PRIMARY KEY,
         timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
         
         order_id VARCHAR(50) NOT NULL,
         event_type VARCHAR(50) NOT NULL,
         -- REGISTERED, SUBMITTED, FILLED, PARTIALLY_FILLED, CANCELLED, MODIFIED
         
         previous_status VARCHAR(20),
         new_status VARCHAR(20),
         
         actor VARCHAR(100),  -- Who/what triggered event
         reason TEXT,
         
         metadata JSONB
     );
     
     CREATE INDEX idx_order_events_order ON order_events(order_id, timestamp DESC);
     CREATE INDEX idx_order_events_type ON order_events(event_type, timestamp DESC);
     ```

#### 3. → Redis (для fast order lookup)
   - **Key: `oms:order:{order_id}`** → JSON order data
   - **Key: `oms:orders:active`** → Set of active order_ids
   - **Key: `oms:orders:pending`** → Set of pending order_ids
   - **Key: `oms:orders:by_symbol:{symbol}`** → Set of order_ids для symbol
   - **TTL:** Permanent для active, 7 дней для completed

#### 4. → Execution Layer (для cancellation requests)
   - Запрос: `async def cancel_exchange_order(order_id: str, exchange: str) -> bool`
   - Действие: OMS просит Execution отменить ордер на бирже

#### 5. → Metrics (Prometheus)
   - Метрики: `oms_orders_total`, `oms_orphaned_orders`, `oms_reconciliation_duration`

### Контракты данных:

#### OrderEvent:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

class OrderEventType(str, Enum):
    """Типы событий ордера."""
    REGISTERED = "REGISTERED"           # Зарегистрирован в OMS
    SUBMITTED = "SUBMITTED"             # Отправлен на биржу
    ACCEPTED = "ACCEPTED"               # Принят биржей
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Частично исполнен
    FILLED = "FILLED"                   # Полностью исполнен
    CANCELLED = "CANCELLED"             # Отменен
    REJECTED = "REJECTED"               # Отклонен
    MODIFIED = "MODIFIED"               # Изменен
    EXPIRED = "EXPIRED"                 # Истек

@dataclass
class OrderEvent:
    """Событие в lifecycle ордера."""
    
    event_id: Optional[int] = None  # DB auto-increment
    timestamp: datetime = None
    
    order_id: str
    event_type: OrderEventType
    
    previous_status: Optional[OrderStatus] = None
    new_status: Optional[OrderStatus] = None
    
    actor: Optional[str] = None  # "strategy_manager", "operator_john", "auto_expiry"
    reason: Optional[str] = None
    
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
```

#### OrderBook (centralized):

```python
class OrderBook:
    """
    Centralized order book (все ордера системы).
    
    In-memory + Redis + PostgreSQL persistence.
    """
    
    def __init__(self):
        # In-memory index для fast lookup
        self._orders: Dict[str, Order] = {}
        
        # Index по статусу
        self._by_status: Dict[OrderStatus, Set[str]] = {
            status: set() for status in OrderStatus
        }
        
        # Index по symbol
        self._by_symbol: Dict[str, Set[str]] = {}
        
        # Index по exchange
        self._by_exchange: Dict[str, Set[str]] = {}
    
    def add_order(self, order: Order):
        """Добавить ордер в order book."""
        self._orders[order.order_id] = order
        self._by_status[order.status].add(order.order_id)
        
        if order.symbol not in self._by_symbol:
            self._by_symbol[order.symbol] = set()
        self._by_symbol[order.symbol].add(order.order_id)
        
        if order.exchange not in self._by_exchange:
            self._by_exchange[order.exchange] = set()
        self._by_exchange[order.exchange].add(order.order_id)
    
    def update_order_status(
        self,
        order_id: str,
        new_status: OrderStatus,
    ):
        """Обновить статус ордера."""
        order = self._orders.get(order_id)
        if not order:
            return
        
        # Remove from old status index
        self._by_status[order.status].discard(order_id)
        
        # Update
        order.status = new_status
        
        # Add to new status index
        self._by_status[new_status].add(order_id)
    
    def get_active_orders(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
    ) -> List[Order]:
        """
        Получить активные ордера.
        
        Активные = PENDING + SUBMITTED + PARTIALLY_FILLED
        """
        active_statuses = {
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
        }
        
        active_ids = set()
        for status in active_statuses:
            active_ids.update(self._by_status[status])
        
        # Filter по symbol
        if symbol:
            symbol_ids = self._by_symbol.get(symbol, set())
            active_ids = active_ids.intersection(symbol_ids)
        
        # Filter по exchange
        if exchange:
            exchange_ids = self._by_exchange.get(exchange, set())
            active_ids = active_ids.intersection(exchange_ids)
        
        return [self._orders[oid] for oid in active_ids]
```

### Sequence Diagram (Order Lifecycle in OMS):

```
[Execution Layer] ──register_order──> [OMS]
                                        |
                            [Add to Order Book]
                            in-memory + Redis + DB
                                        |
                                        v
                            [ORDER_REGISTERED event]
                                        |
                                        
[Execution Layer] ──ORDER_SUBMITTED──> [OMS]
                                        |
                            [Update Status: SUBMITTED]
                                        |
                                        v
                            [Record OrderEvent]
                            audit trail
                                        
[Exchange] ──fill notification──> [Execution] ──ORDER_FILLED──> [OMS]
                                                                    |
                                                [Update Status: FILLED]
                                                [Calculate fill metrics]
                                                                    |
                                                                    v
                                                [ORDER_FILLED event to subscribers]
                                                
[Strategy Manager] ──cancel_order──> [OMS]
                                        |
                            [Check can cancel]
                            not FILLED yet?
                                        |
                            ┌───────────┴───────────┐
                            v                       v
                        ✅ OK                   ❌ ALREADY FILLED
                            |                       |
                [Request Execution]         [Return error]
                to cancel on exchange
                            |
                            v
                [Update Status: CANCELLING]
                            |
                [Wait for confirmation]
                            |
                            v
                [Update Status: CANCELLED]
                            |
                            v
                [ORDER_CANCELLED event]
```

### Обработка ошибок интеграции:

#### 1. Orphaned order detection:

```python
class OrderManagementSystem:
    async def detect_orphaned_orders(self):
        """
        Обнаружить orphaned ордера (без parent signal или слишком старые).
        
        Критерии orphaned:
        - Order PENDING > 24 часа
        - Order SUBMITTED без fills > 24 часа
        - Order без signal_id
        """
        now = datetime.now(timezone.utc)
        
        # Получить все active orders
        active_orders = self.order_book.get_active_orders()
        
        orphaned = []
        
        for order in active_orders:
            # Check age
            age = (now - order.created_at).total_seconds() / 3600  # hours
            
            if age > 24:
                logger.warning(
                    "Обнаружен orphaned ордер",
                    order_id=order.order_id,
                    status=order.status.value,
                    age_hours=age,
                    symbol=order.symbol,
                )
                
                orphaned.append(order)
                
                # Публиковать event
                await self.event_bus.publish(Event(
                    event_type="ORPHANED_ORDER_DETECTED",
                    priority=Priority.Critical,
                    source="oms",
                    payload={
                        "order_id": order.order_id,
                        "exchange": order.exchange,
                        "age_hours": age,
                        "status": order.status.value,
                    },
                ))
                
                # Auto-cancel (если настроено)
                if self.config.auto_cancel_orphaned:
                    await self.cancel_order(
                        order.order_id,
                        reason=f"orphaned_{age:.1f}h",
                    )
        
        # Метрика
        self.metrics.orphaned_orders_total.set(len(orphaned))
        
        return orphaned
```

**Orphaned detection policy:**
- Age > 24 часа → orphaned
- Auto-cancel: configurable
- CRITICAL event публикуется

#### 2. Order reconciliation с биржами:

```python
class OrderManagementSystem:
    async def reconcile_with_exchange(
        self,
        exchange: str,
    ):
        """
        Reconcile OMS order book с биржей.
        
        Процесс:
        1. Получить все active orders от биржи
        2. Сравнить с OMS order book
        3. Найти discrepancies (missing, orphaned)
        4. Sync статусы
        """
        logger.info("Начало reconciliation", exchange=exchange)
        
        start = time.time()
        
        # 1. Получить active orders от биржи
        exchange_orders = await self.execution_layer.get_exchange_orders(exchange)
        exchange_order_ids = {o["exchange_order_id"] for o in exchange_orders}
        
        # 2. Получить OMS orders для этой биржи
        oms_orders = self.order_book.get_active_orders(exchange=exchange)
        oms_order_ids = {o.exchange_order_id for o in oms_orders if o.exchange_order_id}
        
        # 3. Find discrepancies
        
        # Missing in OMS (ордера на бирже, но не в OMS)
        missing_in_oms = exchange_order_ids - oms_order_ids
        
        if missing_in_oms:
            logger.error(
                "Найдены ордера на бирже, отсутствующие в OMS",
                count=len(missing_in_oms),
                exchange=exchange,
                orders=list(missing_in_oms)[:5],  # Первые 5
            )
        
        # Orphaned in OMS (ордера в OMS, но не на бирже)
        orphaned_in_oms = oms_order_ids - exchange_order_ids
        
        if orphaned_in_oms:
            logger.warning(
                "Найдены orphaned ордера в OMS",
                count=len(orphaned_in_oms),
                exchange=exchange,
            )
            
            # Update статусы на CANCELLED (они уже не на бирже)
            for order in oms_orders:
                if order.exchange_order_id in orphaned_in_oms:
                    self.order_book.update_order_status(
                        order.order_id,
                        OrderStatus.CANCELLED,
                    )
                    
                    # Record event
                    await self._record_event(
                        order.order_id,
                        OrderEventType.CANCELLED,
                        actor="reconciliation",
                        reason="not_on_exchange",
                    )
        
        # Matched orders
        matched = exchange_order_ids.intersection(oms_order_ids)
        
        duration = (time.time() - start) * 1000  # ms
        
        logger.info(
            "Reconciliation завершена",
            exchange=exchange,
            matched=len(matched),
            missing=len(missing_in_oms),
            orphaned=len(orphaned_in_oms),
            duration_ms=duration,
        )
        
        # Публиковать event
        await self.event_bus.publish(Event(
            event_type="RECONCILIATION_COMPLETED",
            priority=Priority.Normal,
            source="oms",
            payload={
                "exchange": exchange,
                "matched": len(matched),
                "missing": len(missing_in_oms),
                "orphaned": len(orphaned_in_oms),
                "duration_ms": duration,
            },
        ))
        
        # Метрика
        self.metrics.reconciliation_duration_seconds.observe(duration / 1000)
```

**Reconciliation policy:**
- Frequency: каждые 15 минут (configurable)
- Missing in OMS: CRITICAL (alert operations)
- Orphaned in OMS: auto-update status to CANCELLED
- Matched: verify статусы match

#### 3. Cancel already filled order:

```python
class OrderManagementSystem:
    async def cancel_order(
        self,
        order_id: str,
        reason: str,
    ) -> bool:
        """Cancel с проверкой можно ли отменить."""
        # Получить ордер
        order = self.order_book._orders.get(order_id)
        
        if not order:
            logger.error("Ордер не найден для cancellation", order_id=order_id)
            return False
        
        # Проверить можно ли отменить
        if order.status in {OrderStatus.FILLED, OrderStatus.CANCELLED}:
            logger.warning(
                "Невозможно отменить ордер",
                order_id=order_id,
                status=order.status.value,
                reason="already_terminal_status",
            )
            return False
        
        # Request cancellation от Execution Layer
        try:
            success = await self.execution_layer.cancel_exchange_order(
                order.order_id,
                order.exchange,
            )
            
            if success:
                # Update status
                self.order_book.update_order_status(
                    order_id,
                    OrderStatus.CANCELLED,
                )
                
                # Record event
                await self._record_event(
                    order_id,
                    OrderEventType.CANCELLED,
                    actor="manual" if reason.startswith("manual") else "auto",
                    reason=reason,
                )
                
                # Публиковать event
                await self.event_bus.publish(Event(
                    event_type="ORDER_CANCELLED",
                    priority=Priority.High,
                    source="oms",
                    payload={
                        "order_id": order_id,
                        "reason": reason,
                        "cancelled_at": datetime.now(timezone.utc).isoformat(),
                    },
                ))
                
                return True
            
        except Exception as e:
            logger.error(
                "Ошибка cancellation ордера",
                order_id=order_id,
                error=str(e),
            )
        
        return False
```

**Cancellation handling:**
- Check можно ли отменить (не FILLED/CANCELLED)
- Request от Execution Layer
- Update status + record event
- Publish ORDER_CANCELLED

### Мониторинг интеграций:

#### Метрики OMS:

```python
# Order tracking
oms_orders_total{status}  # gauge: current count
oms_orders_registered_total{symbol, exchange}
oms_orders_cancelled_total{reason}

# Order lifecycle
order_lifecycle_duration_seconds{outcome}  # histogram: REGISTERED → FILLED
order_pending_duration_seconds{}  # histogram: time in PENDING

# Orphaned orders
oms_orphaned_orders_total{}  # gauge
oms_orphaned_orders_detected_total{age_range}

# Reconciliation
oms_reconciliation_duration_seconds{exchange}
oms_reconciliation_discrepancies_total{type}  # type: missing, orphaned

# Audit
oms_order_events_total{event_type}
```

#### Alerts:

**Critical (PagerDuty):**
- `oms_orphaned_orders_total` > 5
- `oms_reconciliation_discrepancies_total{type="missing"}` > 0
- `order_pending_duration_seconds{p95}` > 3600 (1 час)

**Warning (Telegram):**
- `oms_orders_cancelled_total{reason!="manual"}` rate > 10/день
- `oms_reconciliation_duration_seconds` > 10 секунд

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 11

### Order Management System:

**✅ Что реализовано:**
- Centralized order book (in-memory + Redis + PostgreSQL)
- Order lifecycle tracking (full audit trail)
- Order cancellation (manual + automatic)
- Orphaned order detection (age-based)
- Order reconciliation (sync с биржами)
- Order expiration (TTL-based)
- Multi-index lookup (by status, symbol, exchange)

**❌ Что НЕ реализовано:**
- Order modification (change price/quantity while active)
- Complex order types (OCO, Bracket, Trailing stop)
- Order routing optimization (multi-leg orders)
- Pre-trade compliance checks
- Post-trade allocation
- Order netting/aggregation

**⚠️ ВАЖНО:**
```markdown
OMS отслеживает simple orders (LIMIT, MARKET, STOP).
Для complex orders требуется:
- OCO (One-Cancels-Other)
- Bracket orders (entry + SL + TP)
- Trailing stops
- Фаза 20: Advanced Order Types

Order modification НЕ поддерживается.
Для изменения ордера требуется:
- Cancel старый
- Submit новый
Или Фаза 20: Order Modification Engine

Reconciliation — периодическая (15 минут).
Для real-time sync требуется:
- WebSocket order updates от всех бирж
- Event-driven reconciliation
```

### Production Readiness Matrix:

| Компонент | После Фазы 11 | Production Ready |
|-----------|--------------|------------------|
| Order Book | ✅ Ready | ✅ Ready |
| Lifecycle Tracking | ✅ Ready | ✅ Ready |
| Cancellation | ✅ Ready | ✅ Ready |
| Orphaned Detection | ✅ Ready | ✅ Ready |
| Reconciliation | ✅ Ready (periodic) | ⚠️ Real-time для advanced |
| Audit Trail | ✅ Ready | ✅ Ready |

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ И МАСШТАБИРУЕМОСТЬ

### Критические требования:

```
Операция                         Latency Target    Частота
────────────────────────────────────────────────────────────────────
register_order()                 <50ms             5-20 раз/день
cancel_order()                   <100ms            редко
get_active_orders()              <10ms             по запросу
update_order_status()            <10ms             при каждом fill
detect_orphaned_orders()         <5s               каждый час
reconcile_with_exchange()        <10s              каждые 15 минут
────────────────────────────────────────────────────────────────────
```

### Ожидаемая нагрузка:

```
Component                 Operations/sec    CPU Impact    Memory Impact
─────────────────────────────────────────────────────────────────────
Order registration        0.01-0.1/sec      Low           Low
Status updates            0.1-1/sec         Low           Low (in-place)
Active order queries      0.1-1/sec         Low           Low (indexed)
Cancellations             0.01-0.05/sec     Low           Low
Orphaned detection        0.0003/sec        Low           Low (background)
Reconciliation            0.001/sec         Medium        Medium
─────────────────────────────────────────────────────────────────────
TOTAL                     ~2 ops/sec        Low           ~20 MB
```

### Критические узкие места:

#### 1. Order book lookup latency

**Проблема:** Linear search через все ордера медленно.

**Решение: Multi-index in-memory structure**

```python
class OrderBook:
    """Order book с быстрым lookup."""
    
    def __init__(self):
        # Primary index
        self._orders: Dict[str, Order] = {}
        
        # Secondary indexes для fast filtering
        self._by_status: Dict[OrderStatus, Set[str]] = defaultdict(set)
        self._by_symbol: Dict[str, Set[str]] = defaultdict(set)
        self._by_exchange: Dict[str, Set[str]] = defaultdict(set)
    
    def get_active_orders(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
    ) -> List[Order]:
        """
        Fast lookup с indexes.
        
        Complexity: O(1) для каждого index, O(N) только для final list construction.
        """
        # Start с active statuses
        active_ids = set()
        for status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]:
            active_ids.update(self._by_status[status])
        
        # Filter по symbol (если нужно)
        if symbol:
            active_ids = active_ids.intersection(self._by_symbol[symbol])
        
        # Filter по exchange (если нужно)
        if exchange:
            active_ids = active_ids.intersection(self._by_exchange[exchange])
        
        # Construct list (только для filtered IDs)
        return [self._orders[oid] for oid in active_ids]
```

**Результат:**
- Index lookup: O(1)
- Set intersection: O(min(len(set1), len(set2)))
- Total: <1ms для 1000+ orders

#### 2. PostgreSQL audit trail writes

**Решение: Background batch writes**

```python
class OrderManagementSystem:
    def __init__(self, ...):
        # Queue для audit events
        self.audit_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        asyncio.create_task(self._audit_writer_worker())
    
    async def _record_event(
        self,
        order_id: str,
        event_type: OrderEventType,
        **kwargs,
    ):
        """Record event БЕЗ блокировки."""
        event = OrderEvent(
            order_id=order_id,
            event_type=event_type,
            **kwargs,
        )
        
        # Enqueue (non-blocking)
        await self.audit_queue.put(event)
    
    async def _audit_writer_worker(self):
        """Background worker для batch audit writes."""
        batch = []
        
        while True:
            try:
                # Collect batch
                while len(batch) < 100:
                    event = await asyncio.wait_for(
                        self.audit_queue.get(),
                        timeout=1.0,
                    )
                    batch.append(event)
                
                # Batch INSERT
                await self._batch_insert_events(batch)
                batch.clear()
                
            except asyncio.TimeoutError:
                # Flush partial batch
                if batch:
                    await self._batch_insert_events(batch)
                    batch.clear()
```

**Результат:**
- Non-blocking event recording
- Batch writes: 10x faster

#### 3. Reconciliation performance

**Решение: Parallel exchange queries**

```python
class OrderManagementSystem:
    async def reconcile_all_exchanges(self):
        """Reconcile со всеми биржами параллельно."""
        exchanges = self.config.get_enabled_exchanges()
        
        # Parallel reconciliation
        tasks = [
            self.reconcile_with_exchange(exchange)
            for exchange in exchanges
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        for exchange, result in zip(exchanges, results):
            if isinstance(result, Exception):
                logger.error(
                    "Reconciliation failed",
                    exchange=exchange,
                    error=str(result),
                )
```

**Результат:**
- 3 биржи: ~3 секунды вместо ~9 секунд

---

## 📊 ОБЯЗАТЕЛЬНЫЕ BENCHMARK ТЕСТЫ

```python
@pytest.mark.benchmark
async def test_order_registration_latency():
    """
    Acceptance: <50ms
    """
    oms = OrderManagementSystem(...)
    order = Order(...)
    
    start = time.time()
    await oms.register_order(order)
    latency = (time.time() - start) * 1000
    
    assert latency < 50, f"Registration {latency}ms > 50ms"

@pytest.mark.benchmark
async def test_active_orders_lookup():
    """
    Acceptance: <10ms для 1000 orders
    """
    oms = OrderManagementSystem(...)
    
    # Add 1000 orders
    for i in range(1000):
        order = Order(...)
        oms.order_book.add_order(order)
    
    start = time.time()
    active = oms.order_book.get_active_orders(symbol="BTC/USDT")
    latency = (time.time() - start) * 1000
    
    assert latency < 10, f"Lookup {latency}ms > 10ms"

@pytest.mark.benchmark
async def test_reconciliation_performance():
    """
    Acceptance: 3 exchanges <10s
    """
    # ...
```

**Acceptance Criteria:**
```
✅ order_registration: <50ms
✅ active_orders_lookup: <10ms (1000 orders)
✅ order_cancellation: <100ms
✅ orphaned_detection: <5s (1000 orders)
✅ reconciliation: <10s (3 exchanges)
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── src/
│   └── oms/
│       ├── __init__.py
│       ├── system.py                     # OrderManagementSystem
│       ├── order_book.py                 # OrderBook
│       ├── reconciliation.py             # Reconciliation
│       ├── orphaned_detector.py          # Orphaned detection
│       └── models.py                     # OrderEvent
│
└── tests/
    ├── unit/
    │   ├── test_order_book.py
    │   ├── test_reconciliation.py
    │   └── test_orphaned_detection.py
    ├── integration/
    │   └── test_oms.py
    └── benchmarks/
        └── bench_oms.py
```

---

## ACCEPTANCE CRITERIA

### Order Book
- [ ] Centralized order book
- [ ] Multi-index lookup
- [ ] Fast queries (<10ms)

### Lifecycle Tracking
- [ ] Full audit trail
- [ ] Order events
- [ ] Status transitions

### Cancellation
- [ ] Manual cancel
- [ ] Auto cancel (orphaned)
- [ ] Bulk cancel

### Reconciliation
- [ ] Periodic (15min)
- [ ] Find discrepancies
- [ ] Auto-sync

### Performance
- [ ] Registration <50ms
- [ ] Lookup <10ms
- [ ] Reconciliation <10s

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 11: Order Management System** готова к реализации! 🚀
