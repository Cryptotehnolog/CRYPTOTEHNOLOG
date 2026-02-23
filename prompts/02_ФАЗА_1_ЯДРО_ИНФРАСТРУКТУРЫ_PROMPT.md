# AI ПРОМТ: ФАЗА 1 - ЯДРО ИНФРАСТРУКТУРЫ

## КОНТЕКСТ

Вы — Senior Systems Architect и Rust/Python expert, специализирующийся на высокопроизводительных торговых системах.

**Фаза 0 завершена.** Доступны:
- Python 3.11+ виртуальное окружение активировано
- Rust 1.75+ установлен (cargo, rustc)
- Docker инфраструктура запущена (PostgreSQL, Redis, Vault)
- Структура проекта CRYPTOTEHNOLOG создана
- Git репозиторий инициализирован (v1.0.0)

**Текущая задача:** Реализовать фундаментальные инфраструктурные компоненты (Event Bus, Logging, Database, Metrics, Health Checks).

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Правила русификации:

#### 1. Rust комментарии — ТОЛЬКО русский

```rust
/// Событие в системе
/// 
/// Все события имеют уникальный ID, тип и полезную нагрузку.
pub struct Event {
    /// Уникальный идентификатор события
    pub id: String,
    /// Тип события (например, "TRADE_SIGNAL")
    pub event_type: String,
}

impl Event {
    /// Создать новое событие
    /// 
    /// # Аргументы
    /// * `event_type` - Тип события
    /// * `source` - Источник события
    /// 
    /// # Пример
    /// ```rust
    /// let event = Event::new("TRADE_SIGNAL".into(), "strategy".into());
    /// ```
    pub fn new(event_type: String, source: String) -> Self {
        // Создать UUID для события
        Event {
            id: Uuid::new_v4().to_string(),
            event_type,
            source,
        }
    }
}
```

#### 2. Python docstrings — ТОЛЬКО русский

```python
def connect(self) -> None:
    """
    Подключиться к базе данных.
    
    Аргументы:
        Нет
    
    Raises:
        ConnectionError: Если подключение не удалось
    
    Пример:
        >>> await db.connect()
    """
    pass

class PostgreSQLManager:
    """
    Менеджер подключений к PostgreSQL.
    
    Особенности:
    - Пул соединений
    - Автоматическое переподключение
    - Поддержка транзакций
    """
    pass
```

#### 3. Логи — ТОЛЬКО русский

```python
logger.info("Подключение к базе данных установлено")
logger.error("Ошибка подключения к БД", error=str(e))
logger.warning("Очередь переполнена", queue_size=1000)
logger.debug("Событие опубликовано", event_id=event.id, event_type=event.event_type)
```

#### 4. Ошибки — ТОЛЬКО русский

```python
raise ValueError("Недопустимый переход состояния")
raise ConnectionError("Не удалось подключиться к БД")
raise RuntimeError("Пул соединений не создан")
```

#### 5. Имена переменных/функций — английский (стандарт)

```python
def fetch_trades(self, symbol: str) -> List[Trade]:  # ✅ Имя функции английское
    """Получить список сделок."""                     # ✅ Docstring русский
    pass
```

### Примеры замены:

| ❌ Неправильно | ✅ Правильно |
|----------------|--------------|
| "Connection established" | "Подключение установлено" |
| "Invalid state transition" | "Недопустимый переход состояния" |
| "Event published" | "Событие опубликовано" |
| "Database error" | "Ошибка базы данных" |
| "Queue full" | "Очередь переполнена" |

---

## ЦЕЛЬ ФАЗЫ

Создать production-ready инфраструктурные компоненты:

1. **Event Bus (Rust)** — межкомпонентная коммуникация с priority queues
2. **Structured Logging (Python)** — JSON logging с context propagation
3. **Database Layer (Python)** — PostgreSQL и Redis managers
4. **Metrics Collector (Python)** — system metrics collection
5. **Health Check System (Python)** — component health monitoring

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Event Bus — центральная нервная система CRYPTOTEHNOLOG. Все компоненты общаются через него асинхронно, обеспечивая decoupling и масштабируемость. Logging/Database/Metrics — фундаментальные сервисы, используемые всеми фазами.

### Входящие зависимости (что получает Event Bus):

**От всех компонентов системы (Фазы 2-22):**

1. **State Machine (Фаза 2)** → публикует события изменения состояния
   - События: `STATE_TRANSITION`, `SYSTEM_BOOT`, `SYSTEM_HALT`
   - Payload: `{"from_state": "TRADING", "to_state": "DEGRADED", "trigger": "risk_violation"}`
   - Частота: 1-10 раз/минуту
   - Обработка: fire-and-forget, at-least-once delivery

2. **Risk Engine (Фаза 5)** → публикует нарушения риска
   - События: `RISK_VIOLATION`, `RISK_BUDGET_UPDATE`, `RISK_CHECK_COMPLETED`
   - Payload: `{"violation_type": "position_size", "symbol": "BTC/USDT", "severity": "HIGH"}`
   - Частота: 10-100 раз/сек (в зависимости от торговой активности)
   - Обработка: async, приоритет HIGH для RISK_VIOLATION

3. **Execution Layer (Фаза 10)** → публикует события исполнения
   - События: `ORDER_PLACED`, `ORDER_FILLED`, `ORDER_CANCELLED`, `EXECUTION_ERROR`
   - Payload: `{"order_id": "ord_123", "symbol": "BTC/USDT", "filled_qty": 0.5, "avg_price": 50000.0}`
   - Частота: 50-200 раз/сек (пиковая нагрузка)
   - Обработка: async, приоритет NORMAL

4. **Kill Switch (Фаза 12)** → публикует критические события
   - События: `KILL_SWITCH_TRIGGERED`, `EMERGENCY_SHUTDOWN`
   - Payload: `{"kill_level": "HARD_HALT", "reason": "drawdown_exceeded", "timestamp": 1234567890}`
   - Частота: редко (аварийные ситуации)
   - Обработка: sync (блокирует систему), приоритет CRITICAL

5. **Portfolio Governor (Фаза 9)** → публикует изменения портфеля
   - События: `POSITION_OPENED`, `POSITION_CLOSED`, `POSITION_UPDATED`
   - Payload: `{"symbol": "ETH/USDT", "size_usd": 10000.0, "r_units": 0.02}`
   - Частота: 10-50 раз/сек
   - Обработка: async, приоритет NORMAL

### Исходящие зависимости (что отправляет Event Bus):

**Доставка событий подписчикам:**

1. → **Metrics Collector** (эта же фаза)
   - Подписка: ВСЕ события (wildcard subscription)
   - Действие: подсчет метрик `event_published_total`, `event_delivered_total`
   - Гарантии: best-effort (LOW priority)

2. → **Audit Chain (Фаза 16)**
   - Подписка: критические события (`RISK_VIOLATION`, `STATE_TRANSITION`, `ORDER_FILLED`)
   - Действие: запись в immutable audit log с cryptographic hashing
   - Гарантии: at-least-once, сохранение даже при сбоях

3. → **Observability Dashboard (Фаза 17)**
   - Подписка: `SYSTEM_*`, `HEALTH_CHECK_*`, метрики
   - Действие: обновление real-time дашборда через WebSocket
   - Гарантии: at-most-once (допустима потеря для визуализации)

4. → **Risk Engine (Фаза 5)**
   - Подписка: `ORDER_FILLED`, `POSITION_CLOSED` (для обновления risk budget)
   - Действие: освобождение зарезервированного риска
   - Гарантии: exactly-once (критично для точности риск-учета)

5. → **State Machine (Фаза 2)**
   - Подписка: `RISK_VIOLATION`, `EXECUTION_ERROR`, `HEALTH_CHECK_FAILED`
   - Действие: автоматический переход состояния (TRADING → DEGRADED → HALT)
   - Гарантии: at-least-once, идемпотентная обработка

### Контракты данных:

#### Event Schema (Rust struct + JSON):

```rust
/// Событие в системе
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Event {
    /// Уникальный идентификатор события
    pub id: String,
    
    /// Тип события (например, "TRADE_SIGNAL", "RISK_VIOLATION")
    pub event_type: String,
    
    /// Приоритет события
    pub priority: Priority,
    
    /// Временная метка создания (Unix timestamp в микросекундах)
    pub timestamp: u64,
    
    /// ID корреляции для связывания событий
    pub correlation_id: Option<String>,
    
    /// Источник события (компонент, который создал событие)
    pub source: String,
    
    /// Полезная нагрузка (произвольные данные в JSON)
    pub payload: serde_json::Value,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Priority {
    Critical = 0,  // Kill switches, системные сбои
    High = 1,      // Нарушения риска, критические ошибки
    Normal = 2,    // Торговые сигналы, обычные операции
    Low = 3,       // Метрики, логи, информационные сообщения
}
```

#### JSON Schema Example:

```json
{
  "id": "evt_7f3a9b2c-4d1e-4f8a-9c3b-2e1f4a5b6c7d",
  "event_type": "RISK_VIOLATION",
  "priority": "High",
  "timestamp": 1704067200000000,
  "correlation_id": "req_abc123",
  "source": "risk_engine",
  "payload": {
    "violation_type": "position_size",
    "symbol": "BTC/USDT",
    "limit": 50000.0,
    "attempted": 75000.0,
    "severity": "HIGH",
    "action_taken": "reject_order"
  }
}
```

#### Python Binding API:

```python
from event_bus import PyEventBus

# Создание шины
bus = PyEventBus()

# Публикация события
bus.publish(
    event_type="RISK_VIOLATION",
    source="risk_engine",
    payload={
        "violation_type": "position_size",
        "symbol": "BTC/USDT",
        "severity": "HIGH"
    },
    priority="high",  # опционально, по умолчанию "normal"
    correlation_id="req_123"  # опционально
)

# Подписка на события
subscriber = bus.subscribe("RISK_VIOLATION")
while True:
    event = subscriber.recv()  # blocking
    print(f"Получено событие: {event}")
```

### Sequence Diagram (типичный flow):

```
[Risk Engine] ──check_trade()──> [internal logic]
                                       |
                                       |──create Event(RISK_VIOLATION)
                                       |
                                       V
                              [Event Bus (Rust)]
                                       |
                                       |──prioritize (HIGH)
                                       |──persist to queue
                                       |
                    ┌──────────────────┼──────────────────┐
                    V                  V                  V
            [Metrics Collector]  [Audit Chain]    [State Machine]
                    |                  |                  |
            count violation      hash & store      transition to DEGRADED
                    |                  |                  |
                    V                  V                  V
              [Prometheus]      [PostgreSQL]      [System Controller]
```

### Обработка ошибок интеграции:

#### Event Bus гарантии:

1. **At-least-once delivery:**
   - Событие может быть доставлено несколько раз
   - Подписчики должны быть идемпотентными
   - Redis Streams используется для persistence (Фаза 3)

2. **Backpressure handling:**
   - LOW priority события дропаются при переполнении очереди
   - NORMAL события буферизуются
   - HIGH/CRITICAL события блокируют publisher до освобождения места

3. **Dead Letter Queue:**
   - События, которые не удалось доставить после 3 попыток → DLQ
   - DLQ хранится в Redis Stream: `events:dlq`
   - Replay вручную через операторский интерфейс (Фаза 2)

4. **Subscriber failure:**
   - Если подписчик отключился (channel closed) → метрика `subscribers_disconnected_total`
   - Автоматическая очистка мертвых подписчиков каждые 60 секунд
   - Alert если >10% подписчиков отключились

#### Database Layer обработка ошибок:

1. **Connection pool exhaustion:**
   - Таймаут ожидания соединения: 5 секунд
   - Если пул исчерпан → метрика `db_pool_exhausted_total`
   - Fallback: reject запроса с ошибкой "Database overloaded"

2. **Query timeout:**
   - Все queries с таймаутом 30 секунд (настраиваемо)
   - Slow queries (>1 сек) → логируются в structured log
   - Метрика: `db_query_duration_seconds{query_type, percentile}`

3. **Connection loss:**
   - Автоматический retry: 3 попытки с exponential backoff (1s, 2s, 4s)
   - Если все попытки провалились → переход в DEGRADED режим (Фаза 2)
   - Health check возвращает `unhealthy` до восстановления соединения

### Мониторинг интеграций:

#### Метрики Event Bus:

```python
# Счетчики
event_published_total{source, event_type, priority}
event_delivered_total{event_type, subscriber}
event_dropped_total{reason, priority}  # reason: "queue_full", "subscriber_dead"
subscribers_active{event_type}
subscribers_disconnected_total{event_type, reason}

# Гистограммы
event_publish_latency_seconds{priority, percentile}  # p50, p95, p99
event_delivery_latency_seconds{event_type, percentile}
event_queue_size{priority}

# Gauges
event_bus_health{status}  # 1=healthy, 0=unhealthy
```

#### Метрики Database:

```python
db_connections_active{database}  # PostgreSQL/Redis
db_connections_idle{database}
db_pool_exhausted_total{database}
db_query_duration_seconds{query_type, database, percentile}
db_query_errors_total{database, error_type}
db_health{database, status}  # 1=connected, 0=disconnected
```

#### Alerts:

1. **Critical:**
   - `event_bus_health == 0` для 60 секунд → PagerDuty
   - `db_health{database="postgresql"} == 0` для 30 секунд → PagerDuty

2. **Warning:**
   - `event_dropped_total` rate > 10/sec для 5 минут → Telegram
   - `db_query_duration_seconds{p99} > 5s` для 5 минут → Telegram
   - `subscribers_disconnected_total` > 5 за 1 минуту → Telegram

### Особенности реализации:

#### Event Bus (Rust):

1. **Thread safety:**
   - Arc<RwLock<>> для subscribers map
   - Atomic операции для метрик
   - Tokio async runtime для concurrency

2. **Zero-copy optimization:**
   - Event.payload остается `serde_json::Value` (избегаем лишней сериализации)
   - Clone только при необходимости доставки нескольким подписчикам

3. **Python bindings:**
   - PyO3 для FFI
   - GIL handling для thread safety
   - Async runtime bridge (tokio <-> asyncio)

#### Database Layer (Python):

1. **Connection pooling:**
   - asyncpg для PostgreSQL (native async)
   - redis-py с connection pool для Redis
   - Автоматическое управление lifecycle (acquire/release)

2. **Transactional support:**
   - Context manager для транзакций: `async with db.transaction():`
   - Автоматический rollback при exception
   - Nested transactions через savepoints

3. **Migration support:**
   - Alembic для schema versioning (подготовка в этой фазе)
   - `init_schema()` методы для базовых таблиц

### Тестирование интеграций:

#### Integration Test Plan:

```python
# tests/integration/test_infrastructure.py

async def test_event_bus_to_metrics_flow():
    """Проверить что события попадают в метрики."""
    bus = PyEventBus()
    metrics = MetricsCollector()
    
    # Подписать метрики на все события
    metrics.subscribe_to_bus(bus)
    
    # Опубликовать событие
    bus.publish("TEST_EVENT", "test", {"key": "value"})
    
    # Проверить что метрика увеличилась
    assert metrics.get_metric("event_published_total") == 1

async def test_database_health_check():
    """Проверить что health check детектирует состояние БД."""
    db = PostgreSQLManager(...)
    health = HealthChecker()
    
    # БД доступна
    await db.connect()
    status = await health.check_component("database")
    assert status.healthy == True
    
    # БД недоступна (simulate)
    await db.disconnect()
    status = await health.check_component("database")
    assert status.healthy == False
```

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 1

### Event Bus (без persistence в Фазе 1):

**✅ Что реализовано:**
- In-memory pub/sub с низкой задержкой (<1ms)
- Priority queues (Critical/High/Normal/Low)
- Backpressure handling
- Python bindings через PyO3

**❌ Что НЕ реализовано (будет в Фазе 3):**
- Persistence на диск (Redis Streams)
- Replay capability
- Репликация (single point of failure)
- Гарантия доставки при перезапуске

**⚠️ ВАЖНО:**
```markdown
Event Bus в Фазе 1 — это MVP для тестирования интеграций.
Для production использовать НЕЛЬЗЯ до Фазы 3!

При перезапуске системы:
- Все непрочитанные события теряются
- Подписчики должны переподписаться
- История событий не сохраняется
```

### Production Readiness Matrix:

| Компонент | После Фазы 1 | Production Ready |
|-----------|--------------|------------------|
| Event Bus | ⚠️ Только для dev/testing | ✅ Требует Фазу 3 (Redis Streams) |
| Logging | ✅ Ready | ✅ Ready |
| Database | ✅ Ready | ✅ Ready |
| Metrics | ⚠️ In-memory only | ✅ Требует Фазу 17 (Prometheus) |
| Health Checks | ✅ Ready | ✅ Ready |

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ И МАСШТАБИРУЕМОСТЬ

### Ожидаемая нагрузка:

```
Execution Layer:   50-200 events/сек (пик)
Risk Engine:       10-100 events/сек
Portfolio:         10-50 events/сек
Metrics:           постоянно (LOW priority)
────────────────────────────────────────────
ИТОГО:            ~300 events/сек (пиковая)
```

### Узкие места и оптимизации:

#### 1. Python ↔ Rust bridge bottleneck

**Проблема:** PyO3 сериализация PyDict → JSON → Event медленная при high load.

**Решение:** Реализовать batch API и fast path:

```rust
// src/python_bindings.rs

#[pymethods]
impl PyEventBus {
    /// Опубликовать одно событие (стандартный путь)
    fn publish(&self, event_type: String, source: String, payload: &PyDict) -> PyResult<()> {
        // Сериализация PyDict -> serde_json::Value
        let json_value = pythonize::depythonize(payload)?;
        // ... обычная публикация
    }
    
    /// Опубликовать пакет событий (оптимизация)
    fn publish_batch(&self, events: Vec<PyEvent>) -> PyResult<usize> {
        // Batch processing — обработать все события за один вызов
        // Возвращает количество успешно опубликованных
    }
    
    /// Быстрая публикация с готовым JSON (zero-copy)
    fn publish_fast(&self, event_type: &str, source: &str, json_bytes: &[u8]) -> PyResult<()> {
        // Принять уже сериализованный JSON как bytes
        // Избежать PyDict → JSON conversion
        let json_value: serde_json::Value = serde_json::from_slice(json_bytes)?;
        // ... публикация
    }
}
```

**Когда использовать:**
- `publish()` — для 90% случаев (удобство)
- `publish_batch()` — для массовых операций (>10 событий)
- `publish_fast()` — для high-frequency paths (ORDER_FILLED)

#### 2. Subscriber scalability

**Проблема:** Один медленный subscriber блокирует доставку другим.

**Решение:** Неблокирующая доставка с backpressure:

```rust
impl EventBus {
    pub async fn publish(&self, event: Event) -> usize {
        let subs = self.subscribers.read().await;
        let mut delivered = 0;
        
        if let Some(subscribers) = subs.get(&event.event_type) {
            for sub in subscribers {
                // try_send вместо send — неблокирующий
                match sub.try_send(event.clone()) {
                    Ok(_) => delivered += 1,
                    Err(TrySendError::Full(_)) => {
                        // Очередь подписчика переполнена
                        // Применить backpressure policy
                        if event.priority == Priority::Low {
                            // DROP событие
                            self.metrics.dropped += 1;
                        } else {
                            // Ждать (блокировать publisher)
                            sub.send(event.clone()).await.ok();
                        }
                    }
                    Err(TrySendError::Closed(_)) => {
                        // Подписчик отключился — игнорировать
                        self.metrics.dropped += 1;
                    }
                }
            }
        }
        delivered
    }
}
```

#### 3. Memory pressure при высокой нагрузке

**Решение:** Ограничение размера очередей + мониторинг:

```rust
pub struct EventBus {
    subscribers: Arc<RwLock<HashMap<String, Vec<Subscriber>>>>,
    metrics: Arc<RwLock<BusMetrics>>,
    
    // НОВОЕ: лимиты
    max_queue_size: usize,  // 10_000 событий на подписчика
    max_event_size_bytes: usize,  // 1 MB на событие
}

impl EventBus {
    pub fn new() -> Self {
        EventBus {
            // ...
            max_queue_size: 10_000,
            max_event_size_bytes: 1_048_576,  // 1 MB
        }
    }
    
    pub async fn publish(&self, event: Event) -> Result<usize, PublishError> {
        // Проверить размер события
        let event_size = serde_json::to_vec(&event.payload)?.len();
        if event_size > self.max_event_size_bytes {
            return Err(PublishError::EventTooLarge(event_size));
        }
        
        // ... публикация
    }
}
```

---

## 📊 ОБЯЗАТЕЛЬНЫЕ BENCHMARK ТЕСТЫ

### Добавить в tests/benchmarks/:

**tests/benchmarks/bench_event_bus.rs:**
```rust
use criterion::{black_box, criterion_group, criterion_main, Criterion};
use event_bus::{EventBus, Event, Priority};
use serde_json::json;

fn benchmark_publish_single(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();
    let bus = EventBus::new();
    
    c.bench_function("publish_single_event", |b| {
        b.to_async(&runtime).iter(|| async {
            let event = Event::new(
                "BENCHMARK".to_string(),
                "bench".to_string(),
                json!({"test": "data"}),
            );
            bus.publish(black_box(event)).await;
        });
    });
}

fn benchmark_publish_throughput(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();
    let bus = EventBus::new();
    
    c.bench_function("publish_1000_events", |b| {
        b.to_async(&runtime).iter(|| async {
            for _ in 0..1000 {
                let event = Event::new(
                    "BENCHMARK".to_string(),
                    "bench".to_string(),
                    json!({"i": 1}),
                );
                bus.publish(event).await;
            }
        });
    });
}

fn benchmark_priority_ordering(c: &mut Criterion) {
    // Проверить что Critical события обрабатываются первыми
    // даже если опубликованы позже Low событий
}

criterion_group!(
    benches,
    benchmark_publish_single,
    benchmark_publish_throughput,
    benchmark_priority_ordering
);
criterion_main!(benches);
```

**Acceptance Criteria для benchmarks:**
```
✅ publish_single_event: median < 1ms, p99 < 5ms
✅ publish_1000_events: < 1 second total (1000 events/sec)
✅ priority_ordering: Critical всегда перед Low
✅ memory_usage: < 100 MB при 10K событий в очереди
```

**tests/integration/test_event_bus_load.py:**
```python
import pytest
import asyncio
from event_bus import PyEventBus

@pytest.mark.benchmark
async def test_event_bus_high_load():
    """
    Проверить обработку 1000 событий/сек без деградации.
    """
    bus = PyEventBus()
    subscriber = bus.subscribe("LOAD_TEST")
    
    # Публиковать 1000 событий параллельно
    start = asyncio.get_event_loop().time()
    tasks = []
    for i in range(1000):
        task = asyncio.create_task(
            bus.publish("LOAD_TEST", "bench", {"index": i})
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    end = asyncio.get_event_loop().time()
    
    # Assertions
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) < 10, f"Слишком много ошибок: {len(errors)}/1000"
    
    duration = end - start
    assert duration < 2.0, f"Публикация заняла {duration}s (ожидается <2s)"
    
    throughput = 1000 / duration
    assert throughput > 500, f"Throughput {throughput} events/sec (ожидается >500)"

@pytest.mark.benchmark
async def test_event_bus_backpressure():
    """
    Проверить что backpressure корректно отбрасывает LOW события.
    """
    bus = PyEventBus()
    # НЕ создавать subscriber → очередь переполнится
    
    # Публиковать 1000 LOW priority событий
    for i in range(1000):
        await bus.publish("TEST", "bench", {"i": i}, priority="low")
    
    metrics = bus.get_metrics()
    # Некоторые должны быть dropped из-за backpressure
    assert metrics["dropped"] > 0, "Backpressure не сработал"
```

---

## 🔧 STUBS ДЛЯ БУДУЩИХ КОМПОНЕНТОВ

**ОБЯЗАТЕЛЬНО создать src/core/stubs.py:**

```python
"""
Заглушки для компонентов из будущих фаз.

Используются для:
1. Тестирования Фаз 1-2 без зависимостей
2. Документирования интерфейсов
3. Постепенной миграции (stub → real implementation)
"""

from typing import Optional, Dict, Any, List
from decimal import Decimal
from dataclasses import dataclass

from src.core.logger import get_logger

logger = get_logger("Stubs")


# ============================================================================
# ФАЗА 5: RISK ENGINE
# ============================================================================

@dataclass
class RiskCheckResult:
    """Результат проверки риска."""
    allowed: bool
    reason: Optional[str]
    risk_score: float


class RiskEngineStub:
    """
    Заглушка Risk Engine (реализация в Фазе 5).
    
    В production это будет полноценный компонент с:
    - R-unit system
    - Position size validation
    - Drawdown monitoring
    - Correlation checks
    """
    
    def __init__(self):
        logger.warning(
            "⚠️  Используется ЗАГЛУШКА RiskEngine",
            real_implementation="Фаза 5"
        )
    
    async def check_trade(
        self,
        symbol: str,
        size_usd: float,
        side: str,
    ) -> RiskCheckResult:
        """
        Проверить допустимость сделки.
        
        ЗАГЛУШКА: Всегда возвращает allowed=True.
        """
        logger.debug(
            "RiskEngine stub: проверка пропущена",
            symbol=symbol,
            size_usd=size_usd,
        )
        
        return RiskCheckResult(
            allowed=True,
            reason="stub_implementation",
            risk_score=0.0,
        )
    
    async def pause_trading(self) -> bool:
        """Приостановить торговлю."""
        logger.warning("RiskEngine stub: pause_trading() вызван, но ничего не делает")
        return True
    
    async def resume_trading(self) -> bool:
        """Возобновить торговлю."""
        logger.warning("RiskEngine stub: resume_trading() вызван")
        return True


# ============================================================================
# ФАЗА 10: EXECUTION LAYER
# ============================================================================

@dataclass
class Order:
    """Ордер на бирже."""
    order_id: str
    symbol: str
    side: str
    size: float
    price: Optional[float]


class ExecutionLayerStub:
    """
    Заглушка Execution Layer (реализация в Фазе 10).
    """
    
    def __init__(self):
        logger.warning(
            "⚠️  Используется ЗАГЛУШКА ExecutionLayer",
            real_implementation="Фаза 10"
        )
    
    async def cancel_all_orders(self) -> List[str]:
        """Отменить все активные ордера."""
        logger.warning("ExecutionLayer stub: cancel_all_orders() вызван")
        return []  # Пустой список отмененных ордеров
    
    async def execute_order(self, order: Order) -> str:
        """Отправить ордер на биржу."""
        logger.warning(
            "ExecutionLayer stub: ордер НЕ отправлен на биржу",
            order_id=order.order_id,
        )
        return order.order_id


# ============================================================================
# ФАЗА 14: STRATEGY MANAGER
# ============================================================================

class StrategyManagerStub:
    """
    Заглушка Strategy Manager (реализация в Фазе 14).
    """
    
    def __init__(self):
        logger.warning(
            "⚠️  Используется ЗАГЛУШКА StrategyManager",
            real_implementation="Фаза 14"
        )
    
    async def disable_all_strategies(self) -> int:
        """Отключить все торговые стратегии."""
        logger.warning("StrategyManager stub: disable_all_strategies() вызван")
        return 0  # Количество отключенных стратегий
    
    async def enable_strategy(self, strategy_name: str) -> bool:
        """Включить стратегию."""
        logger.warning(f"StrategyManager stub: enable_strategy({strategy_name}) вызван")
        return True
```

**Использование в System Controller (Фаза 2):**

```python
# src/core/system_controller.py

from typing import Union

try:
    # Попытка импортировать реальную реализацию
    from src.risk.engine import RiskEngine
    from src.execution.layer import ExecutionLayer
    from src.strategies.manager import StrategyManager
    USE_STUBS = False
except ImportError:
    # Fallback на заглушки
    from src.core.stubs import (
        RiskEngineStub as RiskEngine,
        ExecutionLayerStub as ExecutionLayer,
        StrategyManagerStub as StrategyManager,
    )
    USE_STUBS = True

logger = get_logger("SystemController")

class SystemController:
    def __init__(self, ...):
        # ...
        self.risk_engine = RiskEngine()
        self.execution = ExecutionLayer()
        self.strategies = StrategyManager()
        
        if USE_STUBS:
            logger.warning(
                "⚠️⚠️⚠️  СИСТЕМА ИСПОЛЬЗУЕТ ЗАГЛУШКИ ⚠️⚠️⚠️",
                components=["RiskEngine", "ExecutionLayer", "StrategyManager"],
                note="Для production нужны реальные реализации",
            )
```

---

## ФАЙЛОВАЯ СТРУКТУРА

Создайте следующие файлы с ПОЛНЫМ рабочим кодом:

```
CRYPTOTEHNOLOG/
├── rust_components/
│   └── event_bus/
│       ├── Cargo.toml
│       ├── src/
│       │   ├── lib.rs
│       │   ├── bus.rs
│       │   ├── event.rs
│       │   └── python_bindings.rs
│       ├── tests/
│       │   └── integration_test.rs
│       └── benches/                     # НОВОЕ: бенчмарки
│           └── bench_event_bus.rs
│
├── src/
│   └── core/
│       ├── __init__.py
│       ├── logger.py
│       ├── database.py
│       ├── redis_manager.py
│       ├── metrics.py
│       ├── health.py
│       └── stubs.py                     # НОВОЕ: заглушки для будущих фаз
│
└── tests/
    ├── unit/
    │   ├── test_logging.py             # ★ РАСШИРЕН: тесты для bind_context, LoggerMixin
    │   ├── test_database.py
    │   ├── test_health.py
    │   └── test_stubs.py               # НОВОЕ: тесты заглушек
    ├── integration/
    │   ├── test_infrastructure.py
    │   └── test_event_bus_load.py      # НОВОЕ: нагрузочные тесты
    └── benchmarks/                      # НОВОЕ: Python бенчмарки
        └── bench_python_bindings.py
```

---

## ТРЕБОВАНИЯ

### 1. Event Bus (Rust)

**crates/eventbus/Cargo.toml:**
```toml
[package]
name = "event_bus"
version = "0.1.0"
edition = "2021"

[lib]
name = "event_bus"
crate-type = ["cdylib", "rlib"]

[dependencies]
tokio = { version = "1.35", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
uuid = { version = "1.6", features = ["v4", "serde"] }
pyo3 = { version = "0.20", features = ["extension-module"] }
pythonize = "0.20"

[dev-dependencies]
criterion = { version = "0.5", features = ["async_tokio"] }
tokio-test = "0.4"

[[bench]]
name = "bench_event_bus"
harness = false
```

**src/event.rs:**
Создайте Event struct с:
- id: String (UUID)
- event_type: String
- priority: Priority (enum: Critical, High, Normal, Low)
- timestamp: u64
- correlation_id: Option<String>
- source: String
- payload: serde_json::Value

**ВАЖНО:** Все комментарии в Rust коде на русском:
```rust
/// Событие в системе
pub struct Event {
    /// Уникальный идентификатор
    pub id: String,
}
```

**src/bus.rs:**
Создайте EventBus с:
- `pub async fn subscribe(&self, event_type: &str) -> Receiver<Event>`
- `pub async fn publish(&self, event: Event)`
- `pub async fn get_metrics(&self) -> BusMetrics`

Метрики:
- published: u64
- delivered: u64
- dropped: u64

**src/python_bindings.rs:**
```rust
#[pyclass]
pub struct PyEventBus {
    bus: Arc<Mutex<EventBus>>,
    runtime: Arc<tokio::runtime::Runtime>,
}

#[pymethods]
impl PyEventBus {
    #[new]
    fn new() -> PyResult<Self>;
    
    fn publish(&self, event_type: String, source: String, payload: &PyDict) -> PyResult<()>;
    
    fn get_metrics(&self) -> PyResult<PyObject>;
}

#[pymodule]
fn event_bus(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyEventBus>()?;
    Ok(())
}
```

---

### 2. Structured Logging (Python)

**src/cryptotechnolog/config/logging.py:**

```python
"""
Структурированное логирование
CRYPTOTEHNOLOG v1.1.0

★ УЖЕ СУЩЕСТВУЕТ — РАСШИРИТЬ:
- bind_context(**kwargs) — привязать контекст к логам
- clear_context() — очистить контекст
- get_context() — получить текущий контекст
- LoggerMixin — миксин для классов
"""

# Добавить в существующий модуль:

from contextvars import ContextVar
from typing import Any

_context: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})


def bind_context(**context: Any) -> None:
    """
    Привязать контекстные данные ко всем последующим логам.
    
    Аргументы:
        **context: Пары ключ-значение для контекста
    """
    current = _context.get()
    current.update(context)
    _context.set(current)


def clear_context() -> None:
    """Очистить контекстные данные."""
    _context.set({})


def get_context() -> dict[str, Any]:
    """Получить текущий контекст."""
    return _context.get()


class LoggerMixin:
    """Миксин для классов с логгером."""
    
    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        if not hasattr(self, "_logger"):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger
```

**ВАЖНО:** Все логи на русском:
```python
logger.info("Подключение установлено")
logger.error("Ошибка подключения", error=str(e))
```

---

### 3. Database Layer (Python)

**src/core/database.py:**

```python
"""
Слой работы с PostgreSQL
CRYPTOTEHNOLOG v1.1.0
"""

import asyncpg
from contextlib import asynccontextmanager

class PostgreSQLManager:
    """
    Менеджер подключений к PostgreSQL.
    
    Особенности:
    - Пул соединений
    - Async операции
    - Поддержка транзакций
    """
    
    def __init__(self, connection_string: str):
        """
        Аргументы:
            connection_string: Строка подключения PostgreSQL
        """
        # РЕАЛИЗУЙТЕ:
        # 1. Сохранить connection_string
        # 2. Инициализировать self.pool = None
    
    async def connect(self) -> None:
        """
        Установить соединение с БД.
        
        Raises:
            ConnectionError: Если подключение не удалось
        """
        # РЕАЛИЗУЙТЕ:
        # 1. Создать пул: asyncpg.create_pool(min_size=10, max_size=20)
        # 2. Логировать: logger.info("Подключение к PostgreSQL установлено")
        # 3. При ошибке: logger.error("Ошибка подключения к PostgreSQL")
    
    async def disconnect(self) -> None:
        """Закрыть соединение."""
        # Закрыть пул и логировать
    
    @asynccontextmanager
    async def transaction(self):
        """
        Контекстный менеджер для транзакций.
        
        Пример:
            async with db.transaction():
                await db.execute("INSERT ...")
        """
        # РЕАЛИЗУЙТЕ через pool.acquire() и conn.transaction()
    
    async def execute(self, query: str, *args) -> str:
        """
        Выполнить SQL команду.
        
        Аргументы:
            query: SQL запрос
            *args: Параметры
        
        Возвращает:
            Статус выполнения
        """
        # РЕАЛИЗУЙТЕ с логированием
    
    async def fetch(self, query: str, *args) -> List:
        """Получить все строки."""
        pass
    
    async def fetchrow(self, query: str, *args) -> Optional:
        """Получить одну строку."""
        pass
    
    async def fetchval(self, query: str, *args) -> Any:
        """Получить одно значение."""
        pass
```

---

### 4. Redis Manager (Python)

**src/core/redis_manager.py:**

```python
"""
Менеджер Redis
CRYPTOTEHNOLOG v1.1.0
"""

import redis.asyncio as aioredis
import json

class RedisManager:
    """
    Менеджер подключений к Redis.
    
    Особенности:
    - Пул соединений
    - Сериализация JSON
    - Поддержка TTL
    """
    
    def __init__(self, redis_url: str):
        """
        Аргументы:
            redis_url: URL Redis (например, "redis://localhost:6379/0")
        """
        pass
    
    async def connect(self) -> None:
        """Установить соединение с Redis."""
        # РЕАЛИЗУЙТЕ:
        # 1. aioredis.from_url()
        # 2. Проверить через ping()
        # 3. logger.info("Redis подключен")
    
    async def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> bool:
        """
        Установить значение.
        
        Аргументы:
            key: Ключ
            value: Значение (будет сериализовано в JSON)
            ttl: Время жизни
        """
        # РЕАЛИЗУЙТЕ с JSON сериализацией
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение (десериализовать из JSON)."""
        pass
```

---

### 5. Metrics Collector (Python)

**src/core/metrics.py:**

```python
"""
Сборщик метрик
CRYPTOTEHNOLOG v1.1.0
"""

from collections import defaultdict

class MetricsCollector:
    """
    Сборщик системных метрик.
    
    Типы метрик:
    - Счетчики (counters)
    - Измерители (gauges)
    - Гистограммы (histograms)
    """
    
    def __init__(self, db: PostgreSQLManager):
        self.db = db
        self.counters = defaultdict(int)
        self.gauges = {}
        self.histograms = defaultdict(list)
    
    def increment(self, metric_name: str, value: int = 1, labels: Dict = None):
        """
        Увеличить счетчик.
        
        Пример:
            metrics.increment("events_published", labels={"type": "TRADE_SIGNAL"})
        """
        # РЕАЛИЗУЙТЕ
    
    def set_gauge(self, metric_name: str, value: float, labels: Dict = None):
        """Установить измеритель."""
        pass
    
    def record_histogram(self, metric_name: str, value: float, labels: Dict = None):
        """Записать в гистограмму."""
        pass
    
    async def flush(self):
        """Записать все метрики в БД."""
        # РЕАЛИЗУЙТЕ:
        # 1. Записать counters
        # 2. Записать gauges
        # 3. Агрегировать histograms (p50, p95, p99)
        # 4. logger.info("Метрики записаны")
```

---

### 6. Health Check (Python)

**src/core/health.py:**

```python
"""
Система проверки здоровья
CRYPTOTEHNOLOG v1.1.0
"""

from enum import Enum
from dataclasses import dataclass

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthCheckResult:
    component: str
    status: HealthStatus
    details: Dict
    checked_at: datetime

class HealthChecker:
    """Проверка здоровья системы."""
    
    def __init__(self, db: PostgreSQLManager, redis: RedisManager):
        self.db = db
        self.redis = redis
    
    async def check_all(self) -> List[HealthCheckResult]:
        """
        Проверить все компоненты.
        
        Возвращает:
            Список результатов проверки
        """
        # РЕАЛИЗУЙТЕ:
        # 1. Проверить PostgreSQL (SELECT 1)
        # 2. Проверить Redis (PING)
        # 3. Вернуть список HealthCheckResult
        # 4. logger.info("Проверка здоровья завершена")
    
    async def check_postgresql(self) -> HealthCheckResult:
        """Проверить PostgreSQL."""
        pass
    
    async def check_redis(self) -> HealthCheckResult:
        """Проверить Redis."""
        pass
```

---

## ACCEPTANCE CRITERIA

### Rust Components
- [ ] Cargo.toml настроен корректно (добавить pyo3 зависимости)
- [ ] Event struct создан с Priority enum
- [ ] EventBus реализован с subscribe/publish
- [x] Python bindings для EventBus ⏳ **РЕАЛИЗОВАТЬ В PHASE 1**
- [ ] **Все комментарии на русском** ✅
- [ ] `cargo build --release` успешен
- [ ] `cargo test` все тесты проходят
- [ ] `maturin build` создает wheel

### Python Components
- [ ] Structured Logging настроен (JSON в файл)
- [ ] PostgreSQL Manager подключается и работает
- [x] Redis Manager работает (set/get/delete + **Pub/Sub + Streams**) ⏳ **ДОБАВИТЬ В PHASE 1**
- [ ] Metrics Collector собирает метрики
- [ ] Health Check проверяет компоненты
- [ ] **Все docstrings на русском** ✅
- [ ] **Все логи на русском** ✅

### Testing
- [ ] Unit tests coverage >= 85%
- [ ] Integration test проходит
- [ ] Все компоненты работают вместе

---

## 📤 ФОРМАТ ВЫДАЧИ

Для каждого файла:
1. Напишите полный путь
2. Покажите ВЕСЬ код (не TODO)
3. Добавьте header комментарий на русском
4. После кода: "✅ filename READY"

Пример:
```
=== crates/eventbus/src/event.rs ===

// CRYPTOTEHNOLOG v1.1.0
// Фаза 1: Ядро инфраструктуры
// Компонент: Event Bus
// Файл: event.rs

use serde::{Deserialize, Serialize};

/// Событие в системе
pub struct Event {
    /// Уникальный идентификатор
    pub id: String,
}

✅ event.rs READY
```

В конце:
```
📦 GENERATED FILES:
- crates/eventbus/Cargo.toml ✅
- crates/eventbus/src/event.rs ✅
- crates/eventbus/src/bus.rs ✅
- crates/eventbus/src/python_bindings.rs ⏳ (РЕАЛИЗОВАТЬ В PHASE 1)
- src/cryptotechnolog/config/logging.py ★ РАСШИРЕН
- src/core/database.py ✅
- src/core/redis_manager.py ✅ (ДОБАВИТЬ Pub/Sub + Streams)
- src/core/metrics.py ✅
- src/core/health.py ✅

🧪 NEXT STEPS:
1. cd crates/eventbus && cargo build --release
2. cargo test
3. maturin develop --release
4. python -c "from event_bus import PyEventBus; print('OK')"
5. pytest tests/unit -v
6. pytest tests/integration -v
```

---

## ✅ КАК ПРОВЕРИТЬ РЕЗУЛЬТАТ

### 1. Rust Build
```bash
cd crates/eventbus
cargo build --release
```
**Ожидаемо:** `Finished release [optimized]`

### 2. Rust Tests
```bash
cargo test
```
**Ожидаемо:** `test result: ok. X passed`

### 3. Python Bindings
```bash
maturin develop --release
python -c "from event_bus import PyEventBus; bus = PyEventBus(); print('✅ OK')"
```
**Ожидаемо:** `✅ OK`

### 4. Python Tests
```bash
pytest tests/unit -v
```
**Ожидаемо:** All tests pass

### 5. Integration Test
```bash
pytest tests/integration/test_infrastructure.py -v
```
**Ожидаемо:** Integration test pass

### 6. Проверка русификации
```bash
# Проверить что НЕТ английских комментариев в Rust
grep -r "// [A-Z]" crates/eventbus/src/

# Проверить что НЕТ английских docstrings в Python
grep -r '"""[A-Z]' src/core/

# Должно быть пусто или минимально
```

---

## ВАЖНО

1. **ВСЕ комментарии, docstrings, логи на русском** — это ОБЯЗАТЕЛЬНО
2. **НЕ используйте TODO или placeholders** — только рабочий код
3. **Error handling везде** — try/except, Result<T, E>
4. **Type hints в Python** — полная типизация
5. **Async/await корректно** — не блокирующие операции

---

**Успехов в реализации Фазы 1!** 🚀

---

## 🆕 ДОПОЛНЕНИЯ v4.4 (SLO DEFINITIONS & MONITORING)

### SLO (SERVICE LEVEL OBJECTIVES) — Определения целевых показателей

**Концепция из плана v4.4:**
SLO — количественные цели по латентности и availability для каждого
критического компонента. Используются для мониторинга health и триггера
State Machine переходов (DEGRADED при нарушении).

**Файл:** `src/core/slo.py` ★ НОВЫЙ

```python
"""
SLO (Service Level Objectives) — определения и мониторинг.

Каждый SLO имеет:
- target_ms: целевая латентность
- percentile: какой процентиль (p95, p99)
- alert_threshold_ms: порог для alert (Telegram)
- degraded_threshold_ms: порог для DEGRADED state
"""

from dataclasses import dataclass
from typing import Dict, Optional
from collections import deque
from datetime import datetime
import statistics

from src.core.logger import get_logger

logger = get_logger("SLO")


@dataclass
class SLODefinition:
    """
    Определение Service Level Objective.
    
    Атрибуты:
        name: Название метрики (e.g., "risk_engine_latency")
        target_ms: Целевая латентность (миллисекунды)
        percentile: Процентиль для измерения (0.95, 0.99)
        alert_threshold_ms: Порог для alert
        degraded_threshold_ms: Порог для DEGRADED state
    """
    name: str
    target_ms: float
    percentile: float
    alert_threshold_ms: float
    degraded_threshold_ms: float


class SLORegistry:
    """
    Центральный реестр SLO definitions из плана v4.4.
    
    SLO для критических компонентов:
    - risk_engine_latency: p99 < 100ms (target), alert @ 150ms, DEGRADED @ 200ms
    - execution_response: p95 < 500ms, alert @ 1000ms, DEGRADED @ 2000ms
    - universe_update: p99 < 2000ms, alert @ 5000ms, DEGRADED @ 10000ms
    - data_freshness: p99 < 500ms, alert @ 1000ms, DEGRADED @ 2000ms
    """
    
    # Определения из плана v4.4 (точно как в исходнике)
    SLO_DEFINITIONS: Dict[str, SLODefinition] = {
        "risk_engine_latency": SLODefinition(
            name="risk_engine_latency",
            target_ms=100.0,
            percentile=0.99,
            alert_threshold_ms=150.0,
            degraded_threshold_ms=200.0,
        ),
        "execution_response": SLODefinition(
            name="execution_response",
            target_ms=500.0,
            percentile=0.95,
            alert_threshold_ms=1000.0,
            degraded_threshold_ms=2000.0,
        ),
        "universe_update": SLODefinition(
            name="universe_update",
            target_ms=2000.0,
            percentile=0.99,
            alert_threshold_ms=5000.0,
            degraded_threshold_ms=10000.0,
        ),
        "data_freshness": SLODefinition(
            name="data_freshness",
            target_ms=500.0,
            percentile=0.99,
            alert_threshold_ms=1000.0,
            degraded_threshold_ms=2000.0,
        ),
    }
    
    @classmethod
    def get(cls, name: str) -> Optional[SLODefinition]:
        """Получить SLO definition по имени."""
        return cls.SLO_DEFINITIONS.get(name)
    
    @classmethod
    def get_all(cls) -> Dict[str, SLODefinition]:
        """Получить все SLO definitions."""
        return cls.SLO_DEFINITIONS.copy()


class Histogram:
    """
    Простая гистограмма для расчёта percentiles.
    
    Хранит последние 10,000 значений в памяти.
    Используется для SLO monitoring.
    """
    
    def __init__(self, buckets: Optional[list] = None):
        """
        Аргументы:
            buckets: Предопределённые buckets (для совместимости)
        """
        self.buckets = sorted(buckets) if buckets else [
            10, 25, 50, 100, 250, 500, 1000, 2000, 5000, 10000
        ]
        self.values: deque = deque(maxlen=10000)
    
    def observe(self, value: float) -> None:
        """
        Записать значение.
        
        Аргументы:
            value: Латентность в миллисекундах
        """
        self.values.append(value)
    
    def percentile(self, p: float) -> float:
        """
        Рассчитать percentile.
        
        Аргументы:
            p: Процентиль (0.95, 0.99)
        
        Возвращает:
            Значение на заданном percentile
        """
        if not self.values:
            return 0.0
        
        sorted_values = sorted(self.values)
        idx = int(len(sorted_values) * p)
        return sorted_values[min(idx, len(sorted_values) - 1)]
    
    def mean(self) -> float:
        """Среднее значение."""
        if not self.values:
            return 0.0
        return statistics.mean(self.values)
    
    def count(self) -> int:
        """Количество наблюдений."""
        return len(self.values)
```

---

### Metrics Collector обновление с SLO monitoring

**Обновлённый `src/core/metrics.py`:**

```python
"""
Metrics Collector v4.4 — с SLO monitoring и Histogram support.
"""

from typing import Dict, Optional
from collections import Counter, defaultdict
from datetime import datetime

from src.core.slo import SLORegistry, Histogram, SLODefinition
from src.core.logger import get_logger

logger = get_logger("MetricsCollector")


class MetricsCollector:
    """
    Центральный сборщик метрик с SLO monitoring.
    
    Новое v4.4:
    - SLO definitions integration
    - Histogram для latency tracking
    - check_slo_violations() → State Machine trigger
    - get_dashboard_data() для UI
    """
    
    def __init__(self, state_machine=None):
        """
        Аргументы:
            state_machine: State Machine для DEGRADED transitions (опционально)
        """
        self.state_machine = state_machine
        
        # ★ НОВОЕ v4.4: Гистограммы латентности для SLO
        self.latencies: Dict[str, Histogram] = {
            name: Histogram() for name in SLORegistry.SLO_DEFINITIONS.keys()
        }
        
        # Счетчики событий
        self.counters = {
            "signals_generated": 0,
            "signals_dropped": 0,
            "blocked_by_risk": 0,
            "blocked_by_exchange": 0,
            "blocked_by_slippage": 0,
            "blocked_by_capital": 0,
            "state_transitions": Counter(),
            "kill_switch_triggers": Counter(),
            "invariant_violations": Counter(),
        }
        
        # Gauges (текущие значения)
        self.gauges = {
            "open_positions": 0,
            "total_risk_r": 0.0,
            "available_risk_r": 0.0,
            "current_drawdown": 0.0,
            "universe_confidence": 0.0,
            "exchange_health_score": 0.0,
        }
    
    def record_latency(self, metric_name: str, latency_ms: float) -> None:
        """
        Записать латентность операции.
        
        Используется компонентами для SLO tracking:
        - Risk Engine: record_latency("risk_engine_latency", duration_ms)
        - Execution: record_latency("execution_response", duration_ms)
        - UniverseEngine: record_latency("universe_update", duration_ms)
        - Market Data: record_latency("data_freshness", tick_age_ms)
        
        Аргументы:
            metric_name: Название метрики из SLORegistry
            latency_ms: Латентность в миллисекундах
        """
        if metric_name in self.latencies:
            self.latencies[metric_name].observe(latency_ms)
            
            logger.debug(
                "Латентность записана",
                metric=metric_name,
                latency_ms=latency_ms,
            )
        else:
            logger.warning(
                "Неизвестная SLO метрика",
                metric=metric_name,
                available=list(self.latencies.keys()),
            )
    
    def record_event(self, counter_name: str, count: int = 1) -> None:
        """
        Записать событие (counter++).
        
        Аргументы:
            counter_name: Название счётчика
            count: Количество (default 1)
        """
        if counter_name in self.counters:
            if isinstance(self.counters[counter_name], Counter):
                self.counters[counter_name].update({counter_name: count})
            else:
                self.counters[counter_name] += count
    
    def update_gauge(self, gauge_name: str, value: float) -> None:
        """
        Обновить gauge (текущее значение).
        
        Аргументы:
            gauge_name: Название gauge
            value: Новое значение
        """
        if gauge_name in self.gauges:
            self.gauges[gauge_name] = value
    
    async def check_slo_violations(self) -> None:
        """
        Проверить SLO violations (вызывается периодически).
        
        Workflow:
        1. Для каждого SLO: рассчитать текущий percentile
        2. Если > alert_threshold → логировать WARNING
        3. Если > degraded_threshold → State Machine DEGRADED
        
        Вызывается раз в минуту из Watchdog (Фаза 2).
        """
        violations = []
        
        for metric_name, slo in SLORegistry.SLO_DEFINITIONS.items():
            histogram = self.latencies.get(metric_name)
            if not histogram or histogram.count() == 0:
                continue
            
            # Рассчитать текущий percentile
            current_latency = histogram.percentile(slo.percentile)
            
            # Проверка alert threshold
            if current_latency > slo.alert_threshold_ms:
                logger.warning(
                    "SLO alert threshold превышен",
                    metric=metric_name,
                    current_latency_ms=current_latency,
                    percentile=int(slo.percentile * 100),
                    alert_threshold_ms=slo.alert_threshold_ms,
                )
            
            # Проверка degraded threshold
            if current_latency > slo.degraded_threshold_ms:
                logger.critical(
                    "SLO VIOLATION — превышен degraded threshold",
                    metric=metric_name,
                    current_latency_ms=current_latency,
                    percentile=int(slo.percentile * 100),
                    degraded_threshold_ms=slo.degraded_threshold_ms,
                    action="DEGRADE_SYSTEM",
                )
                
                violations.append({
                    "metric": metric_name,
                    "latency_p99": current_latency,
                    "threshold": slo.degraded_threshold_ms,
                })
                
                # Триггер State Machine → DEGRADED
                if self.state_machine:
                    await self.state_machine.transition("SLO_VIOLATION", {
                        "metric": metric_name,
                        "latency": current_latency,
                        "threshold": slo.degraded_threshold_ms,
                    })
        
        if violations:
            logger.critical(
                "SLO violations обнаружены",
                violations_count=len(violations),
                violations=violations,
            )
    
    def get_dashboard_data(self) -> dict:
        """
        Получить данные для real-time dashboard (Фаза 18).
        
        Возвращает:
            {
              "timestamp": "2025-02-19T...",
              "system_state": "TRADING",
              "latencies": {
                "risk_engine_latency": {"p50": 45, "p99": 98},
                "execution_response": {"p50": 250, "p95": 450}
              },
              "counters": {...},
              "gauges": {...},
              "slo_status": [...]
            }
        """
        # Рассчитать latencies
        latencies_data = {}
        for name, hist in self.latencies.items():
            if hist.count() > 0:
                latencies_data[name] = {
                    "p50": hist.percentile(0.50),
                    "p95": hist.percentile(0.95),
                    "p99": hist.percentile(0.99),
                    "mean": hist.mean(),
                    "count": hist.count(),
                }
            else:
                latencies_data[name] = {
                    "p50": 0.0,
                    "p95": 0.0,
                    "p99": 0.0,
                    "mean": 0.0,
                    "count": 0,
                }
        
        # SLO status
        slo_status = self._get_slo_status()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system_state": self.state_machine.state if self.state_machine else "UNKNOWN",
            "latencies": latencies_data,
            "counters": {k: v if not isinstance(v, Counter) else dict(v) for k, v in self.counters.items()},
            "gauges": dict(self.gauges),
            "slo_status": slo_status,
        }
    
    def _get_slo_status(self) -> list:
        """
        Рассчитать статус каждого SLO.
        
        Возвращает:
            [
              {
                "name": "risk_engine_latency",
                "target_ms": 100,
                "current_p99_ms": 98,
                "status": "OK",  # OK / WARNING / CRITICAL
                "compliance_percent": 98.0
              },
              ...
            ]
        """
        status_list = []
        
        for name, slo in SLORegistry.SLO_DEFINITIONS.items():
            hist = self.latencies.get(name)
            if not hist or hist.count() == 0:
                status_list.append({
                    "name": name,
                    "target_ms": slo.target_ms,
                    "current_latency_ms": 0.0,
                    "percentile": int(slo.percentile * 100),
                    "status": "NO_DATA",
                    "compliance_percent": 0.0,
                })
                continue
            
            current_latency = hist.percentile(slo.percentile)
            
            # Определить status
            if current_latency <= slo.target_ms:
                status = "OK"
            elif current_latency <= slo.alert_threshold_ms:
                status = "WARNING"
            else:
                status = "CRITICAL"
            
            # Compliance percent
            compliance = (slo.target_ms / current_latency * 100) if current_latency > 0 else 100.0
            
            status_list.append({
                "name": name,
                "target_ms": slo.target_ms,
                "current_latency_ms": current_latency,
                "percentile": int(slo.percentile * 100),
                "alert_threshold_ms": slo.alert_threshold_ms,
                "degraded_threshold_ms": slo.degraded_threshold_ms,
                "status": status,
                "compliance_percent": min(100.0, compliance),
            })
        
        return status_list
```

---

### Integration примеры

**1. Risk Engine (Фаза 5) — record latency:**

```python
class RiskEngine:
    async def check_trade(self, signal):
        """Проверка риска с SLO tracking."""
        start = time.time()
        
        # Выполнить проверку
        result = await self._do_risk_check(signal)
        
        # Записать латентность для SLO
        duration_ms = (time.time() - start) * 1000
        self.metrics_collector.record_latency("risk_engine_latency", duration_ms)
        
        return result
```

**2. Execution Layer (Фаза 10) — record latency:**

```python
class ExecutionLayer:
    async def execute_order(self, signal):
        """Исполнение с SLO tracking."""
        start = time.time()
        
        order = await self._send_order_to_exchange(signal)
        
        duration_ms = (time.time() - start) * 1000
        self.metrics_collector.record_latency("execution_response", duration_ms)
        
        return order
```

**3. Watchdog (Фаза 2) — periodic SLO check:**

```python
class Watchdog:
    async def _monitoring_loop(self):
        """Периодическая проверка SLO."""
        while True:
            await asyncio.sleep(60)  # Раз в минуту
            
            # Проверить SLO violations
            await self.metrics_collector.check_slo_violations()
```

---

## ACCEPTANCE CRITERIA v4.4

### SLO Definitions ★ НОВОЕ
- [ ] SLORegistry с 4 определениями из плана v4.4
- [ ] Histogram класс для percentile calculation
- [ ] MetricsCollector.record_latency() для всех критических операций
- [ ] MetricsCollector.check_slo_violations() → State Machine DEGRADED
- [ ] get_dashboard_data() для UI (Фаза 18)
- [ ] _get_slo_status() с compliance %

### SLO Integration Points ★ НОВОЕ
- [ ] Risk Engine: record_latency("risk_engine_latency")
- [ ] Execution: record_latency("execution_response")
- [ ] UniverseEngine: record_latency("universe_update")
- [ ] Market Data: record_latency("data_freshness")
- [ ] Watchdog: periodic check_slo_violations() каждые 60 сек

### Existing Infrastructure (как было)
- [ ] Event Bus (Rust) с priority queues
- [ ] Structured Logging (JSON)
- [ ] PostgreSQL Manager
- [ ] Redis Manager
- [ ] Health Check System

---

**Version:** CRYPTOTEHNOLOG v4.4 (Фаза 1 — полная редакция)
**Dependencies:** Phase 0
**Next:** Phase 2 - Control Plane (State Machine использует SLO violations для transitions)
