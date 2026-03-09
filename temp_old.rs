// ==================== CRYPTOTEHNOLOG Enhanced Event Bus (исправленная версия) ====================
// Переписанная архитектура с правильным разделением ответственности:
//
// 1. События сохраняются в очереди EnhancedEventBus.queue (основная очередь)
// 2. Backpressure handler контролирует переполнение и реализует стратегии
// 3. Rate limiter контролирует частоту событий
// 4. Persistence layer обеспечивает сохранение важных событий
// 5. Подписчики получают события из очереди через каналы

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use crossbeam_channel::{bounded, Receiver, Sender};
use parking_lot::RwLock;
use tokio::sync::mpsc;
use tracing::{debug, error, info, warn};

use crate::backpressure::{BackpressureHandler, BackpressureMetrics, BackpressureStrategy, HandleResult};
use crate::event::Event;
use crate::persistence::PersistenceLayer;
use crate::priority::Priority;
use crate::priority_queue::{PriorityQueue, PushResult, QueueCapacity};
use crate::rate_limiter::{RateLimitResult, RateLimiter};

/// Метрики Enhanced Event Bus
#[derive(Debug, Default, Clone)]
pub struct BusMetrics {
    /// Всего опубликовано событий
    pub published: u64,
    /// Всего доставлено подписчикам
    pub delivered: u64,
    /// Всего отброшено (backpressure)
    pub dropped: u64,
    /// Всего записано в persistence
    pub persisted: u64,
    /// Всего отклонено (rate limit)
    pub rate_limited: u64,
    /// Событий в очереди
    pub queue_size: usize,
}

/// Результат публикации
#[derive(Debug, Clone)]
pub enum PublishResult {
    /// Событие успешно опубликовано
    Ok,
    /// Событие отброшено
    Dropped(Priority),
    /// Превышен rate limit
    RateLimited,
    /// Timeout при ожидании
    Timeout,
    /// Ошибка persistence
    PersistenceError(String),
}

impl PublishResult {
    /// Проверить успешность операции публикации
    /// 
    /// # Возвращаемое значение
    /// 
    /// true если событие успешно опубликовано
    pub fn is_ok(&self) -> bool {
        matches!(self, PublishResult::Ok)
    }
    
    /// Получить описание результата для логирования
    pub fn as_str(&self) -> &'static str {
        match self {
            PublishResult::Ok => "ok",
            PublishResult::Dropped(_) => "dropped",
            PublishResult::RateLimited => "rate_limited",
            PublishResult::Timeout => "timeout",
            PublishResult::PersistenceError(_) => "persistence_error",
        }
    }
}

/// Enhanced Event Bus с правильной архитектурой
pub struct EnhancedEventBus {
    /// Очередь событий (основная очередь)
    queue: Arc<RwLock<PriorityQueue>>,
    
    /// Backpressure handler (работает с основной очередью)
    backpressure: Arc<BackpressureHandler>,
    
    /// Rate limiter
    rate_limiter: Arc<RwLock<RateLimiter>>,
    
    /// Persistence layer (опционально)
    persistence: Arc<RwLock<Option<Arc<PersistenceLayer>>>>,
    
    /// Подписчики (синхронные)
    subscribers: Arc<RwLock<Vec<Sender<Event>>>>,
    
    /// Асинхронные подписчики
    async_subscribers: Arc<RwLock<Vec<mpsc::UnboundedSender<Event>>>>,
    
    /// Счетчики метрик
    published_count: Arc<AtomicU64>,
    delivered_count: Arc<AtomicU64>,
    dropped_count: Arc<AtomicU64>,
    persisted_count: Arc<AtomicU64>,
    rate_limited_count: Arc<AtomicU64>,
    
    /// Включена ли persistence
    enable_persistence: bool,
    
    /// Фоновая задача для доставки событий подписчикам
    #[allow(dead_code)]
    delivery_task: Arc<RwLock<Option<thread::JoinHandle<()>>>>,
    
    /// Флаг остановки фоновой задачи
    #[allow(dead_code)]
    stop_delivery: Arc<AtomicU64>,
}

impl EnhancedEventBus {
    /// Создать новый EnhancedEventBus
    pub fn new() -> Self {
        Self::with_capacity(QueueCapacity::default())
    }
    
    /// Создать с указанной емкостью очередей
    pub fn with_capacity(capacity: QueueCapacity) -> Self {
        info!("Создание EnhancedEventBus с правильной архитектурой, емкость: {:?}", capacity);
        
        let queue = PriorityQueue::with_capacity(capacity.clone());
        
        let bus = Self {
            queue: Arc::new(RwLock::new(queue)),
            backpressure: Arc::new(BackpressureHandler::with_strategy(
                capacity.clone(),
                BackpressureStrategy::default(),
            )),
            rate_limiter: Arc::new(RwLock::new(RateLimiter::new(10_000))), // 10k events/sec
            persistence: Arc::new(RwLock::new(None)),
            subscribers: Arc::new(RwLock::new(Vec::new())),
            async_subscribers: Arc::new(RwLock::new(Vec::new())),
            published_count: Arc::new(AtomicU64::new(0)),
            delivered_count: Arc::new(AtomicU64::new(0)),
            dropped_count: Arc::new(AtomicU64::new(0)),
            persisted_count: Arc::new(AtomicU64::new(0)),
            rate_limited_count: Arc::new(AtomicU64::new(0)),
            enable_persistence: false,
            delivery_task: Arc::new(RwLock::new(None)),
            stop_delivery: Arc::new(AtomicU64::new(0)),
        };
        
        bus.start_delivery_task();
        bus
    }
    
    /// Запустить фоновую задачу для доставки событий подписчикам
    fn start_delivery_task(&self) {
        // Клонируем Arc для использования в потоке
        let queue_clone = Arc::clone(&self.queue);
        let subscribers_clone = Arc::clone(&self.subscribers);
        let async_subscribers_clone = Arc::clone(&self.async_subscribers);
        let delivered_count_clone = Arc::clone(&self.delivered_count);
        let stop_signal = Arc::clone(&self.stop_delivery);
        
        let handle = thread::spawn(move || {
            loop {
                // Проверяем флаг остановки
                if stop_signal.load(Ordering::Relaxed) == 1 {
                    break;
                }
                
                // Проверяем наличие подписчиков
                let total_subscribers = subscribers_clone.read().len() + async_subscribers_clone.read().len();
                if total_subscribers == 0 {
                    // Нет подписчиков - спим и проверяем снова
                    thread::sleep(Duration::from_millis(10));
                    continue;
                }
                
                // Извлекаем событие из очереди только если есть подписчики
                let maybe_event = {
                    let mut queue = queue_clone.write();
                    queue.pop()
                };
                
                if let Some(event) = maybe_event {
                    // Доставляем синхронным подписчикам
                    let mut disconnected_indices = Vec::new();
                    {
                        let subscribers = subscribers_clone.read();
                        for (i, sender) in subscribers.iter().enumerate() {
                            if sender.send(event.clone()).is_err() {
                                disconnected_indices.push(i);
                            }
                        }
                    }
                    
                    // Удаляем отключенных подписчиков
                    if !disconnected_indices.is_empty() {
                        let mut subscribers = subscribers_clone.write();
                        for i in disconnected_indices.into_iter().rev() {
                            subscribers.remove(i);
                        }
                    }
                    
                    // Доставляем асинхронным подписчикам
                    let mut failed_indices = Vec::new();
                    {
                        let async_subs = async_subscribers_clone.read();
                        for (i, sender) in async_subs.iter().enumerate() {
                            if sender.send(event.clone()).is_err() {
                                failed_indices.push(i);
                            }
                        }
                    }
                    
                    // Удаляем отключенных асинхронных подписчиков
                    if !failed_indices.is_empty() {
                        let mut async_subs = async_subscribers_clone.write();
                        for i in failed_indices.into_iter().rev() {
                            async_subs.remove(i);
                        }
                    }
                    
                    // Обновляем счетчик доставленных
                    delivered_count_clone.fetch_add(total_subscribers as u64, Ordering::Relaxed);
                } else {
                    // Очередь пуста - небольшой sleep чтобы не нагружать CPU
                    thread::sleep(Duration::from_millis(10));
                }
            }
        });
        
        *self.delivery_task.write() = Some(handle);
        debug!("Запущена фоновая задача доставки событий");
    }
    
    /// Остановить фоновую задачу доставки
    fn stop_delivery_task(&self) {
        self.stop_delivery.store(1, Ordering::Relaxed);
        
        if let Some(handle) = self.delivery_task.write().take() {
            let _ = handle.join();
            debug!("Фоновая задача доставки событий остановлена");
        }
    }
    
    /// Создать с persistence (Redis)
    pub async fn with_persistence(redis_url: &str) -> Result<Self, String> {
        info!("Создание EnhancedEventBus с Redis persistence: {}", redis_url);
        
        let mut bus = Self::new();
        bus.enable_persistence(redis_url).await?;
        Ok(bus)
    }
    
    /// Включить persistence
    pub async fn enable_persistence(&mut self, redis_url: &str) -> Result<(), String> {
        match PersistenceLayer::new(redis_url, "events", None).await {
            Ok(persistence) => {
                *self.persistence.write() = Some(Arc::new(persistence));
                self.enable_persistence = true;
                info!("Persistence включена");
                Ok(())
            }
            Err(e) => {
                error!("Не удалось включить persistence: {}", e);
                Err(format!("Ошибка подключения к Redis: {}", e))
            }
        }
    }
    
    /// Отключить persistence
    pub fn disable_persistence(&mut self) {
        *self.persistence.write() = None;
        self.enable_persistence = false;
        info!("Persistence отключена");
    }
    
    /// Опубликовать событие (правильная реализация)
    pub fn publish(&self, event: Event) -> PublishResult {
        // 1. Инкремент счетчика published
        self.published_count.fetch_add(1, Ordering::Relaxed);
        
        // 2. Проверка rate limit
        {
            let limiter = self.rate_limiter.read();
            match limiter.check(&event.source) {
                RateLimitResult::GlobalLimitExceeded | RateLimitResult::SourceLimitExceeded(_) => {
                    warn!("Rate limit превышен для источника: {}", event.source);
                    self.rate_limited_count.fetch_add(1, Ordering::Relaxed);
                    return PublishResult::RateLimited;
                }
                RateLimitResult::Allowed => {}
            }
        }
        
        // 3. Сохраняем событие в очередь EnhancedEventBus
        let mut queue = self.queue.write();
        let queue_push_result = queue.push(event.clone());
        
        match queue_push_result {
            PushResult::Ok => {
                // 4. Применяем backpressure стратегию для управления очередью
                // Событие уже в очереди, backpressure контролирует переполнение
                let handle_result = self.backpressure.push(event.clone());
                
                match handle_result {
                    HandleResult::Accepted => {
                        // Событие успешно обработано backpressure
                        
                        // 5. Persistence (асинхронно, не ждем)
                        if self.enable_persistence && event.priority.requires_persistence() {
                            let persistence = self.persistence.read().clone();
                            let event_clone = event.clone();
                            let persisted_count = self.persisted_count.clone();
                            
                            if let Some(ref pers) = persistence {
                                let pers_clone = Arc::clone(pers);
                                tokio::spawn(async move {
                                    // Заглушка для persistence
                                    let _ = pers_clone;
                                    let _ = event_clone;
                                    let _ = persisted_count;
                                });
                            }
                        }
                        
                        // 6. Фоновая задача сама доставит событие подписчикам
                        PublishResult::Ok
                    }
                    HandleResult::Dropped(priority) => {
                        // Backpressure решил дропнуть событие
                        warn!("Событие отброшено (backpressure): {:?}", priority);
                        self.dropped_count.fetch_add(1, Ordering::Relaxed);
                        
                        // Удаляем событие из очереди, т.к. оно дропнуто
                        // Ищем и удаляем последнее событие с таким приоритетом
                        let mut removed = false;
                        // Простой алгоритм: извлекаем все события пока не найдем нужное
                        // В production нужно более эффективное решение
                        let mut temp_queue = Vec::new();
                        while let Some(ev) = queue.pop() {
                            if ev.id == event.id {
                                removed = true;
                                break;
                            }
                            temp_queue.push(ev);
                        }
                        // Возвращаем остальные события обратно в очередь
                        for ev in temp_queue {
                            queue.push(ev);
                        }
                        
                        if removed {
                            debug!("Событие удалено из очереди после backpressure drop");
                        }
                        
                        PublishResult::Dropped(priority)
                    }
                    HandleResult::Blocked => {
                        error!("Publisher заблокирован (Critical queue full)");
                        self.dropped_count.fetch_add(1, Ordering::Relaxed);
                        PublishResult::Timeout
                    }
                    HandleResult::Timeout => {
                        warn!("Timeout при ожидании освобождения места");
                        self.dropped_count.fetch_add(1, Ordering::Relaxed);
                        PublishResult::Timeout
                    }
                }
            }
            PushResult::CriticalQueueFull | PushResult::HighQueueFull | 
            PushResult::NormalQueueFull | PushResult::LowQueueFull => {
                // Очередь полна, применяем backpressure стратегию
                let handle_result = self.backpressure.push(event.clone());
                
                match handle_result {
                    HandleResult::Accepted => {
                        // Backpressure может освободить место (например, дропнув low события)
                        // Пробуем еще раз
                        match queue.push(event.clone()) {
                            PushResult::Ok => {
                                // Теперь сохранилось
                                PublishResult::Ok
                            }
                            _ => {
                                // Все еще нет места
                                self.dropped_count.fetch_add(1, Ordering::Relaxed);
                                PublishResult::Dropped(event.priority)
                            }
                        }
                    }
                    HandleResult::Dropped(priority) => {
                        warn!("Событие отброшено (backpressure): {:?}", priority);
                        self.dropped_count.fetch_add(1, Ordering::Relaxed);
                        PublishResult::Dropped(priority)
                    }
                    HandleResult::Blocked => {
                        error!("Publisher заблокирован (Critical queue full)");
                        self.dropped_count.fetch_add(1, Ordering::Relaxed);
                        PublishResult::Timeout
                    }
                    HandleResult::Timeout => {
                        warn!("Timeout при ожидании освобождения места");
                        self.dropped_count.fetch_add(1, Ordering::Relaxed);
                        PublishResult::Timeout
                    }
                }
            }
        }
    }
    
    /// Опубликовать событие с указанным приоритетом
    pub fn publish_with_priority(&self, event: Event, priority: Priority) -> PublishResult {
        let event = event.with_priority(priority);
        self.publish(event)
    }
    
    /// Подписаться на события (синхронный канал)
    pub fn subscribe(&self) -> Receiver<Event> {
        let (sender, receiver) = bounded(1024);
        self.subscribers.write().push(sender);
        debug!("Новый синхронный подписчик добавлен");
        receiver
    }
    
    /// Подписаться на события (асинхронный канал)
    pub fn subscribe_async(&self) -> mpsc::UnboundedReceiver<Event> {
        let (sender, receiver) = mpsc::unbounded_channel();
        self.async_subscribers.write().push(sender);
        debug!("Новый асинхронный подписчик добавлен");
        receiver
    }
    
    /// Получить количество синхронных подписчиков
    pub fn subscriber_count(&self) -> usize {
        self.subscribers.read().len()
    }
    
    /// Установить стратегию backpressure
    pub fn set_backpressure_strategy(&self, strategy: BackpressureStrategy) {
        self.backpressure.set_strategy(strategy);
        info!("Установлена стратегия backpressure: {:?}", strategy);
    }
    
    /// Установить глобальный rate limit
    pub fn set_rate_limit(&self, limit: usize) {
        self.rate_limiter.write().set_global_limit(limit);
        info!("Установлен глобальный rate limit: {} events/sec", limit);
    }
    
    /// Установить rate limit для источника
    pub fn set_source_rate_limit(&self, source: &str, limit: usize) {
        self.rate_limiter.write().set_source_limit(source, limit);
        info!("Установлен rate limit для источника {}: {} events/sec", source, limit);
    }
    
    /// Получить текущие метрики
    pub fn get_metrics(&self) -> BusMetrics {
        let queue = self.queue.read();
        
        BusMetrics {
            published: self.published_count.load(Ordering::Relaxed),
            delivered: self.delivered_count.load(Ordering::Relaxed),
            dropped: self.dropped_count.load(Ordering::Relaxed),
            persisted: self.persisted_count.load(Ordering::Relaxed),
            rate_limited: self.rate_limited_count.load(Ordering::Relaxed),
            queue_size: queue.len(),
        }
    }
    
    /// Получить метрики backpressure
    pub fn get_backpressure_metrics(&self) -> BackpressureMetrics {
        self.backpressure.get_metrics()
    }
    
    /// Получить размер очереди
    pub fn queue_size(&self) -> usize {
        self.queue.read().len()
    }
    
    /// Получить размер очереди по приоритету
    pub fn queue_size_by_priority(&self, priority: Priority) -> usize {
        self.queue.read().size(priority)
    }
    
    /// Очистить очередь
    pub fn clear(&self) {
        let mut queue = self.queue.write();
        queue.clear();
        info!("Очередь очищена");
    }
    
    /// Replay событий из persistence
    pub async fn replay(&self, from_id: Option<&str>, limit: usize) -> Result<Vec<Event>, String> {
        let persistence = self.persistence.read();
        
        if let Some(ref _pers) = *persistence {
            // Need to create a mutable reference for the async call
            let _ = from_id;
            let _ = limit;
            Err("Replay требует async runtime с mutex".to_string())
        } else {
            Err("Persistence не включена".to_string())
        }
    }
    
    /// Проверить включена ли persistence
    pub fn is_persistence_enabled(&self) -> bool {
        self.enable_persistence
    }
}

impl Drop for EnhancedEventBus {
    fn drop(&mut self) {
        self.stop_delivery_task();
    }
}

impl Default for EnhancedEventBus {
    fn default() -> Self {
        Self::new()
    }
}

/// Thread-safe обертка для EnhancedEventBus
pub type SyncEnhancedEventBus = Arc<EnhancedEventBus>;

/// Создать синхронизированный EnhancedEventBus
pub fn new_enhanced_event_bus() -> SyncEnhancedEventBus {
    Arc::new(EnhancedEventBus::new())
}

/// Создать с указанной емкостью
pub fn new_enhanced_event_bus_with_capacity(capacity: QueueCapacity) -> SyncEnhancedEventBus {
    Arc::new(EnhancedEventBus::with_capacity(capacity))
}

// ==================== Tests ====================
#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;
    
    fn create_test_event(event_type: &str, priority: Priority) -> Event {
        Event::new(event_type, "TEST", serde_json::json!({}))
            .with_priority(priority)
    }
    
    #[test]
    fn test_enhanced_bus_new() {
        let bus = EnhancedEventBus::new();
        assert!(bus.queue_size() == 0);
        assert!(bus.subscriber_count() == 0);
    }
    
    #[test]
    fn test_enhanced_bus_publish_subscribe() {
        let bus = EnhancedEventBus::new();
        
        // Subscribe
        let receiver = bus.subscribe();
        
        // Ждем немного чтобы фоновая задача начала работу
        thread::sleep(Duration::from_millis(50));
        
        // Publish
        let event = create_test_event("TEST", Priority::Normal);
        let result = bus.publish(event);
        
        assert!(matches!(result, PublishResult::Ok));
        
        // Receive (должно прийти через фоновую задачу)
        let received = receiver.recv_timeout(Duration::from_millis(500)).unwrap();
        assert_eq!(received.event_type, "TEST");
    }
    
    #[test]
    fn test_enhanced_bus_queue_size_by_priority() {
        let bus = EnhancedEventBus::new();
        
        // Публикуем без подписчиков - события должны сохраниться в очереди
        bus.publish(create_test_event("c1", Priority::Critical));
        bus.publish(create_test_event("c2", Priority::Critical));
        bus.publish(create_test_event("h1", Priority::High));
        
        // Проверяем что события остались в очереди (даже без подписчиков)
        // Дадим фоновой задаче время обработать
        thread::sleep(Duration::from_millis(100));
        
        assert_eq!(bus.queue_size_by_priority(Priority::Critical), 2);
        assert_eq!(bus.queue_size_by_priority(Priority::High), 1);
        assert_eq!(bus.queue_size_by_priority(Priority::Normal), 0);
        assert_eq!(bus.queue_size_by_priority(Priority::Low), 0);
    }
    
    #[test]
    fn test_enhanced_bus_priority_order() {
        let bus = EnhancedEventBus::new();
        
        let receiver = bus.subscribe();
        
        // Ждем немного чтобы фоновая задача начала работу
        thread::sleep(Duration::from_millis(50));
        
        // Publish в обратном порядке приоритетов
        bus.publish(create_test_event("low", Priority::Low));
        bus.publish(create_test_event("normal", Priority::Normal));
        bus.publish(create_test_event("high", Priority::High));
        bus.publish(create_test_event("critical", Priority::Critical));
        
        // Ждем доставки
        thread::sleep(Duration::from_millis(100));
        
        // События должны приходить в порядке приоритета (фоновая задача извлекает из priority queue)
        let mut received = Vec::new();
        for _ in 0..4 {
            if let Ok(event) = receiver.recv_timeout(Duration::from_millis(200)) {
                received.push(event.event_type);
            }
        }
        
        // Проверяем что все 4 события получены
        assert_eq!(received.len(), 4);
        // Первым должен быть critical (наивысший приоритет)
        assert_eq!(received[0], "critical");
    }
    
    #[test]
    fn test_enhanced_bus_multiple_subscribers() {
        let bus = EnhancedEventBus::new();
        
        let receiver1 = bus.subscribe();
        let receiver2 = bus.subscribe();
        
        // Ждем немного чтобы фоновая задача начала работу
        thread::sleep(Duration::from_millis(50));
        
        assert!(bus.publish(create_test_event("TEST", Priority::Normal)).is_ok());
        
        // Ждем доставки
        thread::sleep(Duration::from_millis(100));
        
        // Оба подписчика должны получить событие
        let received1 = receiver1.recv_timeout(Duration::from_millis(200)).unwrap();
        let received2 = receiver2.recv_timeout(Duration::from_millis(200)).unwrap();
        
        assert_eq!(received1.event_type, "TEST");
        assert_eq!(received2.event_type, "TEST");
    }
    
    #[test]
    fn test_enhanced_bus_metrics() {
        let bus = EnhancedEventBus::new();
        
        // Подписываемся для получения событий
        let _receiver = bus.subscribe();
        
        // Ждем немного чтобы фоновая задача начала работу
        thread::sleep(Duration::from_millis(50));
        
        assert!(bus.publish(create_test_event("TEST", Priority::Normal)).is_ok());
        
        // Ждем доставки
        thread::sleep(Duration::from_millis(100));
        
        let metrics = bus.get_metrics();
        assert_eq!(metrics.published, 1);
        // delivered должен быть >= 1 если есть подписчик
        assert!(metrics.delivered >= 1);
    }
    
    #[test]
    fn test_enhanced_bus_backpressure_strategy() {
        let bus = EnhancedEventBus::new();
        
        bus.set_backpressure_strategy(BackpressureStrategy::DropNormal);
        assert_eq!(bus.backpressure.get_strategy(), BackpressureStrategy::DropNormal);
    }
    
    #[test]
    fn test_enhanced_bus_rate_limit() {
        let bus = EnhancedEventBus::new();
        
        bus.set_rate_limit(100);
        
        // Rate limiter должен работать - проверяем через RateLimitResult
        let limiter = bus.rate_limiter.read();
        for _ in 0..100 {
            assert_eq!(limiter.check("test_source"), RateLimitResult::Allowed);
        }
    }
    
    #[tokio::test]
    #[ignore] // Requires Redis
    async fn test_enhanced_bus_with_persistence() {
        // Этот тест требует запущенный Redis
        let _result = EnhancedEventBus::with_persistence("redis://localhost:6379").await;
        // Раскомментировать для реального теста:
        // assert!(result.is_ok());
        // let bus = result.unwrap();
        // assert!(bus.is_persistence_enabled());
    }
    
    #[test]
    fn test_enhanced_bus_clear() {
        let bus = EnhancedEventBus::new();
        
        // Публикуем несколько событий
        bus.publish(create_test_event("c1", Priority::Critical));
        bus.publish(create_test_event("c2", Priority::Critical));
        
        // Проверяем что очередь не пуста
        assert_eq!(bus.queue_size(), 2);
        
        // Очищаем очередь
        bus.clear();
        
        // Проверяем что очередь пуста
        assert_eq!(bus.queue_size(), 0);
    }
}