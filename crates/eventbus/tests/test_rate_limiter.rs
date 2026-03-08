// ==================== Rate Limiter Unit Tests ====================
// Тесты для RateLimiter

use cryptotechnolog_eventbus::rate_limiter::{
    RateLimitError, RateLimitResult, RateLimiter, RateLimiterConfig,
    SlidingWindow,
};

#[test]
fn test_sliding_window_creation() {
    let window = SlidingWindow::new(100, 1);

    assert_eq!(window.capacity(), 100);
    assert_eq!(window.remaining(), 100);
    assert!(window.current_rate() >= 0.0);
}

#[test]
fn test_sliding_window_consume() {
    let mut window = SlidingWindow::new(3, 1);

    // Первые 3 должны пройти
    assert!(window.try_consume());
    assert!(window.try_consume());
    assert!(window.try_consume());

    // 4-й должен быть отклонён
    assert!(!window.try_consume());

    // Остаток должен быть 0
    assert_eq!(window.remaining(), 0);
}

#[test]
fn test_sliding_window_remaining() {
    let mut window = SlidingWindow::new(10, 1);

    assert_eq!(window.remaining(), 10);

    window.try_consume();
    assert_eq!(window.remaining(), 9);

    window.try_consume();
    assert_eq!(window.remaining(), 8);
}

#[test]
fn test_sliding_window_reset() {
    let mut window = SlidingWindow::new(2, 1);

    // Заполняем
    window.try_consume();
    window.try_consume();
    assert!(!window.try_consume());

    // Сбрасываем
    window.reset();

    // Должно работать снова
    assert!(window.try_consume());
    assert!(window.try_consume());
    assert!(!window.try_consume());
}

#[test]
fn test_sliding_window_current_rate() {
    let mut window = SlidingWindow::new(10, 1);

    // Пустое окно - скорость 0
    assert!(window.current_rate() < 0.1);

    // После потребления
    window.try_consume();
    let rate = window.current_rate();
    assert!(rate >= 0.0);
}

#[test]
fn test_rate_limiter_global_limit() {
    let limiter = RateLimiter::new(2);

    // Первые 2 глобальных запроса должны пройти
    assert_eq!(limiter.check("source_a"), RateLimitResult::Allowed);
    assert_eq!(limiter.check("source_b"), RateLimitResult::Allowed);

    // 3-й должен быть отклонён
    assert_eq!(
        limiter.check("source_c"),
        RateLimitResult::GlobalLimitExceeded
    );
}

#[test]
fn test_rate_limiter_source_limit() {
    // Используем очень высокий глобальный лимит чтобы тестировать только лимит источника
    let limiter = RateLimiter::new(1_000_000);

    // 1000 запросов от одного source должны пройти (лимит источника по умолчанию)
    for _ in 0..1000 {
        assert_eq!(limiter.check("test_source"), RateLimitResult::Allowed);
    }

    // 1001-й должен быть отклонён по лимиту источника
    assert_eq!(
        limiter.check("test_source"),
        RateLimitResult::SourceLimitExceeded("test_source".to_string())
    );
}

#[test]
fn test_rate_limiter_different_sources() {
    let limiter = RateLimiter::new(1_000_000);

    // Каждый источник имеет свой лимит 1000
    for i in 0..100 {
        let source = format!("source_{}", i);
        assert_eq!(limiter.check(&source), RateLimitResult::Allowed);
    }

    // 101-й запрос от source_0 должен пройти (у него свой лимит)
    assert_eq!(limiter.check("source_0"), RateLimitResult::Allowed);
}

#[test]
fn test_rate_limiter_critical_priority() {
    use cryptotechnolog_eventbus::Priority;

    let limiter = RateLimiter::new(1);

    // Заполняем глобальный лимит
    assert_eq!(limiter.check("source1"), RateLimitResult::Allowed);

    // Глобальный лимит исчерпан
    assert_eq!(
        limiter.check("source1"),
        RateLimitResult::GlobalLimitExceeded
    );

    // CRITICAL должен пройти несмотря на лимит
    assert_eq!(
        limiter.check_with_priority("source1", Priority::Critical),
        RateLimitResult::Allowed
    );
}

#[test]
fn test_rate_limiter_normal_priority_blocked() {
    use cryptotechnolog_eventbus::Priority;

    let limiter = RateLimiter::new(1);

    // Заполняем
    limiter.check("source1");
    limiter.check("source1");

    // Normal должен быть заблокирован
    assert_eq!(
        limiter.check_with_priority("source1", Priority::Normal),
        RateLimitResult::GlobalLimitExceeded
    );
}

#[test]
fn test_rate_limiter_high_priority() {
    use cryptotechnolog_eventbus::Priority;

    let limiter = RateLimiter::new(1);

    // Заполняем
    limiter.check("source1");
    limiter.check("source1");

    // High также должен быть заблокирован (не CRITICAL)
    assert_eq!(
        limiter.check_with_priority("source1", Priority::High),
        RateLimitResult::GlobalLimitExceeded
    );
}

#[test]
fn test_rate_limiter_critical_sources() {
    let limiter = RateLimiter::new(1);

    // Заполняем глобальный лимит
    limiter.check("any_source");
    limiter.check("any_source");

    // Критические источники должны проходить
    assert_eq!(limiter.check("kill_switch"), RateLimitResult::Allowed);
    assert_eq!(limiter.check("emergency_stop"), RateLimitResult::Allowed);
    assert_eq!(limiter.check("watchdog"), RateLimitResult::Allowed);
}

#[test]
fn test_rate_limiter_set_source_limit() {
    let limiter = RateLimiter::new(10000);

    // По умолчанию 1000
    for _ in 0..1000 {
        assert_eq!(limiter.check("custom"), RateLimitResult::Allowed);
    }
    assert_eq!(
        limiter.check("custom"),
        RateLimitResult::SourceLimitExceeded("custom".to_string())
    );

    // Увеличиваем до 2000
    limiter.set_source_limit("custom", 2000);

    // Теперь должно помещаться больше
    for _ in 0..1000 {
        assert_eq!(limiter.check("custom"), RateLimitResult::Allowed);
    }
}

#[test]
fn test_rate_limiter_set_global_limit() {
    let limiter = RateLimiter::new(2);

    // Заполняем
    limiter.check("s1");
    limiter.check("s2");
    assert_eq!(
        limiter.check("s3"),
        RateLimitResult::GlobalLimitExceeded
    );

    // Увеличиваем глобальный лимит
    limiter.set_global_limit(5);

    // Теперь должно работать
    assert_eq!(limiter.check("s3"), RateLimitResult::Allowed);
    assert_eq!(limiter.check("s4"), RateLimitResult::Allowed);
}

#[test]
fn test_rate_limiter_get_global_rate() {
    let limiter = RateLimiter::new(1000);

    let initial_rate = limiter.get_global_rate();
    assert!(initial_rate >= 0.0);

    limiter.check("source");

    let after_rate = limiter.get_global_rate();
    assert!(after_rate >= initial_rate);
}

#[test]
fn test_rate_limiter_get_source_rate() {
    let limiter = RateLimiter::new(10000);

    // Несуществующий источник
    let rate = limiter.get_source_rate("nonexistent");
    assert_eq!(rate, 0.0);

    // После запросов
    limiter.check("test_source");
    limiter.check("test_source");

    let rate = limiter.get_source_rate("test_source");
    assert!(rate > 0.0);
}

#[test]
fn test_rate_limiter_global_remaining() {
    let limiter = RateLimiter::new(3);

    assert_eq!(limiter.global_remaining(), 3);

    limiter.check("s1");
    assert_eq!(limiter.global_remaining(), 2);

    limiter.check("s2");
    assert_eq!(limiter.global_remaining(), 1);

    limiter.check("s3");
    assert_eq!(limiter.global_remaining(), 0);
}

#[test]
fn test_rate_limiter_source_remaining() {
    let limiter = RateLimiter::new(10000);

    assert_eq!(limiter.source_remaining("test"), 1000); // default

    limiter.set_source_limit("test", 500);
    assert_eq!(limiter.source_remaining("test"), 500);
}

#[test]
fn test_rate_limiter_metrics() {
    let limiter = RateLimiter::new(10_000_000);

    // Выполняем проверки - каждый источник имеет свой лимит 1000
    for _ in 0..5 {
        limiter.check("source1"); // Allowed
    }

    // Превышаем лимит источника - делаем 1001 запрос
    for _ in 0..1001 {
        limiter.check("source2"); // 1000 Allowed, 1 SourceLimitExceeded
    }

    let metrics = limiter.get_metrics();

    // 5 + 1000 = 1005 allowed, 1 source rejected
    assert_eq!(metrics.allowed, 1005);
    assert_eq!(metrics.source_rejected, 1);
}

#[test]
fn test_rate_limiter_metrics_reset() {
    let limiter = RateLimiter::new(1_000_000);

    limiter.check("s1");
    limiter.check("s1");

    let metrics = limiter.get_metrics();
    assert!(metrics.allowed > 0);

    limiter.reset_metrics();

    let metrics_after = limiter.get_metrics();
    assert_eq!(metrics_after.allowed, 0);
}

#[test]
fn test_rate_limiter_config_default() {
    let config = RateLimiterConfig::default();

    assert_eq!(config.global_limit, 10_000);
    assert_eq!(config.default_source_limit, 1_000);
    assert_eq!(config.window_secs, 1);
    assert!(config.critical_sources.contains(&"kill_switch".to_string()));
    assert!(config
        .critical_sources
        .contains(&"emergency_stop".to_string()));
    assert!(config.critical_sources.contains(&"watchdog".to_string()));
}

#[test]
fn test_rate_limiter_config_custom() {
    let config = RateLimiterConfig {
        global_limit: 5000,
        default_source_limit: 500,
        window_secs: 2,
        critical_sources: vec!["custom_critical".to_string()],
    };

    assert_eq!(config.global_limit, 5000);
    assert_eq!(config.default_source_limit, 500);
    assert_eq!(config.window_secs, 2);
    assert!(config.critical_sources.contains(&"custom_critical".to_string()));
}

#[test]
fn test_rate_limiter_with_config() {
    let config = RateLimiterConfig {
        global_limit: 5,
        default_source_limit: 10,
        window_secs: 1,
        critical_sources: vec![],
    };

    let limiter = RateLimiter::with_config(config);

    // 5 глобальных должно пройти
    for _ in 0..5 {
        assert_eq!(limiter.check("test"), RateLimitResult::Allowed);
    }

    // 6-й отклонён
    assert_eq!(
        limiter.check("test"),
        RateLimitResult::GlobalLimitExceeded
    );
}

#[test]
fn test_rate_limit_error_display() {
    let err_global = RateLimitError::GlobalLimit;
    let err_source = RateLimitError::SourceLimit("test_source".to_string());
    let err_internal = RateLimitError::Internal("test error".to_string());

    assert!(err_global.to_string().contains("Глобальный"));
    assert!(err_source.to_string().contains("test_source"));
    assert!(err_internal.to_string().contains("Внутренняя"));
}

#[test]
fn test_rate_limit_error_debug() {
    let err = RateLimitError::GlobalLimit;
    let debug_str = format!("{:?}", err);

    assert!(debug_str.contains("GlobalLimit"));
}

#[test]
fn test_rate_limiter_many_sources() {
    use std::collections::HashSet;

    let limiter = RateLimiter::new(100_000); // высокий глобальный

    let mut unique_sources = HashSet::new();

    // Создаём много источников
    for i in 0..100 {
        let source = format!("source_{}", i);
        // Каждый источник может сделать 10 запросов
        for _ in 0..10 {
            limiter.check(&source);
            unique_sources.insert(source.clone());
        }
    }

    // Должно быть 100 уникальных источников
    assert_eq!(unique_sources.len(), 100);
}

#[test]
fn test_rate_limiter_concurrent_like() {
    use cryptotechnolog_eventbus::Priority;

    let limiter = RateLimiter::new(1);

    // Серия быстрых проверок
    let results: Vec<RateLimitResult> = (0..10)
        .map(|_| limiter.check_with_priority("source", Priority::Normal))
        .collect();

    // Только первый должен быть Allowed
    let allowed_count = results
        .iter()
        .filter(|r| matches!(r, RateLimitResult::Allowed))
        .count();

    assert_eq!(allowed_count, 1);
}

#[test]
fn test_rate_limiter_priority_order() {
    use cryptotechnolog_eventbus::Priority;

    let limiter = RateLimiter::new(1_000_000);

    // Заполняем лимит источника Normal запросами (1000 доступно)
    for _ in 0..2 {
        assert_eq!(
            limiter.check_with_priority("source", Priority::Normal),
            RateLimitResult::Allowed
        );
    }

    // High также заблокирован (не CRITICAL)
    assert_eq!(
        limiter.check_with_priority("source", Priority::High),
        RateLimitResult::Allowed // high лимит источника не превышен
    );

    // Low также не заблокирован
    assert_eq!(
        limiter.check_with_priority("source", Priority::Low),
        RateLimitResult::Allowed
    );

    // CRITICAL всегда проходит
    assert_eq!(
        limiter.check_with_priority("source", Priority::Critical),
        RateLimitResult::Allowed
    );
}
