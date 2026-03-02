// ==================== CRYPTOTEHNOLOG Priority Queue ====================
// Многоприоритетная очередь событий для Event Bus
//
// Очередь разделена на 4 независимых очереди с разными capacity:
// - Critical: 100 событий (максимальный приоритет)
// - High: 500 событий
// - Normal: 10,000 событий
// - Low: 50,000 событий

use std::collections::VecDeque;
use std::sync::Arc;

use parking_lot::RwLock;

use crate::event::Event;
use crate::priority::{Priority, PriorityMetrics};

/// Результат операции push в очередь
#[derive(Debug, Clone, PartialEq)]
pub enum PushResult {
    /// Событие успешно добавлено
    Ok,
    
    /// Очередь критических событий переполнена
    CriticalQueueFull,
    
    /// Очередь высокоприоритетных событий переполнена
    HighQueueFull,
    
    /// Очередь нормальных событий переполнена
    NormalQueueFull,
    
    /// Очередь низкоприоритетных событий переполнена
    LowQueueFull,
}

impl PushResult {
    /// Проверить успешность операции
    pub fn is_ok(&self) -> bool {
        matches!(self, PushResult::Ok)
    }
    
    /// Получить описание ошибки
    pub fn error_message(&self) -> &'static str {
        match self {
            PushResult::Ok => "Успешно",
            PushResult::CriticalQueueFull => "Очередь Critical переполнена",
            PushResult::HighQueueFull => "Очередь High переполнена",
            PushResult::NormalQueueFull => "Очередь Normal переполнена",
            PushResult::LowQueueFull => "Очередь Low переполнена",
        }
    }
}

/// Емкость очередей по приоритетам
#[derive(Debug, Clone)]
pub struct QueueCapacity {
    /// Емкость очереди Critical
    pub critical: usize,
    /// Емкость очереди High
    pub high: usize,
    /// Емкость очереди Normal
    pub normal: usize,
    /// Емкость очереди Low
    pub low: usize,
}

impl Default for QueueCapacity {
    fn default() -> Self {
        Self {
            critical: 100,
            high: 500,
            normal: 10_000,
            low: 50_000,
        }
    }
}

impl QueueCapacity {
    /// Создать новую конфигурацию емкости
    pub fn new(critical: usize, high: usize, normal: usize, low: usize) -> Self {
        Self {
            critical,
            high,
            normal,
            low,
        }
    }
    
    /// Получить емкость для конкретного приоритета
    pub fn get(&self, priority: Priority) -> usize {
        match priority {
            Priority::Critical => self.critical,
            Priority::High => self.high,
            Priority::Normal => self.normal,
            Priority::Low => self.low,
        }
    }
}

/// Многоприоритетная очередь событий
///
/// # Описание
///
/// PriorityQueue реализует 4 отдельных очереди для каждого уровня приоритета.
/// При извлечении событий (pop) всегда возвращается событие с наивысшим приоритетом.
///
/// # Примеры
///
/// ```rust,ignore
/// use cryptotechnolog_eventbus::priority_queue::PriorityQueue;
/// use cryptotechnolog_eventbus::{Event, priority::Priority};
///
/// let mut queue = PriorityQueue::new();
///
/// // Добавить события с разными приоритетами
/// let event_low = Event::new("LOW", "SOURCE", serde_json::json!({}))
///     .with_priority(Priority::Low);
/// let event_high = Event::new("HIGH", "SOURCE", serde_json::json!({}))
///     .with_priority(Priority::High);
///
/// queue.push(event_low).unwrap();
/// queue.push(event_high).unwrap();
///
/// // Извлекаем - первым получим HIGH
/// if let Some(event) = queue.pop() {
///     assert_eq!(event.event_type, "HIGH");
/// }
/// ```
pub struct PriorityQueue {
    /// Очередь критических событий
    critical: VecDeque<Event>,
    
    /// Очередь высокоприоритетных событий
    high: VecDeque<Event>,
    
    /// Очередь нормальных событий
    normal: VecDeque<Event>,
    
    /// Очередь низкоприоритетных событий
    low: VecDeque<Event>,
    
    /// Емкость очередей
    capacity: QueueCapacity,
    
    /// Метрики очереди
    metrics: RwLock<PriorityMetrics>,
}

impl Default for PriorityQueue {
    fn default() -> Self {
        Self::new()
    }
}

impl PriorityQueue {
    /// Создать новую очередь с приоритетами
    ///
    /// # Возвращаемое значение
    ///
    /// Новая PriorityQueue с емкостью по умолчанию
    pub fn new() -> Self {
        Self {
            critical: VecDeque::new(),
            high: VecDeque::new(),
            normal: VecDeque::new(),
            low: VecDeque::new(),
            capacity: QueueCapacity::default(),
            metrics: RwLock::new(PriorityMetrics::new()),
        }
    }
    
    /// Создать очередь с указанной емкостью
    ///
    /// # Аргументы
    ///
    /// * `capacity` - Емкость очередей для каждого приоритета
    ///
    /// # Возвращаемое значение
    ///
    /// Новая PriorityQueue с указанной емкостью
    pub fn with_capacity(capacity: QueueCapacity) -> Self {
        Self {
            critical: VecDeque::with_capacity(capacity.critical),
            high: VecDeque::with_capacity(capacity.high),
            normal: VecDeque::with_capacity(capacity.normal),
            low: VecDeque::with_capacity(capacity.low),
            capacity,
            metrics: RwLock::new(PriorityMetrics::new()),
        }
    }
    
    /// Добавить событие в очередь
    ///
    /// Событие помещается в очередь соответствующего приоритета.
    /// Если очередь переполнена, возвращается ошибка.
    ///
    /// # Аргументы
    ///
    /// * `event` - Событие для добавления
    ///
    /// # Возвращаемое значение
    ///
    /// Ok(()) при успехе, Err(PushResult) при ошибке
    pub fn push(&mut self, event: Event) -> PushResult {
        let priority = event.priority;
        
        // Выбрать очередь по приоритету
        match priority {
            Priority::Critical => {
                if self.critical.len() >= self.capacity.critical {
                    self.metrics.write().dropped_critical += 1;
                    self.metrics.write().dropped_total += 1;
                    return PushResult::CriticalQueueFull;
                }
                self.critical.push_back(event);
            }
            Priority::High => {
                if self.high.len() >= self.capacity.high {
                    self.metrics.write().dropped_high += 1;
                    self.metrics.write().dropped_total += 1;
                    return PushResult::HighQueueFull;
                }
                self.high.push_back(event);
            }
            Priority::Normal => {
                if self.normal.len() >= self.capacity.normal {
                    self.metrics.write().dropped_normal += 1;
                    self.metrics.write().dropped_total += 1;
                    return PushResult::NormalQueueFull;
                }
                self.normal.push_back(event);
            }
            Priority::Low => {
                if self.low.len() >= self.capacity.low {
                    self.metrics.write().dropped_low += 1;
                    self.metrics.write().dropped_total += 1;
                    return PushResult::LowQueueFull;
                }
                self.low.push_back(event);
            }
        }
        
        PushResult::Ok
    }
    
    /// Извлечь событие с наивысшим приоритетом
    ///
    /// Проверяет очереди в порядке приоритета:
    /// Critical -> High -> Normal -> Low
    ///
    /// # Возвращаемое значение
    ///
    /// Some(Event) если есть события, None если очередь пуста
    pub fn pop(&mut self) -> Option<Event> {
        // Проверяем в порядке приоритета
        if let Some(event) = self.critical.pop_front() {
            return Some(event);
        }
        if let Some(event) = self.high.pop_front() {
            return Some(event);
        }
        if let Some(event) = self.normal.pop_front() {
            return Some(event);
        }
        self.low.pop_front()
    }
    
    /// Извлечь событие с приоритетом не ниже указанного
    ///
    /// # Аргументы
    ///
    /// * `min_priority` - Минимальный приоритет (включительно)
    ///
    /// # Возвращаемое значение
    ///
    /// Some(Event) если есть события с указанным или более высоким приоритетом
    pub fn pop_priority(&mut self, min_priority: Priority) -> Option<Event> {
        // Critical: можем извлечь только из Critical
        if min_priority == Priority::Critical {
            return self.critical.pop_front();
        }
        
        // High: можем из High или выше (Critical уже проверен)
        if min_priority <= Priority::High {
            if let Some(event) = self.high.pop_front() {
                return Some(event);
            }
            // Fall through to lower priorities
        }
        
        // Normal: можем из Normal или выше
        if min_priority <= Priority::Normal {
            if let Some(event) = self.normal.pop_front() {
                return Some(event);
            }
            // Fall through to lower priorities
        }
        
        // Low: можем из Low
        if min_priority <= Priority::Low {
            return self.low.pop_front();
        }
        
        None
    }
    
    /// Получить следующее событие без его извлечения
    ///
    /// # Возвращаемое значение
    ///
    /// Some(&Event) если есть события, None если очередь пуста
    pub fn peek(&self) -> Option<&Event> {
        self.critical.front()
            .or_else(|| self.high.front())
            .or_else(|| self.normal.front())
            .or_else(|| self.low.front())
    }
    
    /// Получить общее количество событий во всех очередях
    pub fn len(&self) -> usize {
        self.critical.len() + self.high.len() + self.normal.len() + self.low.len()
    }
    
    /// Проверить пуста ли очередь
    pub fn is_empty(&self) -> bool {
        self.critical.is_empty() && self.high.is_empty() && self.normal.is_empty() && self.low.is_empty()
    }
    
    /// Получить размер конкретной очереди
    ///
    /// # Аргументы
    ///
    /// * `priority` - Приоритет очереди
    ///
    /// # Возвращаемое значение
    ///
    /// usize - количество событий в очереди
    pub fn size(&self, priority: Priority) -> usize {
        match priority {
            Priority::Critical => self.critical.len(),
            Priority::High => self.high.len(),
            Priority::Normal => self.normal.len(),
            Priority::Low => self.low.len(),
        }
    }
    
    /// Получить емкость очередей
    pub fn capacity(&self) -> &QueueCapacity {
        &self.capacity
    }
    
    /// Получить текущие метрики очереди
    pub fn get_metrics(&self) -> PriorityMetrics {
        let mut metrics = self.metrics.read().clone();
        metrics.critical_count = self.critical.len();
        metrics.high_count = self.high.len();
        metrics.normal_count = self.normal.len();
        metrics.low_count = self.low.len();
        metrics
    }
    
    /// Получить заполненность очереди в процентах
    ///
    /// # Аргументы
    ///
    /// * `priority` - Приоритет очереди
    ///
    /// # Возвращаемое значение
    ///
    /// f64 - заполненность от 0.0 до 1.0+
    pub fn fill_ratio(&self, priority: Priority) -> f64 {
        let size = self.size(priority);
        let cap = self.capacity.get(priority);
        if cap == 0 {
            return 0.0;
        }
        size as f64 / cap as f64
    }
    
    /// Попытаться освободить место в очереди Low
    ///
    /// # Аргументы
    ///
    /// * `count` - Количество событий для удаления
    ///
    /// # Возвращаемое значение
    ///
    /// usize - фактически удаленное количество
    pub fn drop_low_events(&mut self, count: usize) -> usize {
        let mut dropped = 0;
        for _ in 0..count {
            if self.low.pop_front().is_some() {
                dropped += 1;
            } else {
                break;
            }
        }
        dropped
    }
    
    /// Попытаться освободить место в очереди Normal
    ///
    /// # Аргументы
    ///
    /// * `count` - Количество событий для удаления
    ///
    /// # Возвращаемое значение
    ///
    /// usize - фактически удаленное количество
    pub fn drop_normal_events(&mut self, count: usize) -> usize {
        let mut dropped = 0;
        for _ in 0..count {
            if self.normal.pop_front().is_some() {
                dropped += 1;
            } else {
                break;
            }
        }
        dropped
    }
    
    /// Очистить все очереди
    pub fn clear(&mut self) {
        self.critical.clear();
        self.high.clear();
        self.normal.clear();
        self.low.clear();
    }
}

/// Thread-safe обертка для PriorityQueue
pub type SyncPriorityQueue = Arc<RwLock<PriorityQueue>>;

/// Создать новую синхронизированную очередь
pub fn new_sync_queue() -> SyncPriorityQueue {
    Arc::new(RwLock::new(PriorityQueue::new()))
}

/// Создать синхронизированную очередь с указанной емкостью
pub fn new_sync_queue_with_capacity(capacity: QueueCapacity) -> SyncPriorityQueue {
    Arc::new(RwLock::new(PriorityQueue::with_capacity(capacity)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::priority::Priority;

    fn create_test_event(event_type: &str, priority: Priority) -> Event {
        Event::new(event_type, "TEST_SOURCE", serde_json::json!({}))
            .with_priority(priority)
    }

    #[test]
    fn test_queue_push_pop() {
        let mut queue = PriorityQueue::new();
        
        let event1 = create_test_event("LOW", Priority::Low);
        let event2 = create_test_event("HIGH", Priority::High);
        
        assert!(queue.push(event1).is_ok());
        assert!(queue.push(event2).is_ok());
        
        // Первым должен быть HIGH
        let first = queue.pop().unwrap();
        assert_eq!(first.event_type, "HIGH");
        
        // Вторым - LOW
        let second = queue.pop().unwrap();
        assert_eq!(second.event_type, "LOW");
    }

    #[test]
    fn test_queue_priority_order() {
        let mut queue = PriorityQueue::new();
        
        // Добавляем в случайном порядке
        queue.push(create_test_event("LOW", Priority::Low)).is_ok();
        queue.push(create_test_event("CRITICAL", Priority::Critical)).is_ok();
        queue.push(create_test_event("HIGH", Priority::High)).is_ok();
        queue.push(create_test_event("NORMAL", Priority::Normal)).is_ok();
        
        // Проверяем порядок извлечения
        assert_eq!(queue.pop().unwrap().event_type, "CRITICAL");
        assert_eq!(queue.pop().unwrap().event_type, "HIGH");
        assert_eq!(queue.pop().unwrap().event_type, "NORMAL");
        assert_eq!(queue.pop().unwrap().event_type, "LOW");
    }

    #[test]
    fn test_queue_capacity() {
        let mut queue = PriorityQueue::new();
        
        // Critical емкость = 100
        for i in 0..100 {
            let event = Event::new(format!("EVENT_{}", i), "SOURCE", serde_json::json!({}))
                .with_priority(Priority::Critical);
            assert!(queue.push(event).is_ok(), "Failed at iteration {}", i);
        }
        
        // 101-е должно вернуть ошибку
        let overflow = Event::new("OVERFLOW", "SOURCE", serde_json::json!({}))
            .with_priority(Priority::Critical);
        assert_eq!(queue.push(overflow), PushResult::CriticalQueueFull);
    }

    #[test]
    fn test_queue_len() {
        let mut queue = PriorityQueue::new();
        
        assert!(queue.is_empty());
        assert_eq!(queue.len(), 0);
        
        queue.push(create_test_event("1", Priority::Low)).is_ok();
        queue.push(create_test_event("2", Priority::High)).is_ok();
        
        assert!(!queue.is_empty());
        assert_eq!(queue.len(), 2);
    }

    #[test]
    fn test_queue_size_by_priority() {
        let mut queue = PriorityQueue::new();
        
        queue.push(create_test_event("1", Priority::Critical)).is_ok();
        queue.push(create_test_event("2", Priority::Critical)).is_ok();
        queue.push(create_test_event("3", Priority::High)).is_ok();
        
        assert_eq!(queue.size(Priority::Critical), 2);
        assert_eq!(queue.size(Priority::High), 1);
        assert_eq!(queue.size(Priority::Normal), 0);
        assert_eq!(queue.size(Priority::Low), 0);
    }

    #[test]
    fn test_queue_metrics() {
        let mut queue = PriorityQueue::new();
        
        queue.push(create_test_event("1", Priority::Low)).is_ok();
        queue.push(create_test_event("2", Priority::High)).is_ok();
        
        let metrics = queue.get_metrics();
        assert_eq!(metrics.low_count, 1);
        assert_eq!(metrics.high_count, 1);
    }

    #[test]
    fn test_queue_drop_events() {
        let mut queue = PriorityQueue::new();
        
        // Добавляем 10 low событий
        for i in 0..10 {
            queue.push(create_test_event(&format!("LOW_{}", i), Priority::Low)).is_ok();
        }
        
        // Удаляем 5
        let dropped = queue.drop_low_events(5);
        assert_eq!(dropped, 5);
        assert_eq!(queue.size(Priority::Low), 5);
    }

    #[test]
    fn test_queue_fill_ratio() {
        let mut queue = PriorityQueue::new();
        
        // Critical емкость = 100
        for _ in 0..50 {
            queue.push(create_test_event("C", Priority::Critical)).is_ok();
        }
        
        let ratio = queue.fill_ratio(Priority::Critical);
        assert!((ratio - 0.5).abs() < 0.001);
    }

    #[test]
    fn test_queue_peek() {
        let mut queue = PriorityQueue::new();
        
        assert!(queue.peek().is_none());
        
        queue.push(create_test_event("FIRST", Priority::High)).is_ok();
        
        let peeked = queue.peek().unwrap();
        assert_eq!(peeked.event_type, "FIRST");
        
        // peek не удаляет
        assert_eq!(queue.len(), 1);
    }

    #[test]
    fn test_queue_pop_priority() {
        let mut queue = PriorityQueue::new();
        
        queue.push(create_test_event("LOW", Priority::Low)).is_ok();
        queue.push(create_test_event("HIGH", Priority::High)).is_ok();
        
        // Запрашиваем только Critical - должны получить None
        let result = queue.pop_priority(Priority::Critical);
        assert!(result.is_none());
        
        // Запрашиваем High - должны получить HIGH
        let result = queue.pop_priority(Priority::High);
        assert_eq!(result.unwrap().event_type, "HIGH");
    }

    #[test]
    fn test_queue_clear() {
        let mut queue = PriorityQueue::new();
        
        queue.push(create_test_event("1", Priority::Low)).is_ok();
        queue.push(create_test_event("2", Priority::High)).is_ok();
        
        queue.clear();
        
        assert!(queue.is_empty());
    }

    #[test]
    fn test_queue_with_custom_capacity() {
        let capacity = QueueCapacity::new(10, 20, 30, 40);
        let queue = PriorityQueue::with_capacity(capacity);
        
        assert_eq!(queue.capacity().critical, 10);
        assert_eq!(queue.capacity().high, 20);
        assert_eq!(queue.capacity().normal, 30);
        assert_eq!(queue.capacity().low, 40);
    }

    #[test]
    fn test_sync_queue() {
        let queue = new_sync_queue();
        
        {
            let mut locked = queue.write();
            locked.push(create_test_event("TEST", Priority::Normal)).is_ok();
        }
        
        {
            let locked = queue.read();
            assert_eq!(locked.len(), 1);
        }
    }
}
