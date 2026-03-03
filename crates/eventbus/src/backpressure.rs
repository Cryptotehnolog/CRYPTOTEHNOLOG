// ==================== CRYPTOTEHNOLOG Backpressure Handler ====================
// Обработчик обратного давления для Event Bus
//
// Реализует стратегии обработки переполнения очередей:
// - DropLow: дропать низкоприоритетные события
// - DropNormal: дропать normal + low
// - Overflow: переполнение в overflow queue
// - BlockCritical: блокировать только critical

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

use parking_lot::RwLock;

use crate::event::Event;
use crate::priority::Priority;
use crate::priority_queue::{new_sync_queue_with_capacity, PushResult, QueueCapacity, SyncPriorityQueue};

/// Стратегия backpressure при переполнении очереди
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum BackpressureStrategy {
    /// Дропать low priority события при переполнении
    #[default]
    DropLow,
    
    /// Дропать normal + low priority события при переполнении
    DropNormal,
    
    /// Перенаправлять в overflow queue при переполнении
    Overflow,
    
    /// Блокировать только critical, остальное дропать
    BlockCritical,
}



impl BackpressureStrategy {
    /// Получить строковое представление стратегии
    pub fn as_str(&self) -> &'static str {
        match self {
            BackpressureStrategy::DropLow => "drop_low",
            BackpressureStrategy::DropNormal => "drop_normal",
            BackpressureStrategy::Overflow => "overflow",
            BackpressureStrategy::BlockCritical => "block_critical",
        }
    }
    
 /// Создать стратегию из строки
 pub fn parse(s: &str) -> Option<Self> {
 if s.eq_ignore_ascii_case("drop_low") {
 Some(BackpressureStrategy::DropLow)
 } else if s.eq_ignore_ascii_case("drop_normal") {
 Some(BackpressureStrategy::DropNormal)
 } else if s.eq_ignore_ascii_case("overflow") {
 Some(BackpressureStrategy::Overflow)
 } else if s.eq_ignore_ascii_case("block_critical") {
 Some(BackpressureStrategy::BlockCritical)
 } else {
 None
 }
 }
}

impl std::str::FromStr for BackpressureStrategy {
 type Err = &'static str;

 fn from_str(s: &str) -> Result<Self, Self::Err> {
 Self::parse(s).ok_or("Неверная стратегия backpressure")
 }
}

/// Результат обработки backpressure
#[derive(Debug, Clone, PartialEq)]
pub enum HandleResult {
    /// Событие успешно обработано
    Accepted,
    
    /// Событие отброшено
    Dropped(Priority),
    
    /// Publisher заблокирован (для critical)
    Blocked,
    
    /// Таймаут при ожидании освобождения места
    Timeout,
}

/// Статистика отброшенных событий
#[derive(Debug, Clone, Default)]
pub struct DroppedStats {
    /// Количество отброшенных Critical событий
    pub dropped_critical: u64,
    /// Количество отброшенных High событий
    pub dropped_high: u64,
    /// Количество отброшенных Normal событий
    pub dropped_normal: u64,
    /// Количество отброшенных Low событий
    pub dropped_low: u64,
    /// Общее количество блокировок Critical
    pub blocked_critical: u64,
    /// Количество таймаутов
    pub timeouts: u64,
}

impl DroppedStats {
    /// Получить общее количество отброшенных событий
    pub fn total_dropped(&self) -> u64 {
        self.dropped_critical + self.dropped_high + self.dropped_normal + self.dropped_low
    }
    
    /// Сбросить все счетчики
    pub fn reset(&mut self) {
        self.dropped_critical = 0;
        self.dropped_high = 0;
        self.dropped_normal = 0;
        self.dropped_low = 0;
        self.blocked_critical = 0;
        self.timeouts = 0;
    }
}

/// Метрики backpressure
#[derive(Debug, Clone, Default)]
pub struct BackpressureMetrics {
    /// Количество отброшенных событий по приоритетам
    pub dropped: DroppedStats,
    /// Активные блокировки по приоритетам
    pub active_blocks: u64,
    /// Количество срабатываний backpressure
    pub trigger_count: u64,
}

/// Обработчик backpressure
///
/// # Описание
///
/// BackpressureHandler управляет потоком событий при переполнении очередей.
/// Реализует различные стратегии в зависимости от приоритета события и
/// текущей заполненности очередей.
///
/// # Стратегии
///
/// - **DropLow**: При переполнении High/Normal очереди дропаем Low
/// - **DropNormal**: При переполнении High дропаем Normal + Low
/// - **Overflow**: Перенаправляем в отдельную overflow queue
/// - **BlockCritical**: Для Critical - блокируем publisher
pub struct BackpressureHandler {
    /// Приоритетная очередь
    queue: SyncPriorityQueue,
    
    /// Текущая стратегия
    strategy: RwLock<BackpressureStrategy>,
    
    /// Порог заполнения для активации backpressure (0.0 - 1.0)
    threshold: RwLock<f64>,
    
    /// Максимальное количество попыток при блокировке
    #[allow(dead_code)]
    max_retries: usize,
    
    /// Таймаут ожидания освобождения места (мс)
    #[allow(dead_code)]
    timeout_ms: u64,
    
    /// Метрики (atomic для производительности)
    dropped_low: Arc<AtomicU64>,
    dropped_high: Arc<AtomicU64>,
    dropped_normal: Arc<AtomicU64>,
    dropped_critical: Arc<AtomicU64>,
    blocked_critical: Arc<AtomicU64>,
    timeouts: Arc<AtomicU64>,
    trigger_count: Arc<AtomicU64>,
}

impl BackpressureHandler {
    /// Создать новый обработчик backpressure
    ///
    /// # Аргументы
    ///
    /// * `capacity` - Емкость очередей
    ///
    /// # Возвращаемое значение
    ///
    /// Новый BackpressureHandler
    pub fn new(capacity: QueueCapacity) -> Self {
        Self {
            queue: new_sync_queue_with_capacity(capacity),
            strategy: RwLock::new(BackpressureStrategy::default()),
            threshold: RwLock::new(0.9), // 90% по умолчанию
            max_retries: 5,
            timeout_ms: 5000, // 5 секунд
            dropped_low: Arc::new(AtomicU64::new(0)),
            dropped_high: Arc::new(AtomicU64::new(0)),
            dropped_normal: Arc::new(AtomicU64::new(0)),
            dropped_critical: Arc::new(AtomicU64::new(0)),
            blocked_critical: Arc::new(AtomicU64::new(0)),
            timeouts: Arc::new(AtomicU64::new(0)),
            trigger_count: Arc::new(AtomicU64::new(0)),
        }
    }
    
    /// Создать с стратегией по умолчанию
    pub fn with_strategy(capacity: QueueCapacity, strategy: BackpressureStrategy) -> Self {
        let handler = Self::new(capacity);
        *handler.strategy.write() = strategy;
        handler
    }
    
    /// Получить ссылку на очередь
    pub fn queue(&self) -> &SyncPriorityQueue {
        &self.queue
    }
    
    /// Установить стратегию backpressure
    pub fn set_strategy(&self, strategy: BackpressureStrategy) {
        *self.strategy.write() = strategy;
    }
    
    /// Получить текущую стратегию
    pub fn get_strategy(&self) -> BackpressureStrategy {
        *self.strategy.read()
    }
    
    /// Установить порог заполнения
    pub fn set_threshold(&self, threshold: f64) {
        *self.threshold.write() = threshold.clamp(0.0, 1.0);
    }
    
    /// Получить порог заполнения
    pub fn get_threshold(&self) -> f64 {
        *self.threshold.read()
    }
    
    /// Проверить заполненность очереди
    #[allow(dead_code)]
    fn is_queue_full(&self, priority: Priority) -> bool {
        let queue = self.queue.read();
        let fill_ratio = queue.fill_ratio(priority);
        fill_ratio >= *self.threshold.read()
    }
    
    /// Добавить событие с обработкой backpressure
    ///
    /// # Аргументы
    ///
    /// * `event` - Событие для добавления
    ///
    /// # Возвращаемое значение
    ///
    /// HandleResult - результат обработки
    pub fn push(&self, event: Event) -> HandleResult {
        let priority = event.priority;
        let strategy = *self.strategy.read();
        
        // Пробуем добавить напрямую (клонируем для сохранения оригинала)
        let event_for_push = event.clone();
        {
            let mut queue = self.queue.write();
            match queue.push(event_for_push) {
                PushResult::Ok => return HandleResult::Accepted,
                PushResult::CriticalQueueFull => {
                    // CRITICAL никогда не дропаем!
                    return self.handle_critical_full(queue, event, strategy);
                }
                _ => {} // Продолжаем с backpressure логикой
            }
        }
        
        // Применяем стратегию backpressure
        self.trigger_count.fetch_add(1, Ordering::Relaxed);
        
        match strategy {
            BackpressureStrategy::DropLow => self.handle_drop_low(priority),
            BackpressureStrategy::DropNormal => self.handle_drop_normal(priority),
            BackpressureStrategy::Overflow => self.handle_overflow(priority),
            BackpressureStrategy::BlockCritical => self.handle_block_critical(priority),
        }
    }
    
    /// Обработать переполнение Critical очереди
    fn handle_critical_full(
        &self, 
        mut queue: parking_lot::RwLockWriteGuard<'_, crate::priority_queue::PriorityQueue>,
        event: Event,
        _strategy: BackpressureStrategy,
    ) -> HandleResult {
        // Для Critical - пытаемся освободить место
        let dropped = queue.drop_normal_events(50);
        if dropped > 0 {
            // Пробуем еще раз (клонируем event)
            if queue.push(event.clone()).is_ok() {
                return HandleResult::Accepted;
            }
        }
        
        // Пробуем дропнуть low
        queue.drop_low_events(100);
        if queue.push(event).is_ok() {
            return HandleResult::Accepted;
        }
        
        // Блокируем (для Critical)
        self.blocked_critical.fetch_add(1, Ordering::Relaxed);
        HandleResult::Blocked
    }
    
    /// Обработать по стратегии DropLow
    fn handle_drop_low(&self, priority: Priority) -> HandleResult {
        // Пробуем дропнуть low события
        let mut queue = self.queue.write();
        
        match priority {
            Priority::Low => {
                // Low дропаем сразу
                self.dropped_low.fetch_add(1, Ordering::Relaxed);
                HandleResult::Dropped(Priority::Low)
            }
            Priority::Normal => {
                // Пробуем дропнуть 10 low
                let dropped = queue.drop_low_events(10);
                if dropped > 0 {
                    // Пробуем добавить нормальное
                    let event = Event::new("temp", "temp", serde_json::json!({}))
                        .with_priority(Priority::Normal);
                    if queue.push(event).is_ok() {
                        return HandleResult::Accepted;
                    }
                }
                // Дропаем normal
                self.dropped_normal.fetch_add(1, Ordering::Relaxed);
                HandleResult::Dropped(Priority::Normal)
            }
            Priority::High => {
                // Пробуем дропнуть 50 low + 20 normal
                queue.drop_low_events(50);
                let dropped = queue.drop_normal_events(20);
                if dropped > 0 {
                    return HandleResult::Accepted;
                }
                // Дропаем high (редкий случай!)
                self.dropped_high.fetch_add(1, Ordering::Relaxed);
                HandleResult::Dropped(Priority::High)
            }
            Priority::Critical => {
                // Critical не дропаем!
                self.blocked_critical.fetch_add(1, Ordering::Relaxed);
                HandleResult::Blocked
            }
        }
    }
    
    /// Обработать по стратегии DropNormal
    fn handle_drop_normal(&self, priority: Priority) -> HandleResult {
        let mut queue = self.queue.write();
        
        match priority {
            Priority::Low | Priority::Normal => {
                // Дропаем сразу
                if priority == Priority::Low {
                    self.dropped_low.fetch_add(1, Ordering::Relaxed);
                } else {
                    self.dropped_normal.fetch_add(1, Ordering::Relaxed);
                }
                HandleResult::Dropped(priority)
            }
            Priority::High => {
                // Пробуем дропнуть normal + low
                queue.drop_normal_events(30);
                queue.drop_low_events(50);
                if queue.push(Event::new("temp", "temp", serde_json::json!({}))
                    .with_priority(Priority::High)).is_ok() {
                    return HandleResult::Accepted;
                }
                self.dropped_high.fetch_add(1, Ordering::Relaxed);
                HandleResult::Dropped(Priority::High)
            }
            Priority::Critical => {
                // Дропаем все кроме critical
                queue.drop_normal_events(100);
                queue.drop_low_events(100);
                if queue.push(Event::new("temp", "temp", serde_json::json!({}))
                    .with_priority(Priority::Critical)).is_ok() {
                    return HandleResult::Accepted;
                }
                self.blocked_critical.fetch_add(1, Ordering::Relaxed);
                HandleResult::Blocked
            }
        }
    }
    
    /// Обработать по стратегии Overflow
    fn handle_overflow(&self, priority: Priority) -> HandleResult {
        // Overflow пока реализуем как drop для low/normal
        // Полноценная overflow queue будет в persistence layer
        match priority {
            Priority::Critical => {
                self.blocked_critical.fetch_add(1, Ordering::Relaxed);
                HandleResult::Blocked
            }
            Priority::High => {
                self.dropped_high.fetch_add(1, Ordering::Relaxed);
                HandleResult::Dropped(Priority::High)
            }
            Priority::Normal => {
                self.dropped_normal.fetch_add(1, Ordering::Relaxed);
                HandleResult::Dropped(Priority::Normal)
            }
            Priority::Low => {
                self.dropped_low.fetch_add(1, Ordering::Relaxed);
                HandleResult::Dropped(Priority::Low)
            }
        }
    }
    
    /// Обработать по стратегии BlockCritical
    fn handle_block_critical(&self, priority: Priority) -> HandleResult {
        let mut queue = self.queue.write();
        
        match priority {
            Priority::Critical => {
                // Блокируем
                self.blocked_critical.fetch_add(1, Ordering::Relaxed);
                HandleResult::Blocked
            }
            Priority::High => {
                // Пробуем освободить место
                queue.drop_normal_events(50);
                queue.drop_low_events(50);
                if queue.push(Event::new("temp", "temp", serde_json::json!({}))
                    .with_priority(Priority::High)).is_ok() {
                    return HandleResult::Accepted;
                }
                self.dropped_high.fetch_add(1, Ordering::Relaxed);
                HandleResult::Dropped(Priority::High)
            }
            Priority::Normal => {
                queue.drop_low_events(30);
                if queue.push(Event::new("temp", "temp", serde_json::json!({}))
                    .with_priority(Priority::Normal)).is_ok() {
                    return HandleResult::Accepted;
                }
                self.dropped_normal.fetch_add(1, Ordering::Relaxed);
                HandleResult::Dropped(Priority::Normal)
            }
            Priority::Low => {
                self.dropped_low.fetch_add(1, Ordering::Relaxed);
                HandleResult::Dropped(Priority::Low)
            }
        }
    }
    
    /// Извлечь событие с наивысшим приоритетом
    pub fn pop(&self) -> Option<Event> {
        let mut queue = self.queue.write();
        queue.pop()
    }
    
    /// Получить размер очереди
    pub fn len(&self) -> usize {
        let queue = self.queue.read();
        queue.len()
    }
    
    /// Проверить пуста ли очередь
    pub fn is_empty(&self) -> bool {
        let queue = self.queue.read();
        queue.is_empty()
    }
    
    /// Получить статистику отброшенных событий
    pub fn get_dropped_stats(&self) -> DroppedStats {
        DroppedStats {
            dropped_critical: self.dropped_critical.load(Ordering::Relaxed),
            dropped_high: self.dropped_high.load(Ordering::Relaxed),
            dropped_normal: self.dropped_normal.load(Ordering::Relaxed),
            dropped_low: self.dropped_low.load(Ordering::Relaxed),
            blocked_critical: self.blocked_critical.load(Ordering::Relaxed),
            timeouts: self.timeouts.load(Ordering::Relaxed),
        }
    }
    
    /// Получить полные метрики backpressure
    pub fn get_metrics(&self) -> BackpressureMetrics {
        BackpressureMetrics {
            dropped: self.get_dropped_stats(),
            active_blocks: 0, // TODO: реализовать отслеживание активных блокировок
            trigger_count: self.trigger_count.load(Ordering::Relaxed),
        }
    }
    
    /// Сбросить метрики
    pub fn reset_metrics(&self) {
        self.dropped_low.store(0, Ordering::Relaxed);
        self.dropped_high.store(0, Ordering::Relaxed);
        self.dropped_normal.store(0, Ordering::Relaxed);
        self.dropped_critical.store(0, Ordering::Relaxed);
        self.blocked_critical.store(0, Ordering::Relaxed);
        self.timeouts.store(0, Ordering::Relaxed);
        self.trigger_count.store(0, Ordering::Relaxed);
    }
    
    /// Получить заполненность конкретной очереди
    pub fn fill_ratio(&self, priority: Priority) -> f64 {
        let queue = self.queue.read();
        queue.fill_ratio(priority)
    }
}

impl Default for BackpressureHandler {
    fn default() -> Self {
        Self::new(QueueCapacity::default())
    }
}

/// Thread-safe обертка для BackpressureHandler
pub type SyncBackpressureHandler = Arc<BackpressureHandler>;

/// Создать новый синхронизированный обработчик backpressure
pub fn new_backpressure_handler() -> SyncBackpressureHandler {
    Arc::new(BackpressureHandler::default())
}

/// Создать с указанной стратегией
pub fn new_backpressure_handler_with_strategy(
    strategy: BackpressureStrategy,
) -> SyncBackpressureHandler {
    Arc::new(BackpressureHandler::with_strategy(
        QueueCapacity::default(),
        strategy,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_event(priority: Priority) -> Event {
        Event::new("TEST", "SOURCE", serde_json::json!({}))
            .with_priority(priority)
    }

    #[test]
    fn test_handler_basic() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        // Normal событие должно пройти
        let event = create_test_event(Priority::Normal);
        let result = handler.push(event);
        assert_eq!(result, HandleResult::Accepted);
    }

    #[test]
    fn test_handler_critical_never_dropped() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        // Заполняем очередь
        for _ in 0..200 {
            handler.push(create_test_event(Priority::Normal));
        }
        
        // Critical должен пройти или заблокировать, но не дропнуться
        let event = create_test_event(Priority::Critical);
        let result = handler.push(event);
        
        // Не должен быть Dropped(Priority::Critical)
        match result {
            HandleResult::Dropped(Priority::Critical) => panic!("Critical was dropped!"),
            _ => {} // Accepted, Blocked или Timeout допустимы
        }
    }

    #[test]
    fn test_handler_low_dropped_on_overflow() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        // Заполняем очередь полностью low событиями
        for _ in 0..50_000 {
            handler.push(create_test_event(Priority::Low));
        }
        
        // Следующий low должен быть дропнут
        let result = handler.push(create_test_event(Priority::Low));
        assert_eq!(result, HandleResult::Dropped(Priority::Low));
        
        let stats = handler.get_dropped_stats();
        assert!(stats.dropped_low > 0);
    }

    #[test]
    fn test_handler_strategy_change() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        assert_eq!(handler.get_strategy(), BackpressureStrategy::DropLow);
        
        handler.set_strategy(BackpressureStrategy::DropNormal);
        assert_eq!(handler.get_strategy(), BackpressureStrategy::DropNormal);
        
        handler.set_strategy(BackpressureStrategy::BlockCritical);
        assert_eq!(handler.get_strategy(), BackpressureStrategy::BlockCritical);
    }

    #[test]
    fn test_handler_threshold() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        assert_eq!(handler.get_threshold(), 0.9);
        
        handler.set_threshold(0.5);
        assert_eq!(handler.get_threshold(), 0.5);
        
        // Clamp test
        handler.set_threshold(1.5);
        assert_eq!(handler.get_threshold(), 1.0);
        
        handler.set_threshold(-0.5);
        assert_eq!(handler.get_threshold(), 0.0);
    }

    #[test]
    fn test_handler_pop() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        handler.push(create_test_event(Priority::Low));
        handler.push(create_test_event(Priority::High));
        handler.push(create_test_event(Priority::Critical));
        
        // Первым должен прийти Critical
        let first = handler.pop().unwrap();
        assert_eq!(first.priority, Priority::Critical);
        
        let second = handler.pop().unwrap();
        assert_eq!(second.priority, Priority::High);
        
        let third = handler.pop().unwrap();
        assert_eq!(third.priority, Priority::Low);
    }

    #[test]
    fn test_handler_metrics() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        handler.push(create_test_event(Priority::Normal));
        handler.push(create_test_event(Priority::Low));
        
        let stats = handler.get_dropped_stats();
        assert_eq!(stats.total_dropped(), 0);
    }

    #[test]
    fn test_handler_reset_metrics() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        // Заполняем и дропаем
        for _ in 0..50_000 {
            handler.push(create_test_event(Priority::Low));
        }
        handler.push(create_test_event(Priority::Low));
        
        let stats = handler.get_dropped_stats();
        assert!(stats.dropped_low > 0);
        
        handler.reset_metrics();
        
        let stats_after = handler.get_dropped_stats();
        assert_eq!(stats_after.dropped_low, 0);
    }

    #[test]
    fn test_handler_fill_ratio() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        // Normal емкость = 10_000
        for _ in 0..1000 {
            handler.push(create_test_event(Priority::Normal));
        }
        
        let ratio = handler.fill_ratio(Priority::Normal);
        assert!((ratio - 0.1).abs() < 0.001);
    }

    #[test]
    fn test_strategy_from_str() {
        assert_eq!(BackpressureStrategy::parse("drop_low"), Some(BackpressureStrategy::DropLow));
        assert_eq!(BackpressureStrategy::parse("DROP_LOW"), Some(BackpressureStrategy::DropLow));
        assert_eq!(BackpressureStrategy::parse("drop_normal"), Some(BackpressureStrategy::DropNormal));
        assert_eq!(BackpressureStrategy::parse("overflow"), Some(BackpressureStrategy::Overflow));
        assert_eq!(BackpressureStrategy::parse("block_critical"), Some(BackpressureStrategy::BlockCritical));
        assert_eq!(BackpressureStrategy::parse("invalid"), None);
    }

    #[test]
    fn test_handler_len() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        assert!(handler.is_empty());
        assert_eq!(handler.len(), 0);
        
        handler.push(create_test_event(Priority::Normal));
        handler.push(create_test_event(Priority::High));
        
        assert!(!handler.is_empty());
        assert_eq!(handler.len(), 2);
    }

    #[test]
    fn test_handler_trigger_count() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        // Несколько успешных push
        handler.push(create_test_event(Priority::Normal));
        handler.push(create_test_event(Priority::Normal));
        
        // Заполняем до отказа
        for _ in 0..10_000 {
            handler.push(create_test_event(Priority::Normal));
        }
        
        let metrics = handler.get_metrics();
        assert!(metrics.trigger_count > 0);
    }

    #[test]
    fn test_dropped_stats_total() {
        let mut stats = DroppedStats::default();
        stats.dropped_low = 10;
        stats.dropped_normal = 5;
        stats.dropped_high = 2;
        
        assert_eq!(stats.total_dropped(), 17);
    }

    #[test]
    fn test_dropped_stats_reset() {
        let mut stats = DroppedStats::default();
        stats.dropped_low = 10;
        stats.dropped_high = 5;
        
        stats.reset();
        
        assert_eq!(stats.dropped_low, 0);
        assert_eq!(stats.dropped_high, 0);
    }
}
