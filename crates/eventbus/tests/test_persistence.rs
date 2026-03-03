// ==================== Persistence Unit Tests ====================
// Тесты для PersistenceLayer

use cryptotechnolog_eventbus::persistence::{
    PersistenceConfig, PersistenceError, PersistenceMetrics, PersistResult,
};

#[test]
fn test_persistence_config_default() {
    let config = PersistenceConfig::default();

    assert_eq!(config.max_stream_len, 100_000);
    assert_eq!(config.batch_size, 100);
    assert_eq!(config.ttl_critical, 30 * 24 * 60 * 60);
    assert_eq!(config.ttl_high, 7 * 24 * 60 * 60);
    assert_eq!(config.ttl_normal, 3 * 24 * 60 * 60);
    assert_eq!(config.ttl_low, 1 * 24 * 60 * 60);
}

#[test]
fn test_persistence_config_custom() {
    let config = PersistenceConfig {
        max_stream_len: 50_000,
        batch_size: 200,
        ttl_critical: 60 * 24 * 60 * 60,
        ttl_high: 14 * 24 * 60 * 60,
        ttl_normal: 7 * 24 * 60 * 60,
        ttl_low: 2 * 24 * 60 * 60,
    };

    assert_eq!(config.max_stream_len, 50_000);
    assert_eq!(config.batch_size, 200);
    assert_eq!(config.ttl_critical, 60 * 24 * 60 * 60);
}

#[test]
fn test_persistence_config_ttl_by_priority() {
    use cryptotechnolog_eventbus::Priority;

    let config = PersistenceConfig::default();

    assert_eq!(config.get_ttl(Priority::Critical), 30 * 24 * 60 * 60);
    assert_eq!(config.get_ttl(Priority::High), 7 * 24 * 60 * 60);
    assert_eq!(config.get_ttl(Priority::Normal), 3 * 24 * 60 * 60);
    assert_eq!(config.get_ttl(Priority::Low), 1 * 24 * 60 * 60);
}

#[test]
fn test_persistence_metrics_default() {
    let metrics = PersistenceMetrics::default();

    assert_eq!(metrics.persisted_count, 0);
    assert_eq!(metrics.save_errors, 0);
    assert_eq!(metrics.replay_count, 0);
    assert_eq!(metrics.replay_errors, 0);
}

#[test]
fn test_persistence_metrics_increment() {
    let mut metrics = PersistenceMetrics::default();

    metrics.persisted_count = 10;
    metrics.save_errors = 2;
    metrics.replay_count = 5;
    metrics.replay_errors = 1;

    assert_eq!(metrics.persisted_count, 10);
    assert_eq!(metrics.save_errors, 2);
    assert_eq!(metrics.replay_count, 5);
    assert_eq!(metrics.replay_errors, 1);
}

#[test]
fn test_persist_result() {
    let result = PersistResult {
        stream_id: "1234567890-0".to_string(),
        persisted_at: 1704067200000000,
    };

    assert_eq!(result.stream_id, "1234567890-0");
    assert_eq!(result.persisted_at, 1704067200000000);
}

#[test]
fn test_persist_result_clone() {
    let result = PersistResult {
        stream_id: "test-id".to_string(),
        persisted_at: 1234567890,
    };

    let cloned = result.clone();

    assert_eq!(result.stream_id, cloned.stream_id);
    assert_eq!(result.persisted_at, cloned.persisted_at);
}

#[test]
fn test_persistence_error_display() {
    let err_serialization = PersistenceError::Serialization("JSON error".to_string());
    let err_deserialization = PersistenceError::Deserialization("Parse error".to_string());
    let err_redis = PersistenceError::Redis("Connection refused".to_string());
    let err_stream = PersistenceError::StreamNotFound("events:test".to_string());
    let err_connection = PersistenceError::Connection("Timeout".to_string());

    assert!(err_serialization.to_string().contains("JSON error"));
    assert!(err_deserialization.to_string().contains("Parse error"));
    assert!(err_redis.to_string().contains("Connection refused"));
    assert!(err_stream.to_string().contains("events:test"));
    assert!(err_connection.to_string().contains("Timeout"));
}

#[test]
fn test_persistence_error_debug() {
    let err = PersistenceError::Serialization("test".to_string());
    let debug_str = format!("{:?}", err);

    assert!(debug_str.contains("Serialization"));
    assert!(debug_str.contains("test"));
}

#[test]
fn test_persistence_metrics_clone() {
    let metrics = PersistenceMetrics {
        persisted_count: 100,
        save_errors: 5,
        replay_count: 50,
        replay_errors: 2,
    };

    let cloned = metrics.clone();

    assert_eq!(metrics.persisted_count, cloned.persisted_count);
    assert_eq!(metrics.save_errors, cloned.save_errors);
    assert_eq!(metrics.replay_count, cloned.replay_count);
    assert_eq!(metrics.replay_errors, cloned.replay_errors);
}

#[test]
fn test_persistence_config_clone() {
    let config = PersistenceConfig::default();
    let cloned = config.clone();

    assert_eq!(config.max_stream_len, cloned.max_stream_len);
    assert_eq!(config.batch_size, cloned.batch_size);
    assert_eq!(config.ttl_critical, cloned.ttl_critical);
}

#[test]
fn test_persistence_ttl_edge_cases() {
    use cryptotechnolog_eventbus::Priority;

    let config = PersistenceConfig {
        max_stream_len: 1000,
        batch_size: 10,
        ttl_critical: 0, //edge case: 0 TTL
        ttl_high: 1,
        ttl_normal: 2,
        ttl_low: 3,
    };

    assert_eq!(config.get_ttl(Priority::Critical), 0);
    assert_eq!(config.get_ttl(Priority::High), 1);
    assert_eq!(config.get_ttl(Priority::Normal), 2);
    assert_eq!(config.get_ttl(Priority::Low), 3);
}

#[test]
fn test_persistence_stream_id_format() {
    // Redis stream IDs have format "timestamp-sequence"
    let result = PersistResult {
        stream_id: "1704067200000000-0".to_string(),
        persisted_at: 1704067200000000,
    };

    // Проверяем формат
    let parts: Vec<&str> = result.stream_id.split('-').collect();
    assert_eq!(parts.len(), 2);
    
    // Первая часть должна быть timestamp
    let timestamp_part = parts[0].parse::<u64>();
    assert!(timestamp_part.is_ok());
}
