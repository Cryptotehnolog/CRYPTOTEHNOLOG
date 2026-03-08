// ==================== CRYPTOTEHNOLOG Priority Tests ====================
// Unit тесты для системы приоритетов Event Bus

use cryptotechnolog_eventbus::priority::Priority;
use cryptotechnolog_eventbus::PriorityQueue;
use cryptotechnolog_eventbus::PushResult;
use cryptotechnolog_eventbus::Event;
use cryptotechnolog_eventbus::BackpressureHandler;
use cryptotechnolog_eventbus::BackpressureStrategy;
use cryptotechnolog_eventbus::HandleResult;
use cryptotechnolog_eventbus::QueueCapacity;

mod priority_tests {
    use super::*;

    #[test]
    fn test_priority_ordering_critical_is_highest() {
        // Critical должен быть меньше (выше) чем все остальные
        assert!(Priority::Critical < Priority::High);
        assert!(Priority::Critical < Priority::Normal);
        assert!(Priority::Critical < Priority::Low);
    }

    #[test]
    fn test_priority_ordering_high() {
        assert!(Priority::High < Priority::Normal);
        assert!(Priority::High < Priority::Low);
    }

    #[test]
    fn test_priority_ordering_normal() {
        assert!(Priority::Normal < Priority::Low);
    }

    #[test]
    fn test_priority_default() {
        assert_eq!(Priority::default(), Priority::Normal);
    }

    #[test]
    fn test_priority_queue_capacity() {
        assert_eq!(Priority::Critical.queue_capacity(), 100);
        assert_eq!(Priority::High.queue_capacity(), 500);
        assert_eq!(Priority::Normal.queue_capacity(), 10_000);
        assert_eq!(Priority::Low.queue_capacity(), 50_000);
    }

    #[test]
    fn test_priority_requires_persistence() {
        assert!(Priority::Critical.requires_persistence());
        assert!(Priority::High.requires_persistence());
        assert!(!Priority::Normal.requires_persistence());
        assert!(!Priority::Low.requires_persistence());
    }

    #[test]
    fn test_priority_is_droppable() {
        assert!(!Priority::Critical.is_droppable());
        assert!(!Priority::High.is_droppable());
        assert!(Priority::Normal.is_droppable());
        assert!(Priority::Low.is_droppable());
    }

    #[test]
    fn test_priority_as_u8() {
        assert_eq!(Priority::Critical.as_u8(), 0);
        assert_eq!(Priority::High.as_u8(), 1);
        assert_eq!(Priority::Normal.as_u8(), 2);
        assert_eq!(Priority::Low.as_u8(), 3);
    }

    #[test]
    fn test_priority_from_u8() {
        assert_eq!(Priority::from_u8(0), Some(Priority::Critical));
        assert_eq!(Priority::from_u8(1), Some(Priority::High));
        assert_eq!(Priority::from_u8(2), Some(Priority::Normal));
        assert_eq!(Priority::from_u8(3), Some(Priority::Low));
        assert_eq!(Priority::from_u8(4), None);
        assert_eq!(Priority::from_u8(255), None);
    }

    #[test]
    fn test_priority_as_str() {
        assert_eq!(Priority::Critical.as_str(), "critical");
        assert_eq!(Priority::High.as_str(), "high");
        assert_eq!(Priority::Normal.as_str(), "normal");
        assert_eq!(Priority::Low.as_str(), "low");
    }

    #[test]
    fn test_priority_from_str() {
        assert_eq!(Priority::parse("critical"), Some(Priority::Critical));
        assert_eq!(Priority::parse("CRITICAL"), Some(Priority::Critical));
        assert_eq!(Priority::parse("high"), Some(Priority::High));
        assert_eq!(Priority::parse("normal"), Some(Priority::Normal));
        assert_eq!(Priority::parse("low"), Some(Priority::Low));
        assert_eq!(Priority::parse("0"), Some(Priority::Critical));
        assert_eq!(Priority::parse("1"), Some(Priority::High));
        assert_eq!(Priority::parse("invalid"), None);
    }

    #[test]
    fn test_priority_display() {
        assert_eq!(format!("{}", Priority::Critical), "critical");
        assert_eq!(format!("{}", Priority::High), "high");
        assert_eq!(format!("{}", Priority::Normal), "normal");
        assert_eq!(format!("{}", Priority::Low), "low");
    }

    #[test]
    fn test_priority_serialization() {
        // Test JSON serialization/deserialization
        let priorities = vec![
            Priority::Critical,
            Priority::High,
            Priority::Normal,
            Priority::Low,
        ];
        
        for priority in priorities {
            let serialized = serde_json::to_string(&priority).unwrap();
            let deserialized: Priority = serde_json::from_str(&serialized).unwrap();
            assert_eq!(deserialized, priority);
        }
    }
}

mod priority_queue_tests {
    use super::*;

    fn create_test_event(event_type: &str, priority: Priority) -> Event {
        Event::new(event_type, "TEST_SOURCE", serde_json::json!({}))
            .with_priority(priority)
    }

    #[test]
    fn test_queue_push_pop_basic() {
        let mut queue = PriorityQueue::new();
        
        assert!(queue.push(create_test_event("1", Priority::Low)).is_ok());
        assert!(queue.push(create_test_event("2", Priority::High)).is_ok());
        
        // Первым должен быть High
        let first = queue.pop().unwrap();
        assert_eq!(first.priority, Priority::High);
        
        let second = queue.pop().unwrap();
        assert_eq!(second.priority, Priority::Low);
    }

    #[test]
    fn test_queue_priority_order() {
        let mut queue = PriorityQueue::new();
        
        // Добавляем в обратном порядке
        assert!(queue.push(create_test_event("low", Priority::Low)).is_ok());
        assert!(queue.push(create_test_event("normal", Priority::Normal)).is_ok());
        assert!(queue.push(create_test_event("high", Priority::High)).is_ok());
        assert!(queue.push(create_test_event("critical", Priority::Critical)).is_ok());
        
        // Извлекаем в правильном порядке
        assert_eq!(queue.pop().unwrap().priority, Priority::Critical);
        assert_eq!(queue.pop().unwrap().priority, Priority::High);
        assert_eq!(queue.pop().unwrap().priority, Priority::Normal);
        assert_eq!(queue.pop().unwrap().priority, Priority::Low);
    }

    #[test]
    fn test_queue_capacity_enforcement() {
        let mut queue = PriorityQueue::new();
        
        // Critical емкость = 100
        for i in 0..100 {
            let result = queue.push(create_test_event(&format!("{}", i), Priority::Critical));
            assert!(result.is_ok(), "Failed at iteration {}", i);
        }
        
        // 101-е должно вернуть ошибку
        let result = queue.push(create_test_event("overflow", Priority::Critical));
        assert_eq!(result, PushResult::CriticalQueueFull);
    }

    #[test]
    fn test_queue_all_priorities_capacity() {
        // Test High
        let mut queue_high = PriorityQueue::new();
        for _ in 0..500 {
            queue_high.push(create_test_event("h", Priority::High)).is_ok();
        }
        assert_eq!(queue_high.push(create_test_event("h", Priority::High)), PushResult::HighQueueFull);
        
        // Test Normal
        let mut queue_normal = PriorityQueue::new();
        for _ in 0..10_000 {
            queue_normal.push(create_test_event("n", Priority::Normal)).is_ok();
        }
        assert_eq!(queue_normal.push(create_test_event("n", Priority::Normal)), PushResult::NormalQueueFull);
        
        // Test Low
        let mut queue_low = PriorityQueue::new();
        for _ in 0..50_000 {
            queue_low.push(create_test_event("l", Priority::Low)).is_ok();
        }
        assert_eq!(queue_low.push(create_test_event("l", Priority::Low)), PushResult::LowQueueFull);
    }

    #[test]
    fn test_queue_len_and_is_empty() {
        let mut queue = PriorityQueue::new();
        
        assert!(queue.is_empty());
        assert_eq!(queue.len(), 0);
        
        queue.push(create_test_event("1", Priority::Normal)).is_ok();
        
        assert!(!queue.is_empty());
        assert_eq!(queue.len(), 1);
        
        queue.pop();
        
        assert!(queue.is_empty());
        assert_eq!(queue.len(), 0);
    }

    #[test]
    fn test_queue_size_by_priority() {
        let mut queue = PriorityQueue::new();
        
        queue.push(create_test_event("c1", Priority::Critical)).is_ok();
        queue.push(create_test_event("c2", Priority::Critical)).is_ok();
        queue.push(create_test_event("h1", Priority::High)).is_ok();
        
        assert_eq!(queue.size(Priority::Critical), 2);
        assert_eq!(queue.size(Priority::High), 1);
        assert_eq!(queue.size(Priority::Normal), 0);
        assert_eq!(queue.size(Priority::Low), 0);
    }

    #[test]
    fn test_queue_peek() {
        let mut queue = PriorityQueue::new();
        
        assert!(queue.peek().is_none());
        
        queue.push(create_test_event("first", Priority::High)).is_ok();
        queue.push(create_test_event("second", Priority::Low)).is_ok();
        
        let peeked = queue.peek().unwrap();
        assert_eq!(peeked.event_type, "first");
        
        // peek не удаляет
        assert_eq!(queue.len(), 2);
    }

    #[test]
    fn test_queue_pop_priority() {
        let mut queue = PriorityQueue::new();
        
        queue.push(create_test_event("low", Priority::Low)).is_ok();
        
        // Запрашиваем Critical - должны получить None
        let result = queue.pop_priority(Priority::Critical);
        assert!(result.is_none());
        
        // Запрашиваем Low - должны получить Low
        let result = queue.pop_priority(Priority::Low);
        assert!(result.is_some());
        assert_eq!(result.unwrap().priority, Priority::Low);
    }

    #[test]
    fn test_queue_fill_ratio() {
        let mut queue = PriorityQueue::new();
        
        // Заполняем на 50%
        for _ in 0..50 {
            queue.push(create_test_event("c", Priority::Critical)).is_ok();
        }
        
        let ratio = queue.fill_ratio(Priority::Critical);
        assert!((ratio - 0.5).abs() < 0.001);
    }

    #[test]
    fn test_queue_drop_events() {
        let mut queue = PriorityQueue::new();
        
        for i in 0..10 {
            queue.push(create_test_event(&format!("low_{}", i), Priority::Low)).is_ok();
        }
        
        let dropped = queue.drop_low_events(5);
        assert_eq!(dropped, 5);
        assert_eq!(queue.size(Priority::Low), 5);
    }

    #[test]
    fn test_queue_clear() {
        let mut queue = PriorityQueue::new();
        
        queue.push(create_test_event("1", Priority::Critical)).is_ok();
        queue.push(create_test_event("2", Priority::High)).is_ok();
        queue.push(create_test_event("3", Priority::Normal)).is_ok();
        
        queue.clear();
        
        assert!(queue.is_empty());
    }

    #[test]
    fn test_queue_custom_capacity() {
        let capacity = QueueCapacity::new(10, 20, 30, 40);
        let queue = PriorityQueue::with_capacity(capacity);
        
        assert_eq!(queue.capacity().critical, 10);
        assert_eq!(queue.capacity().high, 20);
        assert_eq!(queue.capacity().normal, 30);
        assert_eq!(queue.capacity().low, 40);
    }

    #[test]
    fn test_queue_metrics() {
        let mut queue = PriorityQueue::new();
        
        queue.push(create_test_event("1", Priority::Low)).is_ok();
        queue.push(create_test_event("2", Priority::High)).is_ok();
        
        let metrics = queue.get_metrics();
        
        assert_eq!(metrics.low_count, 1);
        assert_eq!(metrics.high_count, 1);
        assert_eq!(metrics.total(), 2);
    }

    #[test]
    fn test_push_result_is_ok() {
        assert!(PushResult::Ok.is_ok());
        
        assert!(!PushResult::CriticalQueueFull.is_ok());
        assert!(!PushResult::HighQueueFull.is_ok());
        assert!(!PushResult::NormalQueueFull.is_ok());
        assert!(!PushResult::LowQueueFull.is_ok());
    }

    #[test]
    fn test_push_result_error_message() {
        assert_eq!(PushResult::Ok.error_message(), "Успешно");
        assert_eq!(PushResult::CriticalQueueFull.error_message(), "Очередь Critical переполнена");
        assert_eq!(PushResult::HighQueueFull.error_message(), "Очередь High переполнена");
        assert_eq!(PushResult::NormalQueueFull.error_message(), "Очередь Normal переполнена");
        assert_eq!(PushResult::LowQueueFull.error_message(), "Очередь Low переполнена");
    }
}

mod backpressure_tests {
    use super::*;

    fn create_test_event(priority: Priority) -> Event {
        Event::new("TEST", "SOURCE", serde_json::json!({}))
            .with_priority(priority)
    }

    #[test]
    fn test_backpressure_normal_event() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        let result = handler.push(create_test_event(Priority::Normal));
        assert_eq!(result, HandleResult::Accepted);
    }

    #[test]
    fn test_backpressure_critical_never_dropped() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        // Заполняем очередь полностью
        for _ in 0..20_000 {
            handler.push(create_test_event(Priority::Normal));
        }
        
        // Critical должен либо пройти, либо заблокировать, но НЕ быть дропнутым
        let result = handler.push(create_test_event(Priority::Critical));
        
        match result {
            HandleResult::Dropped(Priority::Critical) => {
                panic!("Critical event was dropped - this should never happen!");
            }
            _ => {} // Accepted или Blocked допустимы
        }
    }

    #[test]
    fn test_backpressure_strategy_default() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        assert_eq!(handler.get_strategy(), BackpressureStrategy::DropLow);
    }

    #[test]
    fn test_backpressure_strategy_change() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        handler.set_strategy(BackpressureStrategy::DropNormal);
        assert_eq!(handler.get_strategy(), BackpressureStrategy::DropNormal);
        
        handler.set_strategy(BackpressureStrategy::Overflow);
        assert_eq!(handler.get_strategy(), BackpressureStrategy::Overflow);
        
        handler.set_strategy(BackpressureStrategy::BlockCritical);
        assert_eq!(handler.get_strategy(), BackpressureStrategy::BlockCritical);
    }

    #[test]
    fn test_backpressure_threshold() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        assert_eq!(handler.get_threshold(), 0.9);
        
        handler.set_threshold(0.5);
        assert_eq!(handler.get_threshold(), 0.5);
        
        // Test clamping
        handler.set_threshold(1.5);
        assert_eq!(handler.get_threshold(), 1.0);
        
        handler.set_threshold(-0.5);
        assert_eq!(handler.get_threshold(), 0.0);
    }

    #[test]
    fn test_backpressure_pop_order() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        let _ = handler.push(create_test_event(Priority::Low));
        let _ = handler.push(create_test_event(Priority::High));
        let _ = handler.push(create_test_event(Priority::Critical));
        
        // Первым должен прийти Critical
        let first = handler.pop().unwrap();
        assert_eq!(first.priority, Priority::Critical);
        
        let second = handler.pop().unwrap();
        assert_eq!(second.priority, Priority::High);
        
        let third = handler.pop().unwrap();
        assert_eq!(third.priority, Priority::Low);
    }

    #[test]
    fn test_backpressure_len() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        assert!(handler.is_empty());
        
        let _ = handler.push(create_test_event(Priority::Normal));
        
        assert!(!handler.is_empty());
    }

    #[test]
    fn test_backpressure_fill_ratio() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        // Normal заполняем на 10%
        for _ in 0..1000 {
            let _ = handler.push(create_test_event(Priority::Normal));
        }
        
        let ratio = handler.fill_ratio(Priority::Normal);
        assert!((ratio - 0.1).abs() < 0.001);
    }

    #[test]
    fn test_backpressure_metrics() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        let _ = handler.push(create_test_event(Priority::Normal));
        
        let metrics = handler.get_metrics();
        assert_eq!(metrics.dropped.total_dropped(), 0);
    }

    #[test]
    fn test_backpressure_reset_metrics() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        // Заполняем
        for _ in 0..60_000 {
            let _ = handler.push(create_test_event(Priority::Low));
        }
        // Дропаем
        let _ = handler.push(create_test_event(Priority::Low));
        
        let stats = handler.get_dropped_stats();
        assert!(stats.dropped_low > 0);
        
        handler.reset_metrics();
        
        let stats_after = handler.get_dropped_stats();
        assert_eq!(stats_after.dropped_low, 0);
    }

    #[test]
    fn test_backpressure_trigger_count() {
        let handler = BackpressureHandler::new(QueueCapacity::default());
        
        // Несколько push
        for _ in 0..100 {
            let _ = handler.push(create_test_event(Priority::Normal));
        }
        
        // Заполняем до срабатывания backpressure
        for _ in 0..10_000 {
            handler.push(create_test_event(Priority::Normal));
        }
        
        let metrics = handler.get_metrics();
        assert!(metrics.trigger_count > 0);
    }

    #[test]
    fn test_backpressure_strategy_from_str() {
        assert_eq!(BackpressureStrategy::parse("drop_low"), Some(BackpressureStrategy::DropLow));
        assert_eq!(BackpressureStrategy::parse("DROP_LOW"), Some(BackpressureStrategy::DropLow));
        assert_eq!(BackpressureStrategy::parse("drop_normal"), Some(BackpressureStrategy::DropNormal));
        assert_eq!(BackpressureStrategy::parse("overflow"), Some(BackpressureStrategy::Overflow));
        assert_eq!(BackpressureStrategy::parse("block_critical"), Some(BackpressureStrategy::BlockCritical));
        assert_eq!(BackpressureStrategy::parse("invalid"), None);
    }

    #[test]
    fn test_backpressure_dropped_stats() {
        let mut stats = cryptotechnolog_eventbus::DroppedStats::default();
        
        stats.dropped_low = 10;
        stats.dropped_normal = 5;
        stats.dropped_high = 2;
        stats.dropped_critical = 0;
        
        assert_eq!(stats.total_dropped(), 17);
        
        stats.reset();
        
        assert_eq!(stats.total_dropped(), 0);
    }
}

mod event_priority_tests {
    use super::*;

    #[test]
    fn test_event_default_priority() {
        let event = Event::new("TEST", "SOURCE", serde_json::json!({}));
        assert_eq!(event.priority, Priority::Normal);
    }

    #[test]
    fn test_event_with_priority() {
        let event = Event::new("TEST", "SOURCE", serde_json::json!({}))
            .with_priority(Priority::Critical);
        assert_eq!(event.priority, Priority::Critical);
        
        let event2 = Event::new("TEST", "SOURCE", serde_json::json!({}))
            .with_priority(Priority::Low);
        assert_eq!(event2.priority, Priority::Low);
    }

    #[test]
    fn test_event_requires_persistence() {
        let critical_event = Event::new("TEST", "SOURCE", serde_json::json!({}))
            .with_priority(Priority::Critical);
        assert!(critical_event.requires_persistence());
        
        let normal_event = Event::new("TEST", "SOURCE", serde_json::json!({}));
        assert!(!normal_event.requires_persistence());
    }

    #[test]
    fn test_event_is_droppable() {
        let critical_event = Event::new("TEST", "SOURCE", serde_json::json!({}))
            .with_priority(Priority::Critical);
        assert!(!critical_event.is_droppable());
        
        let low_event = Event::new("TEST", "SOURCE", serde_json::json!({}))
            .with_priority(Priority::Low);
        assert!(low_event.is_droppable());
    }
}
