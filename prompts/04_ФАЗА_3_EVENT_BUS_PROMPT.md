# AI ПРОМТ: ФАЗА 3 - EVENT BUS ENHANCEMENT

## КОНТЕКСТ

Вы — Senior Rust Engineer, специализирующийся на high-performance concurrent systems и async programming.

**Фазы 0-2 завершены.** Доступны:
- Python окружение настроено
- Rust toolchain установлен
- Docker инфраструктура (Redis, PostgreSQL) работает
- **Базовый Event Bus (Rust)** — из Фазы 1
- Control Plane (State Machine, Watchdog) — из Фазы 2
- Structured Logging, Database Layer

**Текущая задача:** Расширить базовый Event Bus до production-ready с priority queues, backpressure, persistence, rate limiting.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Rust комментарии — ТОЛЬКО русский:

```rust
/// Очередь с приоритетами для событий
/// 
/// События обрабатываются в порядке приоритета:
/// Critical > High > Normal > Low
pub struct PriorityQueue {
    /// Очередь критических событий
    critical: VecDeque<Event>,
    /// Очередь событий высокого приоритета
    high: VecDeque<Event>,
}

impl PriorityQueue {
    /// Добавить событие в соответствующую очередь
    /// 
    /// # Аргументы
    /// * `event` - Событие для добавления
    /// 
    /// # Возвращает
    /// `Ok(())` если успешно, `Err(QueueFullError)` если переполнена
    pub fn push(&mut self, event: Event) -> Result<(), QueueFullError> {
        // Выбрать очередь по приоритету
        match event.priority {
            Priority::Critical => {
                if self.critical.len() >= CRITICAL_QUEUE_SIZE {
                    return Err(QueueFullError::Critical);
                }
                self.critical.push_back(event);
            }
            // ...
        }
        Ok(())
    }
}
```

### Логи — ТОЛЬКО русский:

```rust
tracing::info!("Event Bus запущен", subscribers_count = self.subscribers.len());
tracing::error!("Критическая очередь переполнена", queue_size = self.critical.len());
tracing::warn!("Backpressure активирован", dropped_events = dropped);
```

### Примеры замены:

| ❌ Неправильно | ✅ Правильно |
|----------------|--------------|
| "Queue full" | "Очередь переполнена" |
| "Event dropped" | "Событие отброшено" |
| "Persistence failed" | "Сохранение не удалось" |
| "Rate limit exceeded" | "Превышен лимит частоты" |

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Event Bus Enhancement (Фаза 3) превращает базовый Event Bus из Фазы 1 в production-ready компонент с persistence, backpressure и rate limiting. Добавление Redis Streams обеспечивает гарантию доставки при перезапусках.

### Входящие зависимости (что получает Enhanced Event Bus):

#### От всех компонентов системы (увеличенная нагрузка):

1. **Risk Engine (Фаза 5)** → публикует события риска
   - События: `RISK_VIOLATION`, `RISK_BUDGET_UPDATE`
   - Частота: 50-200 events/сек (пиковая нагрузка)
   - Приоритет: HIGH для RISK_VIOLATION, NORMAL для остального
   - Требование: Persistence (для audit trail)

2. **Execution Layer (Фаза 10)** → публикует события исполнения
   - События: `ORDER_FILLED`, `ORDER_CANCELLED`, `EXECUTION_ERROR`
   - Частота: 100-500 events/сек (пиковая при high-frequency trading)
   - Приоритет: NORMAL для успешных, HIGH для ошибок
   - Требование: Persistence (для reconciliation)

3. **Metrics Collector (Фаза 1)** → публикует метрики
   - События: `METRIC_RECORDED`
   - Частота: постоянно (1000+ events/сек)
   - Приоритет: LOW (можно отбрасывать при backpressure)
   - Требование: Best-effort delivery

4. **Kill Switch (Фаза 12)** → критические события
   - События: `KILL_SWITCH_TRIGGERED`
   - Частота: очень редко
   - Приоритет: CRITICAL (максимальный)
   - Требование: Гарантированная доставка + persistence

5. **Watchdog (Фаза 2)** → алерты здоровья
   - События: `HEALTH_CHECK_FAILED`, `COMPONENT_RESTARTED`
   - Частота: 10-50 events/мин
   - Приоритет: HIGH
   - Требование: At-least-once delivery

### Исходящие зависимости (что отправляет Enhanced Event Bus):

#### 1. → Redis Streams (NEW в Фазе 3)
   - Действие: Сохранение всех HIGH/CRITICAL событий
   - Stream keys: `events:{event_type}`, `events:critical`, `events:audit`
   - TTL: 7 дней для NORMAL, 30 дней для CRITICAL/HIGH
   - Формат: JSON с metadata (timestamp, source, correlation_id)

#### 2. → Подписчики (через subscribers)
   - Метод: async channel delivery
   - Backpressure: DROP LOW при переполнении, BLOCK на CRITICAL
   - Гарантии:
     - CRITICAL: exactly-once (через persistence + dedup)
     - HIGH: at-least-once (retry с persistence)
     - NORMAL: at-least-once (best effort)
     - LOW: at-most-once (может потеряться)

#### 3. → Audit Chain (Фаза 16)
   - Подписка: только CRITICAL + HIGH события
   - Stream: `events:audit` в Redis
   - Действие: Immutable audit log с cryptographic hashing
   - Replay: возможность replay за любой период

#### 4. → Metrics (Prometheus)
   - Метрики: event_published_total, event_dropped_total, queue_size, backpressure_triggered
   - Частота: каждые 15 секунд
   - Endpoint: /metrics (scrape target)

### Контракты данных:

#### Enhanced Event struct (Rust):

```rust
/// Событие с расширенными возможностями
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Event {
    /// Уникальный идентификатор (UUID v4)
    pub id: String,
    
    /// Тип события
    pub event_type: String,
    
    /// Приоритет (Critical/High/Normal/Low)
    pub priority: Priority,
    
    /// Временная метка (Unix timestamp микросекунды)
    pub timestamp: u64,
    
    /// ID корреляции для трассировки
    pub correlation_id: Option<String>,
    
    /// Источник события
    pub source: String,
    
    /// Полезная нагрузка (JSON)
    pub payload: serde_json::Value,
    
    /// NEW: Metadata для persistence
    pub metadata: EventMetadata,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventMetadata {
    /// Попытка доставки (для retry logic)
    pub delivery_attempt: u32,
    
    /// Время истечения (для TTL)
    pub expires_at: Option<u64>,
    
    /// Флаг персистентности
    pub persist: bool,
    
    /// Дедупликация ID (для exactly-once)
    pub dedup_id: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Priority {
    Critical = 0,  // Kill switches, системные сбои
    High = 1,      // Риск-нарушения, критические ошибки
    Normal = 2,    // Торговые сигналы, обычные операции
    Low = 3,       // Метрики, информационные логи
}

impl Priority {
    /// Получить размер очереди для приоритета
    pub fn queue_capacity(&self) -> usize {
        match self {
            Priority::Critical => 1_000,    // Маленькая, быстрая
            Priority::High => 10_000,       // Средняя
            Priority::Normal => 50_000,     // Большая
            Priority::Low => 100_000,       // Очень большая
        }
    }
    
    /// Нужна ли персистентность
    pub fn requires_persistence(&self) -> bool {
        matches!(self, Priority::Critical | Priority::High)
    }
}
```

#### Redis Streams Schema:

```
Stream: events:critical
Format: XADD events:critical * event_json {json_blob}

Entry structure:
{
  "event_id": "evt_uuid",
  "event_type": "KILL_SWITCH_TRIGGERED",
  "priority": "Critical",
  "timestamp": 1704067200000000,
  "source": "kill_switch",
  "correlation_id": "req_123",
  "payload": {...},
  "metadata": {
    "delivery_attempt": 1,
    "persist": true,
    "dedup_id": "dedup_uuid"
  }
}

TTL: EXPIRE events:critical 2592000  # 30 days
```

#### Backpressure Policy:

```rust
pub enum BackpressureAction {
    /// Принять событие (очередь не переполнена)
    Accept,
    
    /// Отбросить событие (LOW priority, очередь переполнена)
    Drop,
    
    /// Блокировать publisher до освобождения места (CRITICAL)
    Block,
    
    /// Отправить в overflow queue (NORMAL/HIGH)
    Overflow,
}

impl EventBus {
    /// Определить действие backpressure
    fn backpressure_policy(&self, event: &Event) -> BackpressureAction {
        let queue_size = self.get_queue_size(event.priority);
        let capacity = event.priority.queue_capacity();
        let fill_ratio = queue_size as f64 / capacity as f64;
        
        match (event.priority, fill_ratio) {
            // CRITICAL: всегда блокировать при переполнении
            (Priority::Critical, ratio) if ratio > 0.9 => BackpressureAction::Block,
            
            // HIGH: overflow queue при 80% заполнения
            (Priority::High, ratio) if ratio > 0.8 => BackpressureAction::Overflow,
            
            // NORMAL: overflow queue при 90%
            (Priority::Normal, ratio) if ratio > 0.9 => BackpressureAction::Overflow,
            
            // LOW: отбрасывать при 70%
            (Priority::Low, ratio) if ratio > 0.7 => BackpressureAction::Drop,
            
            // Иначе принять
            _ => BackpressureAction::Accept,
        }
    }
}
```

#### Rate Limiting:

```rust
pub struct RateLimiter {
    /// Лимиты по источнику события
    limits: HashMap<String, TokenBucket>,
    
    /// Глобальный лимит
    global_limit: TokenBucket,
}

pub struct TokenBucket {
    /// Вместимость bucket
    capacity: usize,
    
    /// Текущие токены
    tokens: f64,
    
    /// Скорость пополнения (tokens/sec)
    refill_rate: f64,
    
    /// Последнее пополнение
    last_refill: Instant,
}

impl RateLimiter {
    /// Проверить можно ли принять событие
    pub fn check(&mut self, source: &str) -> Result<(), RateLimitError> {
        // 1. Проверить глобальный лимит (1000 events/sec)
        if !self.global_limit.consume(1.0) {
            return Err(RateLimitError::GlobalLimit);
        }
        
        // 2. Проверить лимит источника (100 events/sec per source)
        let bucket = self.limits.entry(source.to_string())
            .or_insert_with(|| TokenBucket::new(100, 100.0));
        
        if !bucket.consume(1.0) {
            return Err(RateLimitError::SourceLimit(source.to_string()));
        }
        
        Ok(())
    }
}
```

### Sequence Diagram (Enhanced Event Flow):

```
[Risk Engine] ──publish(RISK_VIOLATION, HIGH)──> [Event Bus]
                                                       |
                                           ┌───────────┼───────────┐
                                           v           v           v
                                    [Rate Limiter] [Priority Queue] [Persistence]
                                           |           |           |
                                     check limit   classify      save to
                                           |        priority    Redis Streams
                                           v           v           v
                                       ✅ OK      [HIGH queue]  events:audit
                                                       |
                                           ┌───────────┼───────────┐
                                           v                       v
                                    [Subscriber A]          [Subscriber B]
                                    async deliver           async deliver
                                           |                       |
                                           v                       v
                                    [Audit Chain]            [Metrics]
```

### Обработка ошибок интеграции:

#### 1. Redis недоступен (persistence failure):

```rust
async fn persist_event(&self, event: &Event) -> Result<(), PersistError> {
    match self.redis.xadd(&stream_key, "*", &event_json).await {
        Ok(id) => {
            tracing::info!("Событие сохранено в Redis", event_id = event.id, stream_id = id);
            Ok(())
        }
        Err(e) => {
            tracing::error!("Ошибка сохранения события в Redis", error = %e);
            
            // Fallback: сохранить в локальную очередь для retry
            self.persistence_buffer.push(event.clone());
            
            // Метрика
            self.metrics.persistence_failures.inc();
            
            // Если CRITICAL → паника (не можем потерять)
            if event.priority == Priority::Critical {
                panic!("Не удалось сохранить CRITICAL событие: {:?}", e);
            }
            
            Err(PersistError::RedisUnavailable)
        }
    }
}
```

**Retry logic:**
- Exponential backoff: 100ms, 200ms, 400ms, 800ms, 1.6s
- Max retries: 5
- Fallback: Local disk buffer (если Redis недоступен >5 минут)

#### 2. Queue overflow:

```rust
pub async fn publish(&self, event: Event) -> Result<(), PublishError> {
    let action = self.backpressure_policy(&event);
    
    match action {
        BackpressureAction::Accept => {
            // Нормальная публикация
            self.priority_queue.push(event).await
        }
        
        BackpressureAction::Drop => {
            // Отбросить LOW priority событие
            tracing::warn!("Событие отброшено (backpressure)", event_type = event.event_type);
            self.metrics.events_dropped.inc();
            Err(PublishError::Dropped)
        }
        
        BackpressureAction::Block => {
            // Блокировать publisher до освобождения места
            tracing::warn!("Publisher заблокирован (CRITICAL queue full)");
            
            // Ждать с timeout
            tokio::time::timeout(
                Duration::from_secs(5),
                self.wait_for_queue_space(Priority::Critical)
            ).await??;
            
            self.priority_queue.push(event).await
        }
        
        BackpressureAction::Overflow => {
            // Отправить в overflow queue (Redis)
            tracing::info!("Событие в overflow queue", event_id = event.id);
            self.overflow_queue.push(event).await
        }
    }
}
```

#### 3. Rate limit exceeded:

```rust
pub async fn publish(&self, event: Event) -> Result<(), PublishError> {
    // Проверить rate limit
    match self.rate_limiter.lock().await.check(&event.source) {
        Ok(_) => {
            // Продолжить публикацию
        }
        Err(RateLimitError::GlobalLimit) => {
            tracing::error!("Глобальный rate limit превышен");
            self.metrics.rate_limit_global.inc();
            return Err(PublishError::RateLimitExceeded);
        }
        Err(RateLimitError::SourceLimit(source)) => {
            tracing::warn!("Rate limit превышен для источника", source = source);
            self.metrics.rate_limit_per_source.inc();
            
            // Для CRITICAL — игнорировать rate limit
            if event.priority == Priority::Critical {
                tracing::warn!("Rate limit игнорирован (CRITICAL event)");
            } else {
                return Err(PublishError::RateLimitExceeded);
            }
        }
    }
    
    // ... продолжить публикацию
}
```

### Мониторинг интеграций:

#### Метрики Event Bus Enhanced:

```rust
// Счетчики
event_published_total{source, event_type, priority}
event_delivered_total{event_type, priority}
event_dropped_total{reason, priority}  // reason: backpressure, rate_limit
event_persisted_total{stream, priority}
event_replay_total{stream}

// Гистограммы
event_publish_latency_seconds{priority, percentile}
event_persistence_latency_seconds{percentile}
queue_size{priority}  // gauge
backpressure_active{priority}  // gauge: 0/1

// Rate limiting
rate_limit_exceeded_total{source, type}  // type: global, per_source
rate_limit_tokens{source}  // gauge

// Redis
redis_connection_status{}  // gauge: 1=connected, 0=disconnected
persistence_failures_total{reason}
overflow_queue_size{}  // gauge
```

#### Alerts:

**Critical (PagerDuty):**
- `redis_connection_status == 0` для 60 секунд
- `event_dropped_total{priority="Critical"}` > 0
- `queue_size{priority="Critical"} / capacity > 0.9` для 30 секунд

**Warning (Telegram):**
- `backpressure_active{priority="High"} == 1` для 5 минут
- `event_dropped_total{priority="Normal"}` rate > 100/sec
- `rate_limit_exceeded_total` rate > 50/sec
- `persistence_failures_total` rate > 10/sec

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 3

### Event Bus Enhanced (с Redis Streams):

**✅ Что реализовано:**
- Priority queues (4 уровня)
- Backpressure handling (graceful degradation)
- Persistence в Redis Streams
- Rate limiting (global + per-source)
- Replay capability

**❌ Что НЕ реализовано (для future phases):**
- Distributed Event Bus (multi-instance)
- Event deduplication (exactly-once не гарантируется полностью)
- Cross-datacenter replication
- Event schema validation (будет в Фазе 4 Config Manager)

**⚠️ ВАЖНО:**
```markdown
Event Bus в Фазе 3 работает в single-instance режиме с Redis.
Для multi-instance deployment требуется:
- Фаза 18: Distributed coordination (etcd/Consul)
- Redis Cluster (вместо single Redis instance)

Exactly-once delivery НЕ гарантируется:
- Возможны дубли при сбоях Redis
- Подписчики должны быть идемпотентными
```

### Production Readiness Matrix:

| Компонент | После Фазы 3 | Production Ready |
|-----------|--------------|------------------|
| Event Bus | ✅ Ready (single instance) | ✅ Ready с Redis Cluster |
| Priority Queues | ✅ Ready | ✅ Ready |
| Persistence | ✅ Ready | ✅ Ready с backup |
| Rate Limiting | ✅ Ready | ✅ Ready |
| Backpressure | ✅ Ready | ✅ Ready |

---

## ЦЕЛЬ ФАЗЫ

Создать production-ready Event Bus с:

1. **Priority Queues (Rust)** — 4 уровня (Critical, High, Normal, Low)
2. **Backpressure Handling (Rust)** — graceful degradation под нагрузкой
3. **Persistence (Rust + Redis Streams)** — сохранение для replay
4. **Rate Limiting (Rust)** — защита от event storms
5. **Enhanced Python Bindings** — доступ ко всем features

---

## ФАЙЛОВАЯ СТРУКТУРА

Создайте следующие файлы с ПОЛНЫМ рабочим кодом:

```
CRYPTOTEHNOLOG/
├── rust_components/
│   └── event_bus/
│       ├── Cargo.toml (UPDATE)
│       ├── src/
│       │   ├── lib.rs (UPDATE)
│       │   ├── event.rs (UPDATE - add Priority)
│       │   ├── bus.rs (UPDATE - enhance)
│       │   ├── priority_queue.rs (NEW)
│       │   ├── backpressure.rs (NEW)
│       │   ├── persistence.rs (NEW)
│       │   ├── rate_limiter.rs (NEW)
│       │   └── python_bindings.rs (UPDATE)
│       ├── tests/
│       │   ├── priority_queue_test.rs (NEW)
│       │   ├── backpressure_test.rs (NEW)
│       │   └── integration_test.rs (UPDATE)
│       └── benches/
│           └── throughput.rs (NEW)
│
└── tests/
    └── integration/
        └── test_event_bus_enhanced.py (NEW)
```

---

## ЗАВИСИМОСТИ (уже реализованы)

### Из Фазы 1:
```rust
// Базовый Event struct
pub struct Event {
    pub id: String,
    pub event_type: String,
    pub timestamp: u64,
    pub source: String,
    pub payload: serde_json::Value,
}

// Базовый EventBus (нужно расширить)
pub struct EventBus { /* ... */ }
```

### Новые зависимости (добавьте в Cargo.toml):
```toml
[dependencies]
# Existing: tokio, serde, serde_json, uuid, pyo3, pythonize

# NEW:
redis = { version = "0.24", features = ["tokio-comp", "connection-manager"] }
tracing = "0.1"
tracing-subscriber = "0.3"

[dev-dependencies]
criterion = "0.5"
```

---

## ТРЕБОВАНИЯ

### 1. Priority System (rust_components/event_bus/src/priority.rs)

**Создайте enum Priority:**

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Priority {
    Critical = 0,  // Kill switches, system failures
    High = 1,      // Risk violations, execution errors
    Normal = 2,    // Trade signals, market data
    Low = 3,       // Metrics, logs
}

impl Priority {
    pub fn queue_capacity(&self) -> usize {
        match self {
            Priority::Critical => 256,
            Priority::High => 512,
            Priority::Normal => 2048,
            Priority::Low => 4096,
        }
    }
    
    pub fn is_droppable(&self) -> bool {
        matches!(self, Priority::Low)
    }
}
```

**Обновите Event struct (src/event.rs):**
```rust
pub struct Event {
    pub id: String,
    pub event_type: String,
    pub priority: Priority,  // NEW
    pub timestamp: u64,
    pub correlation_id: Option<String>,
    pub source: String,
    pub payload: serde_json::Value,
}

impl Event {
    pub fn new(event_type: String, source: String, payload: serde_json::Value) -> Self {
        Event {
            id: Uuid::new_v4().to_string(),
            event_type,
            priority: Priority::Normal,  // Default
            timestamp: /* ... */,
            correlation_id: None,
            source,
            payload,
        }
    }
    
    pub fn with_priority(mut self, priority: Priority) -> Self {
        self.priority = priority;
        self
    }
}
```

---

### 2. Priority Queue (rust_components/event_bus/src/priority_queue.rs)

**Создайте PriorityQueue:**

```rust
use std::collections::VecDeque;
use tokio::sync::Mutex;
use crate::event::Event;
use crate::priority::Priority;

pub struct PriorityQueue {
    critical: Mutex<VecDeque<Event>>,
    high: Mutex<VecDeque<Event>>,
    normal: Mutex<VecDeque<Event>>,
    low: Mutex<VecDeque<Event>>,
}

impl PriorityQueue {
    pub fn new() -> Self;
    
    pub async fn push(&self, event: Event) -> Result<(), PushError> {
        // MUST:
        // 1. Get appropriate queue by event.priority
        // 2. Lock queue (Mutex)
        // 3. Check capacity
        // 4. If full: return Err with specific PushError variant
        // 5. If ok: push_back(event)
    }
    
    pub async fn pop(&self) -> Option<Event> {
        // MUST:
        // 1. Try CRITICAL queue first
        // 2. If empty, try HIGH
        // 3. If empty, try NORMAL
        // 4. If empty, try LOW
        // 5. Return first available event
    }
    
    pub async fn total_size(&self) -> usize;
    pub async fn size(&self, priority: Priority) -> usize;
}

#[derive(Debug)]
pub enum PushError {
    CriticalQueueFull,
    HighQueueFull,
    NormalQueueFull,
    LowQueueFull,
}
```

**Требования:**
- Thread-safe (используйте tokio::sync::Mutex)
- pop() всегда возвращает highest priority event
- Capacity enforcement строгий

---

### 3. Backpressure Handler (rust_components/event_bus/src/backpressure.rs)

**Создайте BackpressureHandler:**

```rust
pub struct BackpressureHandler {
    priority_queue: Arc<PriorityQueue>,
    metrics: Arc<RwLock<BackpressureMetrics>>,
}

#[derive(Default)]
pub struct BackpressureMetrics {
    pub dropped_low: u64,
    pub dropped_normal: u64,
    pub dropped_high: u64,
    pub blocked_critical: u64,
}

impl BackpressureHandler {
    pub fn new(priority_queue: Arc<PriorityQueue>) -> Self;
    
    pub async fn push_with_backpressure(&self, event: Event) -> Result<(), BackpressureError> {
        // MUST implement strategy:
        // 
        // 1. Try priority_queue.push(event)
        // 
        // 2. If LowQueueFull:
        //    - Log warning
        //    - Increment metrics.dropped_low
        //    - Return Err(Dropped(Low))
        // 
        // 3. If NormalQueueFull:
        //    - Try to drop some LOW events (call try_drop_low_events(10))
        //    - Retry push
        //    - If still fails: drop this NORMAL event
        // 
        // 4. If HighQueueFull:
        //    - Log ERROR (severe issue)
        //    - Drop LOW events aggressively (50+)
        //    - Retry push
        //    - If fails: drop HIGH event (metrics.dropped_high++)
        // 
        // 5. If CriticalQueueFull:
        //    - Log CRITICAL
        //    - metrics.blocked_critical++
        //    - Drop all LOW/NORMAL events
        //    - Retry with timeout (5 seconds)
        //    - If timeout: return Err(Timeout)
    }
    
    async fn try_drop_low_events(&self, max_drop: usize) -> Option<usize>;
    async fn retry_push_critical(&self, event: Event) -> Result<(), BackpressureError>;
    pub async fn get_metrics(&self) -> BackpressureMetrics;
}

#[derive(Debug)]
pub enum BackpressureError {
    Dropped(Priority),
    Timeout,
    RetriesExhausted,
}
```

**Требования:**
- CRITICAL events НИКОГДА не дропаются (только timeout после ретраев)
- LOW events дропаются первыми
- Metrics обновляются атомарно

---

### 4. Persistence Layer (rust_components/event_bus/src/persistence.rs)

**Создайте PersistenceLayer с Redis Streams:**

```rust
use redis::aio::ConnectionManager;
use redis::AsyncCommands;

pub struct PersistenceLayer {
    redis: ConnectionManager,
    stream_name: String,
    max_stream_len: usize,
}

impl PersistenceLayer {
    pub async fn new(redis_url: &str, stream_name: String) -> Result<Self, redis::RedisError> {
        // MUST:
        // 1. Create Redis client
        // 2. Create ConnectionManager (connection pooling)
        // 3. Return PersistenceLayer
    }
    
    pub async fn persist(&mut self, event: &Event) -> Result<String, PersistenceError> {
        // MUST:
        // 1. Serialize event to JSON (serde_json::to_string)
        // 2. Use XADD with MAXLEN to append to stream
        //    redis.xadd_maxlen(stream_name, MAXLEN, "*", [("event", json)])
        // 3. Return stream ID
    }
    
    pub async fn replay(
        &mut self,
        start_id: &str,
        count: usize,
    ) -> Result<Vec<Event>, PersistenceError> {
        // MUST:
        // 1. Use XRANGE to read events from stream
        //    redis.xrange_count(stream_name, start_id, "+", count)
        // 2. Deserialize each event from JSON
        // 3. Return Vec<Event>
    }
    
    pub async fn stream_length(&mut self) -> Result<usize, PersistenceError> {
        // Use XLEN command
    }
}

#[derive(Debug)]
pub enum PersistenceError {
    Serialization(String),
    Deserialization(String),
    Redis(String),
}
```

**Требования:**
- Async Redis operations (tokio)
- MAXLEN для ограничения размера stream (100k events)
- Error handling для всех Redis операций

---

### 5. Rate Limiter (rust_components/event_bus/src/rate_limiter.rs)

**Создайте RateLimiter:**

```rust
use std::sync::Arc;
use tokio::sync::Mutex;
use std::time::{Duration, Instant};

pub struct RateLimiter {
    max_per_second: usize,
    window: Arc<Mutex<RateWindow>>,
}

struct RateWindow {
    count: usize,
    window_start: Instant,
}

impl RateLimiter {
    pub fn new(max_per_second: usize) -> Self;
    
    pub async fn check_rate(&self) -> bool {
        // MUST:
        // 1. Lock window
        // 2. Check if 1 second elapsed since window_start
        // 3. If yes: reset count to 0, update window_start
        // 4. If count < max_per_second: increment count, return true
        // 5. Else: return false
    }
}
```

**Требования:**
- Sliding window по 1 секунде
- Thread-safe
- Default: 10,000 events/sec

---

### 6. Enhanced Event Bus (rust_components/event_bus/src/bus.rs)

**Обновите EventBus (переименуйте в EnhancedEventBus):**

```rust
pub struct EnhancedEventBus {
    priority_queue: Arc<PriorityQueue>,
    backpressure: Arc<BackpressureHandler>,
    persistence: Arc<RwLock<Option<PersistenceLayer>>>,
    rate_limiter: Arc<RateLimiter>,
    subscribers: Arc<RwLock<HashMap<String, Vec<Subscriber>>>>,
    metrics: Arc<RwLock<BusMetrics>>,
    enable_persistence: bool,
}

#[derive(Default)]
pub struct BusMetrics {
    pub published: u64,
    pub delivered: u64,
    pub dropped: u64,
    pub persisted: u64,
    pub rate_limited: u64,
}

impl EnhancedEventBus {
    pub async fn new(
        enable_persistence: bool,
        redis_url: Option<String>,
    ) -> Result<Self, String> {
        // MUST:
        // 1. Create PriorityQueue
        // 2. Create BackpressureHandler
        // 3. If enable_persistence: create PersistenceLayer
        // 4. Create RateLimiter (10k/sec)
        // 5. Initialize subscribers HashMap
        // 6. Initialize metrics
    }
    
    pub async fn subscribe(&self, event_type: &str) -> mpsc::UnboundedReceiver<Event>;
    
    pub async fn publish(&self, event: Event) -> Result<(), PublishError> {
        // MUST:
        // 1. Check rate_limiter.check_rate()
        //    If false: increment metrics.rate_limited, return Err(RateLimited)
        // 
        // 2. Increment metrics.published
        // 
        // 3. Call backpressure.push_with_backpressure(event)
        //    If Err: increment metrics.dropped, return error
        // 
        // 4. If enable_persistence: spawn async task to persist event
        //    (don't wait for persistence to complete)
        // 
        // 5. Deliver to subscribers (deliver_to_subscribers)
        // 
        // 6. Return Ok(())
    }
    
    async fn deliver_to_subscribers(&self, event: Event);
    
    pub async fn replay(&self, start_id: &str, count: usize) -> Result<Vec<Event>, String>;
    
    pub async fn get_metrics(&self) -> BusMetrics;
}

#[derive(Debug)]
pub enum PublishError {
    RateLimited,
    Backpressure(String),
}
```

---

### 7. Python Bindings (rust_components/event_bus/src/python_bindings.rs)

**Обновите PyEventBus:**

```rust
#[pyclass]
pub struct PyEventBus {
    bus: Arc<Mutex<EnhancedEventBus>>,
    runtime: Arc<tokio::runtime::Runtime>,
}

#[pymethods]
impl PyEventBus {
    #[new]
    #[pyo3(signature = (enable_persistence=false, redis_url=None))]
    fn new(enable_persistence: bool, redis_url: Option<String>) -> PyResult<Self>;
    
    fn publish(
        &self,
        event_type: String,
        source: String,
        payload: &PyDict,
        priority: Option<String>,  // "critical", "high", "normal", "low"
    ) -> PyResult<()> {
        // MUST:
        // 1. Convert priority string to Priority enum
        // 2. Create Event with priority
        // 3. Call bus.publish(event)
    }
    
    fn replay(&self, start_id: String, count: usize) -> PyResult<Vec<String>> {
        // Return events as JSON strings
    }
    
    fn get_metrics(&self) -> PyResult<PyObject> {
        // Return dict with metrics
    }
}
```

---

## ТЕСТЫ

### Unit Tests

**tests/priority_queue_test.rs:**
```rust
#[tokio::test]
async fn test_priority_ordering() {
    let queue = PriorityQueue::new();
    
    let low = Event::new(...).with_priority(Priority::Low);
    let critical = Event::new(...).with_priority(Priority::Critical);
    let normal = Event::new(...).with_priority(Priority::Normal);
    
    queue.push(low).await.unwrap();
    queue.push(normal).await.unwrap();
    queue.push(critical).await.unwrap();
    
    // Pop should return CRITICAL first
    assert_eq!(queue.pop().await.unwrap().priority, Priority::Critical);
    assert_eq!(queue.pop().await.unwrap().priority, Priority::Normal);
    assert_eq!(queue.pop().await.unwrap().priority, Priority::Low);
}

#[tokio::test]
async fn test_queue_capacity() {
    let queue = PriorityQueue::new();
    
    // Fill to capacity
    for i in 0..Priority::Critical.queue_capacity() {
        queue.push(Event::new(...).with_priority(Priority::Critical)).await.unwrap();
    }
    
    // Next push should fail
    let result = queue.push(Event::new(...).with_priority(Priority::Critical)).await;
    assert!(matches!(result, Err(PushError::CriticalQueueFull)));
}
```

---

### Integration Test

**tests/integration_test.rs:**
```rust
#[tokio::test]
async fn test_persistence_and_replay() {
    let redis_url = "redis://localhost:6379";
    let bus = EnhancedEventBus::new(true, Some(redis_url.to_string())).await.unwrap();
    
    // Publish 10 events
    for i in 0..10 {
        let event = Event::new(format!("EVENT_{}", i), "test".into(), json!({"i": i}));
        bus.publish(event).await.unwrap();
    }
    
    // Wait for persistence
    tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
    
    // Replay
    let events = bus.replay("0", 10).await.unwrap();
    assert_eq!(events.len(), 10);
}
```

---

### Benchmark

**benches/throughput.rs:**
```rust
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn bench_throughput(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();
    
    c.bench_function("publish_10k", |b| {
        b.to_async(&runtime).iter(|| async {
            let bus = EnhancedEventBus::new(false, None).await.unwrap();
            
            for i in 0..10_000 {
                let event = Event::new("BENCH".into(), "test".into(), json!({"i": i}));
                black_box(bus.publish(event).await.unwrap());
            }
        });
    });
}

criterion_group!(benches, bench_throughput);
criterion_main!(benches);
```

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ И МАСШТАБИРУЕМОСТЬ

### Ожидаемая нагрузка (с учетом роста):

```
Component                Events/sec (пик)    Priority       Persistence
─────────────────────────────────────────────────────────────────────────
Execution Layer          100-500            NORMAL/HIGH     ✅ Required
Risk Engine              50-200             HIGH            ✅ Required
Portfolio                30-100             NORMAL          ✅ Required
Metrics Collector        1000-2000          LOW             ❌ Best-effort
Watchdog                 10-50              HIGH            ✅ Required
Kill Switch              <1                 CRITICAL        ✅ Required
Strategy Manager         20-100             NORMAL          ❌ Optional
─────────────────────────────────────────────────────────────────────────
TOTAL                    ~2,500 events/sec  Mixed           60% persist
```

### Критические узкие места:

#### 1. Redis Streams write latency

**Проблема:** XADD команда занимает ~1-2ms → bottleneck при 500+ persisted events/sec.

**Решение: Batch persistence**

```rust
pub struct PersistenceLayer {
    redis: redis::aio::ConnectionManager,
    batch_buffer: Vec<Event>,
    batch_size: usize,      // 100 событий
    batch_timeout: Duration, // 10ms
}

impl PersistenceLayer {
    /// Сохранить событие (с batching)
    pub async fn persist(&mut self, event: Event) -> Result<(), PersistError> {
        self.batch_buffer.push(event);
        
        // Flush если batch готов
        if self.batch_buffer.len() >= self.batch_size {
            self.flush_batch().await?;
        }
        
        Ok(())
    }
    
    /// Flush batch в Redis
    async fn flush_batch(&mut self) -> Result<(), PersistError> {
        if self.batch_buffer.is_empty() {
            return Ok(());
        }
        
        let mut pipe = redis::pipe();
        
        for event in &self.batch_buffer {
            let stream_key = format!("events:{}", event.event_type);
            let json = serde_json::to_string(event)?;
            pipe.xadd(&stream_key, "*", &[("event_json", json)]);
        }
        
        // Один roundtrip для всего batch
        pipe.query_async(&mut self.redis).await?;
        
        tracing::info!(
            "Batch сохранен в Redis",
            events_count = self.batch_buffer.len()
        );
        
        self.batch_buffer.clear();
        Ok(())
    }
    
    /// Background flush по таймеру
    pub async fn run_flush_timer(&mut self) {
        let mut interval = tokio::time::interval(self.batch_timeout);
        
        loop {
            interval.tick().await;
            if let Err(e) = self.flush_batch().await {
                tracing::error!("Ошибка flush batch", error = %e);
            }
        }
    }
}
```

**Результат:**
- 100 событий → 1 XADD вместо 100 XADD
- Latency: 1-2ms вместо 100-200ms
- Throughput: 10,000+ persisted events/sec

#### 2. Priority Queue lock contention

**Проблема:** RwLock на всей PriorityQueue блокирует concurrent publishers.

**Решение: Per-priority locks**

```rust
pub struct PriorityQueue {
    critical: Mutex<VecDeque<Event>>,  // Отдельный lock
    high: Mutex<VecDeque<Event>>,      // Отдельный lock
    normal: Mutex<VecDeque<Event>>,    // Отдельный lock
    low: Mutex<VecDeque<Event>>,       // Отдельный lock
}

impl PriorityQueue {
    pub async fn push(&self, event: Event) -> Result<(), QueueFullError> {
        // Блокируется только одна очередь
        match event.priority {
            Priority::Critical => {
                let mut queue = self.critical.lock().await;
                if queue.len() >= Priority::Critical.queue_capacity() {
                    return Err(QueueFullError::Critical);
                }
                queue.push_back(event);
            }
            // ... остальные приоритеты
        }
        Ok(())
    }
    
    pub async fn pop(&self) -> Option<Event> {
        // Попытка взять из CRITICAL (без блокировки)
        if let Ok(mut queue) = self.critical.try_lock() {
            if let Some(event) = queue.pop_front() {
                return Some(event);
            }
        }
        
        // Попытка из HIGH
        if let Ok(mut queue) = self.high.try_lock() {
            if let Some(event) = queue.pop_front() {
                return Some(event);
            }
        }
        
        // ... NORMAL, LOW
        
        None
    }
}
```

**Результат:**
- Concurrent publishers на разных приоритетах не блокируют друг друга
- Throughput: 3x-5x улучшение при mixed priority load

#### 3. Memory pressure при backpressure

**Проблема:** При backpressure очереди растут → OOM.

**Решение: Bounded queues + overflow to disk**

```rust
pub struct EventBus {
    priority_queue: PriorityQueue,
    overflow_queue: DiskBackedQueue,  // ✅ НОВОЕ: disk backup
    memory_limit: usize,  // 500 MB
}

impl EventBus {
    async fn publish(&self, event: Event) -> Result<(), PublishError> {
        // Проверить memory usage
        let current_memory = self.estimate_memory_usage();
        
        if current_memory > self.memory_limit {
            tracing::warn!(
                "Memory limit достигнут, overflow на диск",
                current_mb = current_memory / 1_048_576
            );
            
            // Отправить в disk-backed overflow queue
            if event.priority >= Priority::Normal {
                self.overflow_queue.push(event).await?;
                return Ok(());
            } else {
                // LOW priority → дроп
                return Err(PublishError::Dropped);
            }
        }
        
        // ... нормальная публикация
    }
}
```

**Overflow Queue (disk-backed):**
```rust
pub struct DiskBackedQueue {
    file: tokio::fs::File,
    index: Vec<u64>,  // Offsets в файле
}

impl DiskBackedQueue {
    async fn push(&mut self, event: &Event) -> Result<(), io::Error> {
        // Append в файл
        let json = serde_json::to_vec(event)?;
        let offset = self.file.seek(SeekFrom::End(0)).await?;
        self.file.write_all(&json).await?;
        self.file.write_all(b"
").await?;
        
        // Сохранить offset
        self.index.push(offset);
        
        Ok(())
    }
    
    async fn pop(&mut self) -> Result<Option<Event>, io::Error> {
        if let Some(offset) = self.index.pop() {
            // Прочитать с offset
            self.file.seek(SeekFrom::Start(offset)).await?;
            // ... read JSON line
        }
        Ok(None)
    }
}
```

---

## 📊 ОБЯЗАТЕЛЬНЫЕ BENCHMARK ТЕСТЫ

### benches/throughput.rs (Rust):

```rust
use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use event_bus::{EventBus, Event, Priority};
use serde_json::json;

fn bench_priority_queues(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();
    let bus = EventBus::new();
    
    let mut group = c.benchmark_group("priority_queues");
    
    for priority in &[Priority::Critical, Priority::High, Priority::Normal, Priority::Low] {
        group.bench_with_input(
            BenchmarkId::from_parameter(format!("{:?}", priority)),
            priority,
            |b, &prio| {
                b.to_async(&runtime).iter(|| async {
                    let event = Event::new("BENCH".into(), "test".into(), json!({}))
                        .with_priority(prio);
                    black_box(bus.publish(event).await.unwrap());
                });
            },
        );
    }
    
    group.finish();
}

fn bench_backpressure_handling(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();
    
    c.bench_function("backpressure_low_drop", |b| {
        b.to_async(&runtime).iter(|| async {
            let bus = EventBus::new();
            
            // Заполнить очередь
            for i in 0..100_000 {
                let event = Event::new("FILL".into(), "test".into(), json!({"i": i}))
                    .with_priority(Priority::Low);
                let _ = bus.publish(event).await;
            }
            
            // Попытка добавить еще LOW → должно дропнуть
            let event = Event::new("DROP".into(), "test".into(), json!({}))
                .with_priority(Priority::Low);
            
            black_box(bus.publish(event).await);
        });
    });
}

fn bench_persistence_batch(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();
    
    c.bench_function("persist_batch_100", |b| {
        b.to_async(&runtime).iter(|| async {
            let mut persistence = PersistenceLayer::new(redis_url).await.unwrap();
            
            // Batch из 100 событий
            for i in 0..100 {
                let event = Event::new("PERSIST".into(), "test".into(), json!({"i": i}))
                    .with_priority(Priority::High);
                persistence.persist(event).await.unwrap();
            }
            
            // Flush
            persistence.flush_batch().await.unwrap();
        });
    });
}

criterion_group!(
    benches,
    bench_priority_queues,
    bench_backpressure_handling,
    bench_persistence_batch
);
criterion_main!(benches);
```

**Acceptance Criteria для benchmarks:**
```
✅ publish (CRITICAL): median <500μs, p99 <2ms
✅ publish (HIGH): median <800μs, p99 <5ms
✅ publish (NORMAL): median <1ms, p99 <10ms
✅ publish (LOW): median <1.5ms, p99 <20ms

✅ backpressure_low_drop: <5ms для 100K событий (дропы без задержки)
✅ persist_batch_100: <50ms (batch из 100 событий)

✅ throughput_mixed: >2,500 events/sec (mixed priorities)
✅ memory_usage: <500 MB при 100K событий в очередях
```

### tests/integration/test_event_bus_load.py (Python):

```python
import pytest
import asyncio
from event_bus import PyEventBus

@pytest.mark.benchmark
async def test_sustained_high_load():
    """
    Проверить sustained load 2000 events/sec в течение 10 секунд.
    
    Acceptance: 
    - Dropped events < 1%
    - Latency p99 < 50ms
    - Memory < 500 MB
    """
    bus = PyEventBus()
    subscriber = bus.subscribe("LOAD_TEST")
    
    # Публиковать 2000 events/sec в течение 10 секунд
    start = asyncio.get_event_loop().time()
    total_events = 20_000
    
    async def publisher():
        for i in range(total_events):
            await bus.publish("LOAD_TEST", "bench", {"index": i}, priority="normal")
            if i % 2000 == 0:
                await asyncio.sleep(0.01)  # Throttle to ~2000/sec
    
    await publisher()
    end = asyncio.get_event_loop().time()
    
    # Assertions
    duration = end - start
    assert duration < 12.0, f"Took {duration}s, expected ~10s"
    
    metrics = bus.get_metrics()
    dropped_rate = metrics["dropped"] / total_events
    assert dropped_rate < 0.01, f"Dropped {dropped_rate*100}% > 1%"

@pytest.mark.benchmark
async def test_priority_ordering():
    """
    Проверить что CRITICAL события обрабатываются перед LOW.
    """
    bus = PyEventBus()
    subscriber = bus.subscribe("PRIORITY_TEST")
    
    # Публиковать в обратном порядке приоритета
    await bus.publish("PRIORITY_TEST", "test", {"p": "low"}, priority="low")
    await bus.publish("PRIORITY_TEST", "test", {"p": "normal"}, priority="normal")
    await bus.publish("PRIORITY_TEST", "test", {"p": "high"}, priority="high")
    await bus.publish("PRIORITY_TEST", "test", {"p": "critical"}, priority="critical")
    
    # Получить события
    events = []
    for _ in range(4):
        event = subscriber.recv_timeout(1.0)
        events.append(event["payload"]["p"])
    
    # Порядок должен быть: critical, high, normal, low
    assert events == ["critical", "high", "normal", "low"]

@pytest.mark.benchmark
async def test_persistence_replay():
    """
    Проверить что можно replay события из Redis.
    """
    bus = PyEventBus()
    
    # Публиковать HIGH события (с persistence)
    for i in range(100):
        await bus.publish("REPLAY_TEST", "test", {"index": i}, priority="high")
    
    # Подождать flush
    await asyncio.sleep(0.5)
    
    # Replay из Redis
    replayed = await bus.replay_from_stream("events:REPLAY_TEST", count=100)
    
    assert len(replayed) == 100
    assert replayed[0]["payload"]["index"] == 0
    assert replayed[99]["payload"]["index"] == 99
```

---

## ACCEPTANCE CRITERIA

### Rust Components
- [ ] Priority enum с 4 уровнями
- [ ] PriorityQueue push/pop по приоритету
- [ ] BackpressureHandler дропает LOW events
- [ ] CRITICAL events не дропаются (только timeout)
- [ ] PersistenceLayer сохраняет в Redis Streams
- [ ] replay() восстанавливает события
- [ ] RateLimiter ограничивает 10k/sec
- [ ] EnhancedEventBus интегрирует все компоненты
- [ ] Python bindings работают с priority

### Testing
- [ ] test_priority_ordering проходит
- [ ] test_queue_capacity проходит
- [ ] test_persistence_and_replay проходит
- [ ] bench_throughput >= 10k msg/sec
- [ ] Latency p99 < 5ms

### Build
- [ ] `cargo build --release` успешен
- [ ] `cargo test` все тесты проходят
- [ ] `cargo clippy` без warnings
- [ ] `cargo bench` benchmarks работают
- [ ] `maturin build` создает wheel
- [ ] Python import успешен

---

## СТИЛЬ КОДА

### Rust:
```rust
// CRYPTOTEHNOLOG v1.3.0
// Phase 3: Event Bus Enhancement
// Component: Priority Queue
// File: priority_queue.rs

use std::collections::VecDeque;
use tokio::sync::Mutex;
use crate::event::Event;
use crate::priority::Priority;

/// Priority-based event queue with 4 levels.
/// 
/// Events are dequeued in priority order: Critical > High > Normal > Low.
/// Each priority level has a separate queue with fixed capacity.
pub struct PriorityQueue {
    critical: Mutex<VecDeque<Event>>,
    // ...
}

impl PriorityQueue {
    /// Create a new priority queue.
    pub fn new() -> Self {
        // Implementation
    }
}
```

---

## 📤 ФОРМАТ ВЫДАЧИ

Для каждого файла:
1. Напишите полный путь
2. Покажите ВЕСЬ код
3. Добавьте header комментарий
4. После кода: "✅ filename READY"

В конце:
```
📦 GENERATED FILES:
- rust_components/event_bus/Cargo.toml ✅
- rust_components/event_bus/src/priority.rs ✅
- rust_components/event_bus/src/priority_queue.rs ✅
- rust_components/event_bus/src/backpressure.rs ✅
- rust_components/event_bus/src/persistence.rs ✅
- rust_components/event_bus/src/rate_limiter.rs ✅
- rust_components/event_bus/src/bus.rs ✅
- rust_components/event_bus/src/python_bindings.rs ✅
- tests/priority_queue_test.rs ✅
- tests/integration_test.rs ✅
- benches/throughput.rs ✅

🧪 NEXT STEPS:
1. cd rust_components/event_bus
2. cargo build --release
3. cargo test
4. cargo bench
5. maturin develop --release
6. python -c "from event_bus import PyEventBus; print('OK')"
```

---

## ✅ КАК ПРОВЕРИТЬ РЕЗУЛЬТАТ

### 1. Rust Build
```bash
cd rust_components/event_bus
cargo build --release
```
**Ожидаемо:** `Finished release [optimized]`

### 2. Rust Tests
```bash
cargo test
```
**Ожидаемо:** `test result: ok. X passed`

### 3. Clippy (linter)
```bash
cargo clippy -- -D warnings
```
**Ожидаемо:** No warnings

### 4. Benchmarks
```bash
cargo bench
```
**Ожидаемо:** `publish_10k ... time: [X.XX ms ...]` (должно быть <1 sec для 10k)

### 5. Python Bindings
```bash
maturin develop --release
python -c "
from event_bus import PyEventBus
bus = PyEventBus(enable_persistence=False)
bus.publish('TEST', 'test', {'key': 'value'}, priority='high')
print('✅ Python bindings OK')
"
```
**Ожидаемо:** `✅ Python bindings OK`

### 6. Python Integration Test
```bash
cd ../..
pytest tests/integration/test_event_bus_enhanced.py -v
```
**Ожидаемо:** All tests pass

---

## ВАЖНО

1. **НЕ используйте TODO или NOT IMPLEMENTED**
2. **Error handling везде** (Result<T, E>)
3. **Async/await корректно** (tokio runtime)
4. **Thread-safety** (Arc, Mutex, RwLock where needed)
5. **Persistence асинхронная** (не блокирует publish)
6. **Metrics атомарные** (RwLock для безопасности)
7. **Priority строго соблюдается**

---

**Успехов в реализации Event Bus Enhancement!** 🚀
